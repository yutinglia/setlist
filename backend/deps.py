"""Shared FastAPI dependencies (DB session, pagination)."""

import hmac
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from container import ApplicationContainer
from services.auth import (
    SESSION_COOKIE_NAME,
    AdminSession,
    AuthService,
)
from services.channel_creator import ChannelCreator
from services.data_updater import DataUpdater
from services.queries import (
    CatalogQueryService,
    ChannelIngestQueryService,
    ReportQueryService,
)
from utils.http_cache import (
    prevent_private_response_caching,
    private_response_headers,
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_OFFSET = 1_000_000


def get_container(request: Request) -> ApplicationContainer:
    """Resolve the app-scoped composition root."""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, ApplicationContainer):
        raise RuntimeError("ApplicationContainer is not configured")
    return container


async def get_session(
    container: ApplicationContainer = Depends(get_container),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session (no auto-commit)."""
    async with container.session_factory() as session:
        yield session


def pagination_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
) -> tuple[int, int]:
    """Common ``limit`` / ``offset`` query params for list endpoints."""
    return limit, offset


def get_auth_service(
    container: ApplicationContainer = Depends(get_container),
) -> AuthService:
    return container.auth_service


def optional_admin_session(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AdminSession | None:
    return auth_service.decode_session(request.cookies.get(SESSION_COOKIE_NAME))


def require_admin_session(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> AdminSession:
    """Require a valid administrator session for private read endpoints."""
    prevent_private_response_caching(response)
    if not auth_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator authentication is not configured",
            headers=private_response_headers(),
        )
    session = auth_service.decode_session(request.cookies.get(SESSION_COOKIE_NAME))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator sign-in required",
            headers=private_response_headers({"WWW-Authenticate": "Session"}),
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
            headers=private_response_headers(),
        )
    return admin


def require_management_admin(
    admin: AdminSession = Depends(require_admin_csrf),
    container: ApplicationContainer = Depends(get_container),
) -> AdminSession:
    """Require admin authorization and the management kill switch."""
    if not container.settings.auth.management_api_enabled:
        raise HTTPException(
            status_code=404,
            detail="Not found",
            headers=private_response_headers(),
        )
    return admin


def get_catalog_query_service(
    session: AsyncSession = Depends(get_session),
    container: ApplicationContainer = Depends(get_container),
) -> CatalogQueryService:
    return container.catalog_queries(session)


def get_channel_ingest_query_service(
    session: AsyncSession = Depends(get_session),
    container: ApplicationContainer = Depends(get_container),
) -> ChannelIngestQueryService:
    return container.channel_ingest_queries(session)


def get_report_query_service(
    session: AsyncSession = Depends(get_session),
    container: ApplicationContainer = Depends(get_container),
) -> ReportQueryService:
    return container.report_queries(session)


def get_channel_creator(
    session: AsyncSession = Depends(get_session),
    container: ApplicationContainer = Depends(get_container),
) -> ChannelCreator:
    return container.channel_creator(session)


def get_data_updater(
    session: AsyncSession = Depends(get_session),
    container: ApplicationContainer = Depends(get_container),
) -> DataUpdater:
    return container.data_updater(session)
