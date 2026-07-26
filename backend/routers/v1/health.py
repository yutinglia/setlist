import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from db import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(response: Response):
    """Liveness/readiness: always pings Postgres with SELECT 1."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check database ping failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "version": "v1", "database": "unavailable"}

    return {"status": "healthy", "version": "v1", "database": "ok"}
