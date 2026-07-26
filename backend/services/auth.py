"""Single-admin password verification and signed browser sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

import config

SESSION_COOKIE_NAME = "vks_session"
SESSION_COOKIE_PATH = "/v1"
SESSION_ROLE: Literal["admin"] = "admin"

_password_hasher = PasswordHasher()


@dataclass(frozen=True)
class AdminSession:
    username: str
    role: Literal["admin"]
    csrf_token: str
    session_id: str
    issued_at: int
    expires_at: int


def is_auth_configured() -> bool:
    return bool(
        config.ADMIN_PASSWORD_HASH
        and config.SESSION_SECRET
        and len(config.SESSION_SECRET.encode("utf-8")) >= 32
    )


def verify_admin_credentials(username: str, password: str) -> bool:
    """Verify both fields without revealing whether the username exists."""
    if not is_auth_configured():
        return False

    try:
        password_valid = _password_hasher.verify(
            config.ADMIN_PASSWORD_HASH,
            password,
        )
    except (InvalidHashError, VerificationError):
        password_valid = False

    username_valid = hmac.compare_digest(
        username.encode("utf-8"),
        config.ADMIN_USERNAME.encode("utf-8"),
    )
    return password_valid and username_valid


def create_admin_session(*, now: int | None = None) -> tuple[str, AdminSession]:
    if not is_auth_configured():
        raise RuntimeError("Administrator authentication is not configured")

    issued_at = int(time.time() if now is None else now)
    session = AdminSession(
        username=config.ADMIN_USERNAME,
        role=SESSION_ROLE,
        csrf_token=secrets.token_urlsafe(32),
        session_id=secrets.token_urlsafe(24),
        issued_at=issued_at,
        expires_at=issued_at + config.AUTH_SESSION_TTL_SECONDS,
    )
    payload = {
        "sub": session.username,
        "role": session.role,
        "csrf": session.csrf_token,
        "sid": session.session_id,
        "iat": session.issued_at,
        "exp": session.expires_at,
        "cv": _credential_version(),
    }
    encoded = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _sign(encoded)
    return f"{encoded}.{signature}", session


def decode_admin_session(
    token: str | None,
    *,
    now: int | None = None,
) -> AdminSession | None:
    if not token or not is_auth_configured():
        return None

    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = _sign(encoded)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(_base64url_decode(encoded))
        current_time = int(time.time() if now is None else now)
        if (
            payload.get("role") != SESSION_ROLE
            or payload.get("sub") != config.ADMIN_USERNAME
            or payload.get("cv") != _credential_version()
            or not isinstance(payload.get("iat"), int)
            or not isinstance(payload.get("exp"), int)
            or payload["iat"] > current_time + 60
            or payload["exp"] <= current_time
            or payload["exp"] - payload["iat"] > config.AUTH_SESSION_TTL_SECONDS
            or not isinstance(payload.get("csrf"), str)
            or not isinstance(payload.get("sid"), str)
        ):
            return None
        return AdminSession(
            username=payload["sub"],
            role=SESSION_ROLE,
            csrf_token=payload["csrf"],
            session_id=payload["sid"],
            issued_at=payload["iat"],
            expires_at=payload["exp"],
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _credential_version() -> str:
    return hashlib.sha256(config.ADMIN_PASSWORD_HASH.encode("utf-8")).hexdigest()[:16]


def _sign(encoded_payload: str) -> str:
    digest = hmac.new(
        config.SESSION_SECRET.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
