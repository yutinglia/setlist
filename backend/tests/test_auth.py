"""Administrator authentication, session, and CSRF regressions."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import config
from config import AuthSettings
from container import ApplicationContainer
from deps import get_channel_ingest_query_service, require_management_admin
from main import create_app
from services.auth import AuthService, _password_hasher


def _auth_settings(*, configured: bool = True) -> AuthSettings:
    return AuthSettings(
        username="operator",
        password_hash=(
            _password_hasher.hash("a-strong-test-password") if configured else ""
        ),
        session_secret="s" * 48 if configured else "",
        session_ttl_seconds=3600,
        cookie_secure=False,
        management_api_enabled=True,
    )


def _app(settings: AuthSettings) -> FastAPI:
    app_settings = config.get_settings()
    app_settings = replace(
        app_settings,
        auth=settings,
        rate_limit=replace(app_settings.rate_limit, enabled=False),
    )
    return create_app(ApplicationContainer.build(app_settings))


def test_signed_session_rejects_tampering_and_password_rotation():
    auth_service = AuthService(_auth_settings())
    token, session = auth_service.create_session(now=1_000)

    decoded = auth_service.decode_session(token, now=1_001)
    assert decoded == session
    assert auth_service.decode_session(f"{token}tampered", now=1_001) is None
    assert auth_service.decode_session(token, now=session.expires_at) is None

    rotated = AuthService(
        replace(
            _auth_settings(),
            password_hash=_password_hasher.hash("a-different-test-password"),
        )
    )
    assert rotated.decode_session(token, now=1_001) is None


def test_login_csrf_and_logout_flow():
    app = _app(_auth_settings())

    @app.post("/v1/protected")
    async def protected(_=Depends(require_management_admin)):
        return {"ok": True}

    with TestClient(app) as client:
        wrong = client.post(
            "/v1/auth/login",
            json={"username": "operator", "password": "wrong-password"},
        )
        assert wrong.status_code == 401
        assert "vks_session" not in wrong.cookies
        assert wrong.headers["cache-control"] == "no-store"
        assert wrong.headers["vary"] == "Cookie"

        login = client.post(
            "/v1/auth/login",
            json={
                "username": "operator",
                "password": "a-strong-test-password",
            },
        )
        assert login.status_code == 200
        session = login.json()
        assert session["authenticated"] is True
        assert session["role"] == "admin"
        assert session["csrf_token"]
        assert login.headers["cache-control"] == "no-store"
        assert login.headers["vary"] == "Cookie"
        assert "HttpOnly" in login.headers["set-cookie"]

        missing_csrf = client.post("/v1/protected")
        assert missing_csrf.status_code == 403
        assert missing_csrf.headers["cache-control"] == "no-store"

        allowed = client.post(
            "/v1/protected",
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        assert allowed.status_code == 200
        assert allowed.headers["cache-control"] == "no-store"
        assert allowed.headers["vary"] == "Cookie"

        logout = client.post(
            "/v1/auth/logout",
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        assert logout.status_code == 200
        assert logout.json()["authenticated"] is False

        denied = client.post(
            "/v1/protected",
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        assert denied.status_code == 401
        assert denied.headers["cache-control"] == "no-store"


def test_auth_is_fail_closed_when_not_configured():
    app = _app(_auth_settings(configured=False))

    with TestClient(app) as client:
        response = client.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "not-a-real-password"},
        )
        assert response.status_code == 503
        assert "vks_session" not in response.cookies
        assert response.headers["cache-control"] == "no-store"


def test_channel_ingest_queue_is_private_but_does_not_require_csrf():
    app = _app(_auth_settings())
    queries = SimpleNamespace(
        list_pending=AsyncMock(
            return_value={
                "items": [],
                "total": 0,
                "limit": 20,
                "offset": 0,
            }
        )
    )
    app.dependency_overrides[get_channel_ingest_query_service] = lambda: queries

    with TestClient(app) as client:
        denied = client.get("/v1/channels/ingest-queue")
        assert denied.status_code == 401
        assert denied.headers["cache-control"] == "no-store"

        login = client.post(
            "/v1/auth/login",
            json={
                "username": "operator",
                "password": "a-strong-test-password",
            },
        )
        assert login.status_code == 200

        allowed = client.get("/v1/channels/ingest-queue")
        assert allowed.status_code == 200
        assert allowed.json() == {
            "items": [],
            "total": 0,
            "limit": 20,
            "offset": 0,
        }
        assert allowed.headers["cache-control"] == "no-store"
        assert allowed.headers["vary"] == "Cookie"
        queries.list_pending.assert_awaited_once_with(limit=20, offset=0)
