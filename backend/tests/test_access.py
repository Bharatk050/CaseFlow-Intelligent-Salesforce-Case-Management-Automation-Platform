"""Security and workflow regressions; all Salesforce traffic is mocked."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import main
import salesforce

CASE_A = "500000000000001AAA"
CASE_B = "500000000000002AAA"
ORG = "https://example.my.salesforce.com"


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(salesforce, "DB_PATH", tmp_path / "sessions.sqlite3")
    monkeypatch.setattr(main, "TICKETS_DIR", tmp_path / "tickets")
    monkeypatch.setenv("SALESFORCE_SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("SALESFORCE_CLIENT_ID", "test-client")
    monkeypatch.setenv("SALESFORCE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("SALESFORCE_REDIRECT_URI", "http://testserver/auth/salesforce/callback")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SALESFORCE_ALLOW_WRITEBACK", raising=False)
    def deny_network(*args, **kwargs):
        raise AssertionError("Unexpected external request")
    monkeypatch.setattr(salesforce, "_json_request", deny_network)
    return TestClient(main.app, base_url="https://testserver", client=("127.0.0.1", 50000))


def session(client, token="session-a", user="user-a", expiry=None, org=ORG):
    expires = expiry or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with salesforce._connect() as connection:
        connection.execute("INSERT INTO salesforce_sessions (session_hash, access_token, instance_url, user_id, expires_at) VALUES (?, ?, ?, ?, ?)", (salesforce._hash(token), salesforce._encrypt("fake-access"), org, user, expires))
    client.cookies.set(salesforce.COOKIE_NAME, token)


def ticket(ticket_id="LOCAL-A", **fields):
    return main.save_ticket({"id": ticket_id, "subject": "Password reset", "customer": "Synthetic customer", "message": "A teacher forgot their password.", "created_at": main.now(), "created_by": "user-a", "salesforce_instance_url": ORG, **main.pending_approach(), **fields})


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/tickets", None), ("GET", "/cases", None),
    ("GET", "/tickets/LOCAL-A", None), ("GET", "/team/performance", None),
    ("GET", "/knowledge-base", None),
    ("POST", "/tickets", {"subject": "Test case", "customer": "Test", "message": "Example request"}),
    ("POST", "/tickets/import/excel", None),
    ("POST", "/tickets/LOCAL-A/suggest-approach", {}),
    ("PATCH", "/tickets/LOCAL-A", {"status": "resolved"}),
])
def test_private_routes_require_session(environment, method, path, body):
    response = environment.request(method, path, json=body, headers={"X-Team-Member-ID": "alex-rivera"})
    assert response.status_code == 401


def test_ticket_visibility_and_direct_access(environment, monkeypatch):
    session(environment)
    ticket()
    ticket("OTHER", created_by="user-b")
    ticket("LEGACY", created_by=None)
    ticket("OTHER-ORG", salesforce_instance_url="https://other.example")
    first = main.mirror_salesforce_case({"Id": CASE_A}, ORG)
    second = main.mirror_salesforce_case({"Id": CASE_B}, ORG)
    monkeypatch.setattr(salesforce, "accessible_case_ids", lambda s, ids: {CASE_A} & set(ids))
    assert {item["id"] for item in environment.get("/tickets").json()} == {"LOCAL-A", first["id"]}
    assert [item["id"] for item in environment.get("/cases").json()] == [first["id"]]
    for denied in ["OTHER", "LEGACY", "OTHER-ORG", second["id"]]:
        assert environment.get(f"/tickets/{denied}").status_code == 404
        assert environment.patch(f"/tickets/{denied}", json={"status": "resolved"}).status_code == 404
        assert environment.post(f"/tickets/{denied}/suggest-approach", json={}).status_code == 404
    monkeypatch.setattr(salesforce, "accessible_case_ids", lambda s, ids: set())
    assert environment.get(f"/tickets/{first['id']}").status_code == 404
    assert environment.get("/cases").json() == []


def test_mirrors_are_separate_per_org(environment):
    a = main.mirror_salesforce_case({"Id": CASE_A, "Subject": "First org"}, ORG)
    b = main.mirror_salesforce_case({"Id": CASE_A, "Subject": "Second org"}, "https://other.example")
    assert a["id"] != b["id"]
    assert main.load_ticket(a["id"])["subject"] == "First org"


def test_writeback_is_off_by_default_and_requires_flag(environment, monkeypatch):
    session(environment)
    with pytest.raises(HTTPException) as error:
        salesforce.assign_to_me("session-a", CASE_A)
    assert error.value.status_code == 403
    calls = []
    monkeypatch.setattr(salesforce, "_json_request", lambda *args, **kwargs: calls.append(kwargs) or {})
    monkeypatch.setenv("SALESFORCE_ALLOW_WRITEBACK", "true")
    assert salesforce.assign_to_me("session-a", CASE_A) == "user-a"
    assert calls == [{"method": "PATCH", "token": "fake-access", "body": {"OwnerId": "user-a"}}]


def test_expired_and_legacy_sessions_rejected(environment):
    session(environment, expiry=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    assert environment.get("/tickets").status_code == 401
    with salesforce._connect() as connection:
        assert connection.execute("SELECT count(*) FROM salesforce_sessions").fetchone()[0] == 0
    session(environment, token="legacy")
    with salesforce._connect() as connection:
        connection.execute("UPDATE salesforce_sessions SET expires_at=NULL")
    assert environment.get("/tickets").status_code == 401


def test_expired_oauth_state_consumed_without_token_exchange(environment):
    state = "old-state"
    with salesforce._connect() as connection:
        connection.execute("INSERT INTO oauth_pending VALUES (?, ?, ?)", (salesforce._hash(state), salesforce._encrypt("verifier"), (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()))
    with pytest.raises(HTTPException) as error:
        salesforce.complete_authorization("code", state)
    assert error.value.status_code == 400
    with salesforce._connect() as connection:
        assert connection.execute("SELECT count(*) FROM oauth_pending").fetchone()[0] == 0


def test_oauth_callback_requires_initiating_browser(environment, monkeypatch):
    response = environment.get("/auth/salesforce", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    assert environment.cookies.get(salesforce.STATE_COOKIE) == state
    monkeypatch.setattr(salesforce, "complete_authorization", lambda code, value: "new-session")
    assert environment.get("/auth/salesforce/callback", params={"code": "code", "state": "wrong"}, follow_redirects=False).status_code == 400
    response = environment.get("/auth/salesforce/callback", params={"code": "code", "state": state}, follow_redirects=False)
    assert response.status_code == 307
    assert environment.cookies.get(salesforce.COOKIE_NAME) == "new-session"
    assert not environment.cookies.get(salesforce.STATE_COOKIE)


def test_local_workflow_attributes_authenticated_user(environment):
    session(environment)
    created = environment.post("/tickets", json={"subject": "Password reset", "customer": "Synthetic teacher", "message": "A teacher forgot their password."}).json()
    path = f"/tickets/{created['id']}"
    assert created["created_by"] == "user-a"
    assert created["ai_mode"] == "not_requested"
    response = environment.patch(path, json={"status": "in_progress", "owner": "Agent", "resolution_note": "Investigating"}, headers={"X-Team-Member-ID": "alex-rivera"})
    assert response.status_code == 200
    assert response.json()["activity"][-1]["member_id"] == "user-a"
    suggested = environment.post(path + "/suggest-approach", json={}).json()
    assert suggested["suggested_approach"]
    assert suggested["status"] == "in_progress"
    assert suggested["rag_articles"]
    counts = environment.get("/team/performance").json()[0]
    assert (counts["case_updates"], counts["suggestions_requested"], counts["cases_touched"]) == (1, 1, 1)
    assert environment.post("/team/sign-in", json={"member_id": "alex-rivera"}).status_code == 403


@pytest.mark.parametrize("message", ["I am reporting harassment.", "The caller is abusive.", "Someone is threatening the teacher.", "This is discrimination."])
def test_conduct_variants_escalate(environment, message):
    result = main.rag_triage("Conduct report", message)
    assert result["status"] == "escalated"
    assert result["requires_human"]


def test_low_confidence_escalates(environment):
    result = main.rag_triage("Unclear request", "xyzzy quux blorb")
    assert result["confidence"] < .7
    assert result["status"] == "escalated"


def test_record_visibility_uses_current_user_token(environment, monkeypatch):
    session(environment)
    calls = []
    def response(url, **kwargs):
        calls.append((url, kwargs))
        return {"records": [{"Id": CASE_A}]}
    monkeypatch.setattr(salesforce, "_json_request", response)
    assert salesforce.accessible_case_ids(salesforce._session("session-a"), [CASE_A, CASE_B, "invalid'"]) == {CASE_A}
    assert calls[0][1]["token"] == "fake-access"
    query = parse_qs(urlparse(calls[0][0]).query)["q"][0]
    assert "invalid" not in query
    assert CASE_A in query and CASE_B in query


def test_oauth_state_is_one_time_and_new_session_has_expiry(environment, monkeypatch):
    url = salesforce.authorization_url()
    state = parse_qs(urlparse(url).query)["state"][0]
    def response(url, **kwargs):
        if url.endswith('/token'):
            return {"access_token": "token", "instance_url": ORG, "id": ORG + "/identity"}
        return {"user_id": "user-a"}
    monkeypatch.setattr(salesforce, "_json_request", response)
    token = salesforce.complete_authorization("code", state)
    assert salesforce._session(token).user_id == "user-a"
    with salesforce._connect() as connection:
        row = connection.execute("SELECT * FROM salesforce_sessions").fetchone()
        assert not salesforce._expired(row["expires_at"])
        assert row["access_token"] != b"token"
    with pytest.raises(HTTPException) as error:
        salesforce.complete_authorization("code", state)
    assert error.value.status_code == 400


def test_assignment_endpoint_denies_unseen_case_and_disabled_writeback(environment, monkeypatch):
    session(environment)
    main.mirror_salesforce_case({"Id": CASE_A}, ORG)
    monkeypatch.setattr(salesforce, "accessible_case_ids", lambda s, ids: set())
    assert environment.post(f"/cases/{CASE_A}/assign-me").status_code == 404
    monkeypatch.setattr(salesforce, "accessible_case_ids", lambda s, ids: {CASE_A})
    assert environment.post(f"/cases/{CASE_A}/assign-me").status_code == 403


def test_status_hides_assignment_when_writeback_disabled(environment, monkeypatch):
    session(environment)
    monkeypatch.setattr(salesforce, "_json_request", lambda *args, **kwargs: {"fields": [{"name": "OwnerId", "updateable": True}]})
    assert salesforce.status("session-a")["can_assign"] is False
    monkeypatch.setenv("SALESFORCE_ALLOW_WRITEBACK", "true")
    assert salesforce.status("session-a")["can_assign"] is True


def test_excel_import_belongs_to_authenticated_user(environment):
    from io import BytesIO
    from openpyxl import Workbook
    session(environment)
    workbook = Workbook()
    workbook.active.append(["Subject", "Customer", "Message"])
    workbook.active.append(["Test subject", "Synthetic", "Please help with this request."])
    content = BytesIO()
    workbook.save(content)
    result = environment.post("/tickets/import/excel", content=content.getvalue())
    assert result.status_code == 200
    assert result.json()["tickets"][0]["created_by"] == "user-a"
    assert len(environment.get("/tickets").json()) == 1
    session(environment, token="session-b", user="user-b")
    assert environment.get("/tickets").json() == []


def test_excel_beta_works_without_salesforce_and_is_browser_isolated(environment):
    from io import BytesIO
    from openpyxl import Workbook
    import local_beta
    response = environment.post("/auth/local-beta")
    assert response.status_code == 200
    cookie = environment.cookies.get(local_beta.COOKIE_NAME)
    assert cookie and "httponly" in response.headers["set-cookie"].lower()
    assert not environment.cookies.get(salesforce.COOKIE_NAME)
    workbook = Workbook()
    workbook.active.append(["Subject", "Customer", "Message"])
    workbook.active.append(["Password reset", "Synthetic Teacher", "I forgot my password."])
    buffer = BytesIO()
    workbook.save(buffer)
    imported = environment.post("/tickets/import/excel", content=buffer.getvalue())
    assert imported.status_code == 200
    item = imported.json()["tickets"][0]
    assert item["salesforce_instance_url"] == local_beta.SCOPE
    path = f"/tickets/{item['id']}"
    assert environment.get("/tickets?local_only=true").json()[0]["id"] == item["id"]
    assert environment.post(path + "/suggest-approach", json={}).status_code == 200
    assert environment.patch(path, json={"status": "in_progress"}).status_code == 200
    assert environment.post("/auth/local-beta").status_code == 200
    assert environment.cookies.get(local_beta.COOKIE_NAME) == cookie
    assert environment.post("/auth/salesforce/disconnect").status_code == 204
    assert environment.get(path).status_code == 200
    main.mirror_salesforce_case({"Id": CASE_A}, ORG)
    assert environment.get("/cases").json() == []
    assert environment.post(f"/cases/{CASE_A}/assign-me").status_code == 401
    other = TestClient(main.app, base_url="https://testserver", client=("127.0.0.1", 50001))
    assert other.post("/auth/local-beta").status_code == 200
    assert other.get(path).status_code == 404
    assert other.get("/tickets").json() == []


def test_beta_session_not_available_remotely(environment):
    remote = TestClient(main.app, client=("203.0.113.10", 50000))
    assert remote.post("/auth/local-beta").status_code == 403


def test_expired_beta_session_cannot_read_previous_imports(environment):
    environment.post("/auth/local-beta")
    created = environment.post("/tickets", json={"subject": "Test ticket", "customer": "Synthetic", "message": "Example request"}).json()
    with salesforce._connect() as connection:
        connection.execute("UPDATE local_beta_sessions SET expires_at=?", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),))
    assert environment.get(f"/tickets/{created['id']}").status_code == 401


def test_oauth_error_callback_is_actionable_without_token_exchange(environment):
    response = environment.get("/auth/salesforce", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    response = environment.get("/auth/salesforce/callback", params={"state": state, "error": "OAUTH_APPROVAL_ERROR_GENERIC", "error_description": "provider-private-data"}, follow_redirects=False)
    assert response.status_code == 307
    message = parse_qs(urlparse(response.headers["location"]).query)["salesforce_error"][0]
    assert "administrator" in message
    assert "provider-private-data" not in message
    with salesforce._connect() as connection:
        assert connection.execute("SELECT count(*) FROM oauth_pending").fetchone()[0] == 0


@pytest.mark.parametrize("origin", ["https://login.salesforce.com", "https://test.salesforce.com", "https://example--qa.sandbox.my.salesforce.com", "https://example.my.salesforce.com"])
def test_oauth_uses_configured_login_origin(environment, monkeypatch, origin):
    monkeypatch.setenv("SALESFORCE_LOGIN_URL", origin)
    assert salesforce.authorization_url().startswith(origin + "/services/oauth2/authorize?")


@pytest.mark.parametrize("origin", ["http://login.salesforce.com", "https://attacker.example", "https://login.salesforce.com.attacker.example", "https://user:pass@login.salesforce.com", "https://login.salesforce.com/path"])
def test_oauth_rejects_untrusted_login_origins(environment, monkeypatch, origin):
    monkeypatch.setenv("SALESFORCE_LOGIN_URL", origin)
    with pytest.raises(HTTPException) as error:
        salesforce.authorization_url()
    assert error.value.status_code == 503
