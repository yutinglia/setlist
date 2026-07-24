"""Shared FastAPI dependencies (DB session, pagination)."""

from collections.abc import AsyncGenerator

from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import async_session_factory

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session (no auto-commit)."""
    async with async_session_factory() as session:
        yield session


def pagination_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> tuple[int, int]:
    """Common ``limit`` / ``offset`` query params for list endpoints."""
    return limit, offset
