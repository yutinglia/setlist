"""Shared FastAPI dependencies (DB session, pagination)."""

import hmac
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

import config
from db import async_session_factory
from services.auth import (
    SESSION_COOKIE_NAME,
    AdminSession,
    decode_admin_session,
    is_auth_configured,
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_OFFSET = 1_000_000


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session (no auto-commit)."""
    async with async_session_factory() as session:
        yield session


def pagination_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
) -> tuple[int, int]:
    """Common ``limit`` / ``offset`` query params for list endpoints."""
    return limit, offset


def optional_admin_session(request: Request) -> AdminSession | None:
    return decode_admin_session(request.cookies.get(SESSION_COOKIE_NAME))


def require_admin_session(request: Request) -> AdminSession:
    """Require a valid administrator session for private read endpoints."""
    if not is_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator authentication is not configured",
        )
    session = optional_admin_session(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator sign-in required",
            headers={"WWW-Authenticate": "Session"},
        )
    return session


def require_admin_csrf(
    admin: AdminSession = Depends(require_admin_session),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> AdminSession:
    """Require the signed session's anti-CSRF token for state changes."""
    if csrf_token is None or not hmac.compare_digest(
        csrf_token.encode("utf-8"),
        admin.csrf_token.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )
    return admin


def require_management_admin(
    admin: AdminSession = Depends(require_admin_csrf),
) -> AdminSession:
    """Require admin authorization and the management kill switch."""
    if not config.MANAGEMENT_API_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    return admin
