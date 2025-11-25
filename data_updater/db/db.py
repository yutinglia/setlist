from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL, IS_DEV

# Create async database engine
engine = create_async_engine(DATABASE_URL, echo=IS_DEV)
async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
