"""Administrator browser-session endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

import config
from deps import optional_admin_session, require_admin_csrf
from models.auth import AuthSessionResponse, LoginRequest
from services.auth import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    AdminSession,
    create_admin_session,
    is_auth_configured,
    verify_admin_credentials,
)
from utils.http_cache import prevent_private_response_caching, private_response_headers

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/session", response_model=AuthSessionResponse)
async def get_auth_session(
    response: Response,
    admin: AdminSession | None = Depends(optional_admin_session),
) -> AuthSessionResponse:
    prevent_private_response_caching(response)
    return _session_response(admin)


@router.post("/login", response_model=AuthSessionResponse)
async def login(body: LoginRequest, response: Response) -> AuthSessionResponse:
    prevent_private_response_caching(response)
    if not is_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator authentication is not configured",
            headers=private_response_headers(),
        )
    if not verify_admin_credentials(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers=private_response_headers({"WWW-Authenticate": "Session"}),
        )

    token, admin = create_admin_session()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=config.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.AUTH_COOKIE_SECURE,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
    return _session_response(admin)


@router.post("/logout", response_model=AuthSessionResponse)
async def logout(
    response: Response,
    _: AdminSession = Depends(require_admin_csrf),
) -> AuthSessionResponse:
    prevent_private_response_caching(response)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=config.AUTH_COOKIE_SECURE,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
    return _session_response(None)


def _session_response(admin: AdminSession | None) -> AuthSessionResponse:
    if admin is None:
        return AuthSessionResponse(authenticated=False)
    return AuthSessionResponse(
        authenticated=True,
        role=admin.role,
        username=admin.username,
        csrf_token=admin.csrf_token,
        management_enabled=config.MANAGEMENT_API_ENABLED,
    )
