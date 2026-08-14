"""Direct dependency-provider coverage for request and authorization edges."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Response

from container import ApplicationContainer
from deps import (
    get_auth_service,
    get_catalog_query_service,
    get_channel_creator,
    get_channel_ingest_query_service,
    get_container,
    get_data_updater,
    get_report_query_service,
    get_session,
    optional_admin_session,
    pagination_params,
    require_admin_csrf,
    require_admin_session,
    require_management_admin,
)
from services.auth import AdminSession


class _SessionContext:
    async def __aenter__(self):
        return "session"

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def _admin():
    return AdminSession(
        username="operator",
        role="admin",
        csrf_token="csrf",
        session_id="session",
        issued_at=1,
        expires_at=2,
    )


def test_container_and_simple_dependency_providers():
    container = object.__new__(ApplicationContainer)
    container.database = SimpleNamespace(session_factory=Mock())
    container.auth_service = "auth"
    container.catalog_queries = Mock(return_value="catalog")
    container.channel_ingest_queries = Mock(return_value="ingest")
    container.report_queries = Mock(return_value="report")
    container.channel_creator = Mock(return_value="creator")
    container.data_updater = Mock(return_value="updater")
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(container=container))
    )

    assert get_container(request) is container
    assert pagination_params(10, 4) == (10, 4)
    assert get_auth_service(container) == "auth"
    assert get_catalog_query_service("session", container) == "catalog"
    assert get_channel_ingest_query_service("session", container) == "ingest"
    assert get_report_query_service("session", container) == "report"
    assert get_channel_creator("session", container) == "creator"
    assert get_data_updater("session", container) == "updater"

    with pytest.raises(RuntimeError, match="not configured"):
        get_container(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())))


@pytest.mark.asyncio
async def test_session_provider_yields_from_container_factory():
    container = object.__new__(ApplicationContainer)
    container.database = SimpleNamespace(
        session_factory=Mock(return_value=_SessionContext())
    )
    sessions = get_session(container)

    assert await anext(sessions) == "session"
    with pytest.raises(StopAsyncIteration):
        await anext(sessions)


def test_optional_required_csrf_and_management_authorization():
    admin = _admin()
    request = SimpleNamespace(cookies={"vks_session": "signed"})
    response = Response()
    configured = SimpleNamespace(
        is_configured=Mock(return_value=True),
        decode_session=Mock(return_value=admin),
    )

    assert optional_admin_session(request, configured) is admin
    assert require_admin_session(request, response, configured) is admin
    assert require_admin_csrf(admin, "csrf") is admin
    assert (
        require_management_admin(
            admin,
            SimpleNamespace(
                settings=SimpleNamespace(
                    auth=SimpleNamespace(management_api_enabled=True)
                )
            ),
        )
        is admin
    )
    assert response.headers["cache-control"] == "no-store"

    unconfigured = SimpleNamespace(is_configured=Mock(return_value=False))
    with pytest.raises(HTTPException) as unavailable:
        require_admin_session(request, Response(), unconfigured)
    assert unavailable.value.status_code == 503

    missing = SimpleNamespace(
        is_configured=Mock(return_value=True),
        decode_session=Mock(return_value=None),
    )
    with pytest.raises(HTTPException) as unauthorized:
        require_admin_session(request, Response(), missing)
    assert unauthorized.value.status_code == 401
    assert unauthorized.value.headers["WWW-Authenticate"] == "Session"

    for token in (None, "wrong"):
        with pytest.raises(HTTPException) as forbidden:
            require_admin_csrf(admin, token)
        assert forbidden.value.status_code == 403

    with pytest.raises(HTTPException) as hidden:
        require_management_admin(
            admin,
            SimpleNamespace(
                settings=SimpleNamespace(
                    auth=SimpleNamespace(management_api_enabled=False)
                )
            ),
        )
    assert hidden.value.status_code == 404
