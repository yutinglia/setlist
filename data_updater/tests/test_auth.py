"""Administrator authentication, session, and CSRF regressions."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import config
from deps import require_management_admin
from routers.v1.auth import router as auth_router
from services import auth


def _configure_admin(monkeypatch) -> None:
    password_hash = auth._password_hasher.hash("a-strong-test-password")
    monkeypatch.setattr(config, "ADMIN_USERNAME", "operator")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", password_hash)
    monkeypatch.setattr(config, "SESSION_SECRET", "s" * 48)
    monkeypatch.setattr(config, "AUTH_SESSION_TTL_SECONDS", 3600)
    monkeypatch.setattr(config, "AUTH_COOKIE_SECURE", False)
    monkeypatch.setattr(config, "MANAGEMENT_API_ENABLED", True)


def test_signed_session_rejects_tampering_and_password_rotation(monkeypatch):
    _configure_admin(monkeypatch)
    token, session = auth.create_admin_session(now=1_000)

    decoded = auth.decode_admin_session(token, now=1_001)
    assert decoded == session
    assert auth.decode_admin_session(f"{token}tampered", now=1_001) is None
    assert auth.decode_admin_session(token, now=session.expires_at) is None

    monkeypatch.setattr(
        config,
        "ADMIN_PASSWORD_HASH",
        auth._password_hasher.hash("a-different-test-password"),
    )
    assert auth.decode_admin_session(token, now=1_001) is None


def test_login_csrf_and_logout_flow(monkeypatch):
    _configure_admin(monkeypatch)
    app = FastAPI()
    app.include_router(auth_router, prefix="/v1")

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
        assert "HttpOnly" in login.headers["set-cookie"]

        missing_csrf = client.post("/v1/protected")
        assert missing_csrf.status_code == 403

        allowed = client.post(
            "/v1/protected",
            headers={"X-CSRF-Token": session["csrf_token"]},
        )
        assert allowed.status_code == 200

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


def test_auth_is_fail_closed_when_not_configured(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")
    monkeypatch.setattr(config, "SESSION_SECRET", "")
    app = FastAPI()
    app.include_router(auth_router, prefix="/v1")

    with TestClient(app) as client:
        response = client.post(
            "/v1/auth/login",
            json={"username": "admin", "password": "not-a-real-password"},
        )
        assert response.status_code == 503
        assert "vks_session" not in response.cookies
