"""Database resource factory used by the application composition root."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@dataclass(frozen=True)
class DatabaseResources:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def create_database_resources(
    database_url: str,
    *,
    echo: bool = False,
) -> DatabaseResources:
    """Create one engine/pool and its request-scoped session factory."""

    # Pre-ping prevents stale pooled connections from causing the first request
    # or updater transaction after a database restart to fail.
    engine = create_async_engine(database_url, echo=echo, pool_pre_ping=True)
    return DatabaseResources(
        engine=engine,
        session_factory=async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )
