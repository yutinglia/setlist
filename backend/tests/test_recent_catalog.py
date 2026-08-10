"""PostgreSQL integration coverage for recent updates and channel search."""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.channel import YouTubeChannel
from models.song import Song
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://vks_db_user:vks_db_pwd@localhost:5432/vks_db",
    )


async def _db_available(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session():
    url = _database_url()
    if not await _db_available(url):
        pytest.skip("Postgres not available for repository integration tests")

    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as database_session:
        try:
            yield database_session
            await database_session.rollback()
        finally:
            await database_session.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_recent_catalog_limits_and_literal_channel_search(session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    first_channel_id = f"ch_recent_first_{suffix}"
    latest_channel_id = f"ch_recent_latest_{suffix}"
    video_id = f"vid_recent_{suffix}"
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)

    await channel_repo.create(
        YouTubeChannel(
            id=first_channel_id,
            name=f"Earlier Channel {suffix}",
            url=f"https://www.youtube.com/channel/{first_channel_id}",
        )
    )
    await channel_repo.create(
        YouTubeChannel(
            id=latest_channel_id,
            name=f"Latest %_{suffix}",
            url=f"https://www.youtube.com/channel/{latest_channel_id}",
        )
    )

    literal_matches = await channel_repo.get_all(limit=10, query=f"%_{suffix}")
    assert [item.id for item in literal_matches] == [latest_channel_id]
    assert await channel_repo.count_all(query=f"%_{suffix}") == 1
    assert (await channel_repo.get_all(query=latest_channel_id))[0].id == (
        latest_channel_id
    )
    assert (await channel_repo.get_recent(limit=1))[0].id == latest_channel_id

    await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Recent Karaoke",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=latest_channel_id,
            type="karaoke",
        )
    )
    await song_repo.replace_for_video(
        video_id,
        [
            Song(title="Earlier Song", video_id=video_id, timestamp="1:00"),
            Song(title="Latest Song", video_id=video_id, timestamp="5:00"),
        ],
    )

    recent_songs = await song_repo.get_recent(limit=1)
    assert len(recent_songs) == 1
    assert recent_songs[0].title == "Latest Song"
    assert recent_songs[0].channel_id == latest_channel_id
    assert recent_songs[0].updated_at is not None
    assert recent_songs[0].video_url.endswith("&t=300s")

    await session.rollback()
