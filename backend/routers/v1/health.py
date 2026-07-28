import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from container import ApplicationContainer
from deps import get_container, get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(
    response: Response,
    session: AsyncSession = Depends(get_session),
    container: ApplicationContainer = Depends(get_container),
):
    """Liveness/readiness: always pings Postgres with SELECT 1."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check database ping failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "version": "v1",
            "database": "unavailable",
            "cache": await container.cache.status(),
        }

    return {
        "status": "healthy",
        "version": "v1",
        "database": "ok",
        "cache": await container.cache.status(),
    }
