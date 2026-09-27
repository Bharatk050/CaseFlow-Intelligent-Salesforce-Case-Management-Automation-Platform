import base64
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import salesforce


@pytest.fixture
def salesforce_config(monkeypatch):
    monkeypatch.setenv("SALESFORCE_LOGIN_URL", "https://login.salesforce.com")
    monkeypatch.setenv("SALESFORCE_CLIENT_ID", "consumer-key")
    monkeypatch.setenv("SALESFORCE_CLIENT_SECRET", "consumer-secret")
    monkeypatch.setenv("SALESFORCE_REDIRECT_URI", "http://127.0.0.1:8012/auth/salesforce/callback")
    monkeypatch.setenv("SALESFORCE_SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("SALESFORCE_OAUTH_SCOPES", raising=False)


def test_authorization_url_uses_state_pkce_and_minimum_scopes(salesforce_config, monkeypatch):
    class InMemoryConnection:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def execute(self, *_args): return self
    monkeypatch.setattr(salesforce, "_connect", lambda: InMemoryConnection())
    url = salesforce.authorization_url()
    query = parse_qs(urlparse(url).query)
    assert url.startswith("https://login.salesforce.com/services/oauth2/authorize")
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert set(query["scope"][0].split()) == {"api", "id"}
    assert "state" in query and "code_challenge" in query


def test_invalid_queue_id_is_rejected():
    with pytest.raises(HTTPException) as exc:
        salesforce._queue("not-a-salesforce-id")
    assert exc.value.status_code == 400


def test_disconnected_status_does_not_expose_session_data(monkeypatch):
    monkeypatch.delenv("SALESFORCE_CLIENT_ID", raising=False)
    result = salesforce.status(None)
    assert result["connected"] is False
    assert "access_token" not in result
