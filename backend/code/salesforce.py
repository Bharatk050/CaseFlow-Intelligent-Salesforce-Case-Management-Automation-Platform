"""Per-browser Salesforce OAuth (Authorization Code + PKCE) and Case API client."""
from __future__ import annotations
import base64, hashlib, json, os, re, secrets, sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "salesforce_sessions.sqlite3"
COOKIE_NAME = "rqc_salesforce_session"
STATE_COOKIE = "rqc_salesforce_oauth_state"
SESSION_SECONDS = 8 * 60 * 60
OAUTH_SECONDS = 10 * 60
SF_ID = re.compile(r"^[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?$")

@dataclass
class SalesforceSession:
    session_id: str; access_token: str; refresh_token: str | None; instance_url: str; user_id: str; queue_id: str | None; last_synced_at: str | None; last_sync_count: int | None
    display_name: str | None = None

def _setting(name: str, default: str = "") -> str: return os.getenv(name, default).strip()
def _hash(value: str) -> str: return hashlib.sha256(value.encode()).hexdigest()
def _now() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _fernet() -> Fernet:
    try: return Fernet(_setting("SALESFORCE_SESSION_ENCRYPTION_KEY").encode())
    except (ValueError, TypeError) as exc: raise HTTPException(503, "Salesforce secure session storage is not configured.") from exc
def _encrypt(value: str) -> bytes: return _fernet().encrypt(value.encode())
def _decrypt(value: bytes) -> str:
    try: return _fernet().decrypt(value).decode()
    except InvalidToken as exc: raise HTTPException(401, "Salesforce session is no longer valid. Connect again.") from exc
def _connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS oauth_pending (state_hash TEXT PRIMARY KEY, verifier BLOB NOT NULL, created_at TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS salesforce_sessions (session_hash TEXT PRIMARY KEY, access_token BLOB NOT NULL, refresh_token BLOB, instance_url TEXT NOT NULL, user_id TEXT NOT NULL, queue_id TEXT, last_synced_at TEXT, last_sync_count INTEGER)")
    if "expires_at" not in {row[1] for row in c.execute("PRAGMA table_info(salesforce_sessions)")}:
        c.execute("ALTER TABLE salesforce_sessions ADD COLUMN expires_at TEXT")
    if "display_name" not in {row[1] for row in c.execute("PRAGMA table_info(salesforce_sessions)")}:
        c.execute("ALTER TABLE salesforce_sessions ADD COLUMN display_name TEXT")
    c.commit()
    return c

def _expired(value: str | None) -> bool:
    try:
        return datetime.fromisoformat(value) <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True

def writeback_enabled() -> bool:
    return _setting("SALESFORCE_ALLOW_WRITEBACK", "false").lower() == "true"
def configured() -> bool: return bool(_setting("SALESFORCE_CLIENT_ID") and _setting("SALESFORCE_CLIENT_SECRET") and _setting("SALESFORCE_REDIRECT_URI") and _setting("SALESFORCE_SESSION_ENCRYPTION_KEY"))
def login_url() -> str:
    value = _setting("SALESFORCE_LOGIN_URL", "https://login.salesforce.com").rstrip("/")
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
        or parsed.path or parsed.query or parsed.fragment
        or not (host in {"login.salesforce.com", "test.salesforce.com"} or host.endswith(".my.salesforce.com"))):
        raise HTTPException(503, "Set SALESFORCE_LOGIN_URL to the HTTPS Salesforce production, sandbox, or My Domain login origin.")
    return value


def oauth_error_message(error: str, description: str = "") -> str:
    """Return actionable fixed text; never echo provider-controlled input."""
    combined = f"{error} {description}".lower()
    if "installed" in combined or error == "OAUTH_EC_APP_NOT_FOUND":
        return "Ask your Salesforce administrator to install or deploy this app in the target org and authorize your profile or permission set."
    if "blocked" in combined or "pre-authorized" in combined:
        return "Salesforce app access is blocked. Ask your administrator to review the app's permitted-user policy and your assigned access."
    if "redirect" in combined:
        return "The Salesforce app callback must exactly match the callback URL configured on this server. Ask your administrator to check it."
    if error == "access_denied":
        return "Salesforce authorization was declined. You can continue using Excel beta or connect again."
    return "Salesforce did not approve the connection. Ask your administrator to check app installation, permitted users, and the target org. Excel beta remains available."


def discard_authorization(state: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM oauth_pending WHERE state_hash=?", (_hash(state),))
def oauth_scopes() -> str: return _setting("SALESFORCE_OAUTH_SCOPES", "api id")

def authorization_url() -> str:
    if not configured(): raise HTTPException(503, "Salesforce OAuth is not configured. Ask an administrator to configure the server.")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with _connect() as c: c.execute("INSERT OR REPLACE INTO oauth_pending VALUES (?, ?, ?)", (_hash(state), _encrypt(verifier), _now()))
    params = {"response_type":"code", "client_id":_setting("SALESFORCE_CLIENT_ID"), "redirect_uri":_setting("SALESFORCE_REDIRECT_URI"), "state":state, "code_challenge":challenge, "code_challenge_method":"S256", "scope":oauth_scopes()}
    return f"{login_url()}/services/oauth2/authorize?{urlencode(params)}"

def _json_request(url: str, *, method="GET", token: str | None=None, body: dict | None=None, form: dict | None=None) -> dict:
    data = urlencode(form).encode() if form is not None else json.dumps(body).encode() if body is not None else None
    headers = {"Accept":"application/json", "Content-Type":"application/x-www-form-urlencoded" if form is not None else "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, data=data, headers=headers, method=method), timeout=20) as response:
            raw = response.read().decode(); return json.loads(raw) if raw else {}
    except HTTPError as exc:
        if exc.code == 401:
            raise HTTPException(401, "Your Salesforce session has expired. Connect again.") from exc
        if exc.code == 403:
            raise HTTPException(403, "Salesforce denied access. Ask your administrator to check your permissions.") from exc
        raise HTTPException(502, "Salesforce could not complete this request. Try again.") from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(502, "Salesforce could not complete this request. Try again.") from exc

def complete_authorization(code: str, state: str) -> str:
    with _connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT verifier, created_at FROM oauth_pending WHERE state_hash = ?", (_hash(state),)).fetchone(); c.execute("DELETE FROM oauth_pending WHERE state_hash = ?", (_hash(state),))
    if not row: raise HTTPException(400, "Invalid or expired Salesforce authorization request.")
    try:
        expired = _expired((datetime.fromisoformat(row["created_at"]) + timedelta(seconds=OAUTH_SECONDS)).isoformat())
    except (TypeError, ValueError):
        expired = True
    if expired: raise HTTPException(400, "Invalid or expired Salesforce authorization request.")
    payload = _json_request(f"{login_url()}/services/oauth2/token", method="POST", form={"grant_type":"authorization_code", "code":code, "client_id":_setting("SALESFORCE_CLIENT_ID"), "client_secret":_setting("SALESFORCE_CLIENT_SECRET"), "redirect_uri":_setting("SALESFORCE_REDIRECT_URI"), "code_verifier":_decrypt(row["verifier"])})
    if not payload.get("access_token") or not payload.get("instance_url") or not payload.get("id"): raise HTTPException(502, "Salesforce authorization did not complete. Try connecting again.")
    identity = _json_request(payload["id"], token=payload["access_token"])
    user_id = identity.get("user_id")
    name = identity.get("display_name") or " ".join(filter(None, [identity.get("first_name"), identity.get("last_name")])) or None
    if not user_id: raise HTTPException(502, "Salesforce authorization did not return a user identity.")
    session_id = secrets.token_urlsafe(32)
    with _connect() as c: c.execute("INSERT INTO salesforce_sessions (session_hash,access_token,refresh_token,instance_url,user_id,expires_at,display_name) VALUES (?,?,?,?,?,?,?)", (_hash(session_id),_encrypt(payload["access_token"]),_encrypt(payload["refresh_token"]) if payload.get("refresh_token") else None,payload["instance_url"],user_id,(datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)).isoformat(),name))
    return session_id

def _session(session_id: str | None) -> SalesforceSession:
    if not session_id: raise HTTPException(401, "Connect Salesforce before continuing.")
    with _connect() as c: row = c.execute("SELECT * FROM salesforce_sessions WHERE session_hash = ?", (_hash(session_id),)).fetchone()
    if not row: raise HTTPException(401, "Salesforce session has expired. Connect again.")
    if _expired(row["expires_at"]):
        disconnect(session_id)
        raise HTTPException(401, "Salesforce session has expired. Connect again.")
    return SalesforceSession(session_id,_decrypt(row["access_token"]),_decrypt(row["refresh_token"]) if row["refresh_token"] else None,row["instance_url"],row["user_id"],row["queue_id"],row["last_synced_at"],row["last_sync_count"],row["display_name"])

def available_queues(session: SalesforceSession) -> list[dict]:
    payload = _json_request(f"{session.instance_url.rstrip('/')}/services/data/v60.0/query?{urlencode({'q': "SELECT Id, Name FROM Group WHERE Type = 'Queue' ORDER BY Name"})}", token=session.access_token)
    return [{"id": item["Id"], "name": item["Name"]} for item in payload.get("records", [])]
def status(session_id: str | None) -> dict[str, Any]:
    if not session_id: return {"configured":configured(),"connected":False,"display_name":None,"queues":[],"selected_queue_id":None,"last_synced_at":None,"last_sync_count":None,"can_assign":False}
    s = _session(session_id)
    describe = _json_request(f"{s.instance_url.rstrip('/')}/services/data/v60.0/sobjects/Case/describe", token=s.access_token)
    can_assign = writeback_enabled() and any(field.get("name") == "OwnerId" and field.get("updateable") for field in describe.get("fields", []))
    return {"configured":configured(),"connected":True,"display_name":display_name(s),"queues":[],"selected_queue_id":s.queue_id,"last_synced_at":s.last_synced_at,"last_sync_count":s.last_sync_count,"can_assign":can_assign}
def _queue(queue_id: str) -> str:
    if not SF_ID.fullmatch(queue_id): raise HTTPException(400,"Choose a valid Salesforce queue.")
    return queue_id
def sync_cases(session_id: str | None, queue_id: str) -> list[dict]:
    s, queue_id = _session(session_id), _queue(queue_id)
    query = "SELECT Id, CaseNumber, Subject, Description, Status, Priority, CaseReason, Type, OwnerId, CreatedDate, LastModifiedDate FROM Case WHERE OwnerId = '" + queue_id + "' ORDER BY CreatedDate DESC"
    url = f"{s.instance_url.rstrip('/')}/services/data/v60.0/query?{urlencode({'q':query})}"; records=[]
    while url:
        payload=_json_request(url,token=s.access_token); records.extend(payload.get("records",[])); next_path=payload.get("nextRecordsUrl"); url=f"{s.instance_url.rstrip('/')}{next_path}" if next_path else ""
    with _connect() as c: c.execute("UPDATE salesforce_sessions SET queue_id=?,last_synced_at=?,last_sync_count=? WHERE session_hash=?",(queue_id,_now(),len(records),_hash(session_id)))
    return records
def assign_to_me(session_id: str | None, case_id: str) -> str:
    if not writeback_enabled(): raise HTTPException(403, "Salesforce writeback is disabled.")
    s=_session(session_id)
    if not SF_ID.fullmatch(case_id): raise HTTPException(400,"Invalid Salesforce Case.")
    _json_request(f"{s.instance_url.rstrip('/')}/services/data/v60.0/sobjects/Case/{case_id}",method="PATCH",token=s.access_token,body={"OwnerId":s.user_id})
    return s.user_id

def accessible_case_ids(session: SalesforceSession, case_ids: list[str]) -> set[str]:
    """Recheck current record visibility with this user's Salesforce token."""
    permitted = set()
    valid_ids = [value for value in case_ids if SF_ID.fullmatch(value)]
    for start in range(0, len(valid_ids), 100):
        ids = ",".join("'" + value + "'" for value in valid_ids[start:start + 100])
        query = f"SELECT Id FROM Case WHERE Id IN ({ids})"
        payload = _json_request(f"{session.instance_url.rstrip('/')}/services/data/v60.0/query?{urlencode({'q': query})}", token=session.access_token)
        permitted.update(record["Id"] for record in payload.get("records", []))
    return permitted
def disconnect(session_id: str | None) -> None:
    if session_id:
        with _connect() as c: c.execute("DELETE FROM salesforce_sessions WHERE session_hash=?",(_hash(session_id),))


ROSTER_VIEW_LABEL = "Roster support Queue"
CASE_FIELDS = "Id, CaseNumber, Subject, Description, Status, Priority, CaseReason, Type, OwnerId, CreatedDate, LastModifiedDate"


def display_name(session: SalesforceSession) -> str:
    if session.display_name:
        return session.display_name
    name = None
    if SF_ID.fullmatch(session.user_id):
        try:
            user = _json_request(f"{session.instance_url.rstrip('/')}/services/data/v60.0/sobjects/User/{session.user_id}?fields=Name", token=session.access_token)
            name = user.get("Name")
        except HTTPException:
            pass  # A missing display name must not block the workspace.
    session.display_name = name or "Salesforce user"
    with _connect() as connection:
        connection.execute("UPDATE salesforce_sessions SET display_name=? WHERE session_hash=?", (session.display_name, _hash(session.session_id)))
    return session.display_name


def _api_path(session: SalesforceSession, path: str) -> str:
    # Pagination URLs must remain on this org; never send its token elsewhere.
    if not path.startswith("/services/data/") or urlparse(path).netloc or ".." in path:
        raise HTTPException(502, "Salesforce returned an invalid pagination address.")
    return session.instance_url.rstrip('/') + path


def roster_support_cases(session: SalesforceSession) -> tuple[dict | None, list[dict]]:
    path = "/services/data/v60.0/sobjects/Case/listviews"
    matches = {}
    visited = set()
    while path:
        if path in visited:
            raise HTTPException(502, "Salesforce list view pagination did not advance. Retry.")
        visited.add(path)
        payload = _json_request(_api_path(session, path), token=session.access_token)
        for view in payload.get("listviews", []):
            if str(view.get("label", "")).strip().casefold() == ROSTER_VIEW_LABEL.casefold():
                matches[view["id"]] = {"id": view["id"], "label": view["label"]}
        path = payload.get("nextRecordsUrl")
    if not matches:
        return None, []
    if len(matches) != 1:
        raise HTTPException(409, "More than one Case list view is named Roster support Queue. Ask your Salesforce administrator to give them distinct names.")
    view = next(iter(matches.values()))
    if not SF_ID.fullmatch(view["id"]):
        raise HTTPException(502, "Salesforce returned an invalid list view ID.")
    ids, seen = [], set()
    offset, limit = 0, 2000
    while True:
        path = f"/services/data/v60.0/sobjects/Case/listviews/{view['id']}/results?{urlencode({'limit': limit, 'offset': offset})}"
        page = _json_request(_api_path(session, path), token=session.access_token)
        records = page.get("records", [])
        for record in records:
            case_id = record.get("id") or next((field.get("value") for field in record.get("columns", []) if field.get("fieldNameOrPath") == "Id"), None)
            if not isinstance(case_id, str) or not SF_ID.fullmatch(case_id):
                raise HTTPException(502, "Salesforce list view did not return valid Case IDs.")
            if case_id not in seen:
                seen.add(case_id)
                ids.append(case_id)
        if page.get("done") is True or not records or ("done" not in page and len(records) < limit):
            break
        if len(ids) <= offset:
            raise HTTPException(502, "Salesforce case pagination did not advance. Retry.")
        offset += len(records)
    # Fetch full workspace fields without changing the saved view's criteria.
    cases = {}
    for start in range(0, len(ids), 100):
        selected = ",".join("'" + value + "'" for value in ids[start:start + 100])
        query = f"SELECT {CASE_FIELDS} FROM Case WHERE Id IN ({selected})"
        path = "/services/data/v60.0/query?" + urlencode({"q": query})
        visited = set()
        while path:
            if path in visited:
                raise HTTPException(502, "Salesforce case pagination did not advance. Retry.")
            visited.add(path)
            payload = _json_request(_api_path(session, path), token=session.access_token)
            cases.update({case["Id"]: case for case in payload.get("records", [])})
            path = payload.get("nextRecordsUrl")
    return view, [cases[case_id] for case_id in ids if case_id in cases]
