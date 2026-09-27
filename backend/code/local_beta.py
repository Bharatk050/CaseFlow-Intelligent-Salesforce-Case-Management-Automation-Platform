"""Loopback-only browser sessions for Excel beta testing, separate from OAuth."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
import secrets

from fastapi import HTTPException, Request

try:
    from . import salesforce
except ImportError:
    import salesforce

COOKIE_NAME = "rqc_excel_beta_session"
SCOPE = "local-excel-beta"


@dataclass
class LocalSession:
    user_id: str
    instance_url: str = SCOPE


def require_loopback(request: Request) -> None:
    try:
        local = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local = False
    if not local:
        raise HTTPException(403, "Excel beta sessions are available only on this computer.")


def lookup(request: Request) -> LocalSession | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    require_loopback(request)
    with salesforce._connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS local_beta_sessions (session_hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL)")
        row = connection.execute("SELECT expires_at FROM local_beta_sessions WHERE session_hash=?", (salesforce._hash(token),)).fetchone()
    if not row or salesforce._expired(row["expires_at"]):
        return None
    return LocalSession("beta-" + salesforce._hash(token))


def create(request: Request) -> str:
    require_loopback(request)
    # Reuse this browser's session so refreshing cannot orphan its imports.
    if lookup(request):
        return request.cookies[COOKIE_NAME]
    token = secrets.token_urlsafe(32)
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=salesforce.SESSION_SECONDS)).isoformat()
    with salesforce._connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS local_beta_sessions (session_hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL)")
        connection.execute("INSERT INTO local_beta_sessions VALUES (?, ?)", (salesforce._hash(token), expiry))
    return token
