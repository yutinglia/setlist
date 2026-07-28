"""Administrator browser-session endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from container import ApplicationContainer
from deps import (
    get_auth_service,
    get_container,
    optional_admin_session,
    require_admin_csrf,
)
from models.auth import AuthSessionResponse, LoginRequest
from services.auth import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    AdminSession,
    AuthService,
)
from utils.http_cache import prevent_private_response_caching, private_response_headers

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/session", response_model=AuthSessionResponse)
async def get_auth_session(
    response: Response,
    admin: AdminSession | None = Depends(optional_admin_session),
    container: ApplicationContainer = Depends(get_container),
) -> AuthSessionResponse:
    prevent_private_response_caching(response)
    return _session_response(
        admin,
        management_enabled=container.settings.auth.management_api_enabled,
    )


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    container: ApplicationContainer = Depends(get_container),
) -> AuthSessionResponse:
    prevent_private_response_caching(response)
    if not auth_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrator authentication is not configured",
            headers=private_response_headers(),
        )
    if not auth_service.verify_credentials(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers=private_response_headers({"WWW-Authenticate": "Session"}),
        )

    token, admin = auth_service.create_session()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=container.settings.auth.session_ttl_seconds,
        httponly=True,
        secure=container.settings.auth.cookie_secure,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
    return _session_response(
        admin,
        management_enabled=container.settings.auth.management_api_enabled,
    )


@router.post("/logout", response_model=AuthSessionResponse)
async def logout(
    response: Response,
    _: AdminSession = Depends(require_admin_csrf),
    container: ApplicationContainer = Depends(get_container),
) -> AuthSessionResponse:
    prevent_private_response_caching(response)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=container.settings.auth.cookie_secure,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
    return _session_response(
        None,
        management_enabled=container.settings.auth.management_api_enabled,
    )


def _session_response(
    admin: AdminSession | None,
    *,
    management_enabled: bool,
) -> AuthSessionResponse:
    if admin is None:
        return AuthSessionResponse(authenticated=False)
    return AuthSessionResponse(
        authenticated=True,
        role=admin.role,
        username=admin.username,
        csrf_token=admin.csrf_token,
        management_enabled=management_enabled,
    )
