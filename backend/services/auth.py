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
from config import AuthSettings

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


class AuthService:
    """Signed-session service with immutable injected configuration."""

    def __init__(
        self,
        settings: AuthSettings,
        *,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self.settings = settings
        self.password_hasher = password_hasher or PasswordHasher()

    def is_configured(self) -> bool:
        return bool(
            self.settings.password_hash
            and self.settings.session_secret
            and len(self.settings.session_secret.encode("utf-8")) >= 32
        )

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify both fields without revealing whether the username exists."""
        if not self.is_configured():
            return False

        try:
            password_valid = self.password_hasher.verify(
                self.settings.password_hash,
                password,
            )
        except (InvalidHashError, VerificationError):
            password_valid = False

        username_valid = hmac.compare_digest(
            username.encode("utf-8"),
            self.settings.username.encode("utf-8"),
        )
        return password_valid and username_valid

    def create_session(
        self,
        *,
        now: int | None = None,
    ) -> tuple[str, AdminSession]:
        if not self.is_configured():
            raise RuntimeError("Administrator authentication is not configured")

        issued_at = int(time.time() if now is None else now)
        session = AdminSession(
            username=self.settings.username,
            role=SESSION_ROLE,
            csrf_token=secrets.token_urlsafe(32),
            session_id=secrets.token_urlsafe(24),
            issued_at=issued_at,
            expires_at=issued_at + self.settings.session_ttl_seconds,
        )
        payload = {
            "sub": session.username,
            "role": session.role,
            "csrf": session.csrf_token,
            "sid": session.session_id,
            "iat": session.issued_at,
            "exp": session.expires_at,
            "cv": self._credential_version(),
        }
        encoded = _base64url_encode(
            json.dumps(
                payload,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        signature = self._sign(encoded)
        return f"{encoded}.{signature}", session

    def decode_session(
        self,
        token: str | None,
        *,
        now: int | None = None,
    ) -> AdminSession | None:
        if not token or not self.is_configured():
            return None

        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = self._sign(encoded)
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            payload = json.loads(_base64url_decode(encoded))
            current_time = int(time.time() if now is None else now)
            if (
                payload.get("role") != SESSION_ROLE
                or payload.get("sub") != self.settings.username
                or payload.get("cv") != self._credential_version()
                or not isinstance(payload.get("iat"), int)
                or not isinstance(payload.get("exp"), int)
                or payload["iat"] > current_time + 60
                or payload["exp"] <= current_time
                or payload["exp"] - payload["iat"] > self.settings.session_ttl_seconds
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
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return None

    def _credential_version(self) -> str:
        return hashlib.sha256(self.settings.password_hash.encode("utf-8")).hexdigest()[
            :16
        ]

    def _sign(self, encoded_payload: str) -> str:
        digest = hmac.new(
            self.settings.session_secret.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return _base64url_encode(digest)


def _legacy_service() -> AuthService:
    """Compatibility bridge for command helpers importing module functions."""

    return AuthService(config.get_settings().auth, password_hasher=_password_hasher)


def is_auth_configured() -> bool:
    return _legacy_service().is_configured()


def verify_admin_credentials(username: str, password: str) -> bool:
    return _legacy_service().verify_credentials(username, password)


def create_admin_session(*, now: int | None = None) -> tuple[str, AdminSession]:
    return _legacy_service().create_session(now=now)


def decode_admin_session(
    token: str | None,
    *,
    now: int | None = None,
) -> AdminSession | None:
    return _legacy_service().decode_session(token, now=now)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
