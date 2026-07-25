"""Integration tests for repository write path.

Requires a reachable Postgres (Compose/Dev Container defaults).
Skipped automatically when the database is unavailable.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.channel import YouTubeChannel
from models.song import Song
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.report_repository import ReportRepository
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
    report_repo = ReportRepository(session)
    before = await report_repo.get_summary()

    channel = await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Test Channel",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    assert channel is not None
    assert channel.id == channel_id
    duplicate = await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Duplicate",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    assert duplicate is None

    video = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke Test",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={"duration": 3600, "live_status": "was_live"},
        )
    )
    assert video.id == video_id

    # A later flat channel-tab scrape must update keys it knows without
    # destroying richer metadata used by classification.
    refreshed = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Karaoke Test (updated)",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={"title": "Karaoke Test (updated)"},
        )
    )
    assert refreshed.raw_data == {
        "duration": 3600,
        "live_status": "was_live",
        "title": "Karaoke Test (updated)",
    }
    refreshed.comments_raw_data = {"comments": [{"text": "one"}, {"text": "two"}]}
    refreshed.last_analyzed_at = datetime.now(UTC).replace(tzinfo=None)
    refreshed.has_song_list_comment = True
    refreshed.analysis_status = "done"
    await video_repo.update_analysis(refreshed)

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

    await song_repo.replace_for_video(
        video_id,
        [
            Song(
                title="100% Love",
                video_id=video_id,
                timestamp="3:00",
                analyzed_by_llm=True,
            ),
            Song(title="1000 Love", video_id=video_id, timestamp="4:00"),
            Song(title="Under_score", video_id=video_id, timestamp="5:00"),
        ],
    )
    percent_hits, percent_total = await song_repo.search_by_title(
        "%", limit=20, offset=0
    )
    assert percent_total == 1
    assert [song.title for song in percent_hits] == ["100% Love"]
    underscore_hits, underscore_total = await song_repo.search_by_title(
        "_", limit=20, offset=0
    )
    assert underscore_total == 1
    assert [song.title for song in underscore_hits] == ["Under_score"]

    after = await report_repo.get_summary()
    assert after.channels == before.channels + 1
    assert after.backfill.done == before.backfill.done + 1
    assert after.videos.total == before.videos.total + 1
    assert after.videos.karaoke == before.videos.karaoke + 1
    assert after.analysis.attempted == before.analysis.attempted + 1
    assert after.analysis.with_setlist == before.analysis.with_setlist + 1
    assert (
        after.analysis.videos_with_comments == before.analysis.videos_with_comments + 1
    )
    assert after.analysis.comments == before.analysis.comments + 2
    assert after.analysis.status.done == before.analysis.status.done + 1
    assert after.songs.total == before.songs.total + 3
    assert after.songs.analyzed_by_llm == before.songs.analyzed_by_llm + 1
    assert after.videos.latest_discovered_at is not None
    assert after.analysis.latest_analyzed_at is not None

    # Leave DB clean even if outer rollback is skipped somehow
    await song_repo.replace_for_video(video_id, [])
    await session.rollback()
