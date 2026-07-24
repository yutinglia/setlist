"""Integration tests for repository write path.

Requires a reachable Postgres (Compose/Dev Container defaults).
Skipped automatically when the database is unavailable.
"""

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
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
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
    async with factory() as sess:
        try:
            yield sess
            await sess.rollback()
        finally:
            await sess.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_channel_video_and_replace_songs(session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_test_{suffix}"
    video_id = f"vid_test_{suffix}"

    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)

    channel = await channel_repo.upsert(
        YouTubeChannel(
            id=channel_id,
            name="Test Channel",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    assert channel.id == channel_id

    video = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke Test",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
        )
    )
    assert video.id == video_id

    songs = await song_repo.replace_for_video(
        video_id,
        [
            Song(title="Song A", video_id=video_id, timestamp="0:10"),
            Song(title="Song B", video_id=video_id, timestamp="1:20"),
        ],
    )
    assert len(songs) == 2
    assert all(s.id is not None for s in songs)

    replaced = await song_repo.replace_for_video(
        video_id,
        [Song(title="Only Song", video_id=video_id, timestamp="2:00")],
    )
    assert len(replaced) == 1
    assert replaced[0].title == "Only Song"

    fetched = await song_repo.get_by_video_id(video_id)
    assert len(fetched) == 1
    assert fetched[0].title == "Only Song"

    # Leave DB clean even if outer rollback is skipped somehow
    await song_repo.replace_for_video(video_id, [])
    await session.rollback()
