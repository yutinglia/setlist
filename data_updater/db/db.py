from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL, IS_DEV

# Create async database engine
engine = create_async_engine(DATABASE_URL, echo=IS_DEV)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
