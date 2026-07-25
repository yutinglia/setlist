from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL, IS_DEV

# Pre-ping prevents stale pooled connections from causing the first request or
# updater transaction after a database restart to fail.
engine = create_async_engine(DATABASE_URL, echo=IS_DEV, pool_pre_ping=True)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
