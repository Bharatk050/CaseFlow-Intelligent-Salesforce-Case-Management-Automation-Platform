from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from test_access import environment, session, main, salesforce, CASE_A, ORG


def test_save_atomic_internal_comment_and_permissions(monkeypatch):
    monkeypatch.setenv("SALESFORCE_ALLOW_WRITEBACK", "true")
    monkeypatch.setattr(salesforce, "case_edit_options", lambda s: {"can_edit_status": True, "can_edit_owner": True, "statuses": [{"value": "Pending"}]})
    calls = []
    def request(url, **kwargs):
        calls.append(kwargs)
        return {"compositeResponse": [{"httpStatusCode": 204}, {"httpStatusCode": 201}]}
    monkeypatch.setattr(salesforce, "_json_request", request)
    s = SimpleNamespace(instance_url=ORG, access_token="fake")
    salesforce.save_case(s, CASE_A, {"Status": "Pending"}, "Investigated")
    body = calls[0]["body"]
    assert body["allOrNone"] is True
    assert body["compositeRequest"][1]["body"]["IsPublished"] is False
    with pytest.raises(HTTPException):
        salesforce.save_case(s, CASE_A, {"Status": "invented"}, "")
    monkeypatch.setenv("SALESFORCE_ALLOW_WRITEBACK", "false")
    with pytest.raises(HTTPException) as error:
        salesforce.save_case(s, CASE_A, {}, "Note")
    assert error.value.status_code == 403


def test_composite_failure_never_counts_as_success(monkeypatch):
    monkeypatch.setenv("SALESFORCE_ALLOW_WRITEBACK", "true")
    monkeypatch.setattr(salesforce, "case_edit_options", lambda s: {})
    monkeypatch.setattr(salesforce, "_json_request", lambda *a, **k: {"compositeResponse": [{"httpStatusCode": 400, "body": "private detail"}]})
    with pytest.raises(HTTPException) as error:
        salesforce.save_case(SimpleNamespace(instance_url=ORG, access_token="fake"), CASE_A, {}, "Note")
    assert "private detail" not in error.value.detail


def test_endpoint_updates_only_after_salesforce_success(environment, monkeypatch):
    session(environment)
    monkeypatch.setattr(salesforce, "accessible_case_ids", lambda s, ids: set(ids))
    monkeypatch.setattr(salesforce, "display_name", lambda s: "Agent")
    item = main.mirror_salesforce_case({"Id": CASE_A, "Status": "New", "OwnerId": "005000000000001AAA"}, ORG)
    body = {"status": "Pending", "owner": "005000000000001AAA", "resolution_note": "Checked the account"}
    path = f"/tickets/{item['id']}/save-salesforce"
    def fail(*args):
        raise HTTPException(422, "Rejected")
    monkeypatch.setattr(salesforce, "save_case", fail)
    assert environment.post(path, json=body).status_code == 422
    assert main.load_ticket(item["id"]) == item
    calls = []
    monkeypatch.setattr(salesforce, "save_case", lambda *args: calls.append(args))
    saved = environment.post(path, json=body)
    assert saved.status_code == 200
    assert saved.json()["salesforce_status"] == "Pending"
    assert calls[0][-1] == "Checked the account"
    assert environment.post(path, json=body).status_code == 200
    assert calls[1][-1] == ""
    environment.cookies.clear()
    assert environment.post(path, json=body).status_code == 401
