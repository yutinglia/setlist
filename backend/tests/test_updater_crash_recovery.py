"""PostgreSQL crash-recovery coverage for updater transaction boundaries."""

from __future__ import annotations

import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from db.models import Channels, Songs, Videos
from models.channel import YouTubeChannel
from models.song import Song
from models.video import YouTubeVideo
from repositories.channel_repository import ChannelRepository
from repositories.song_repository import SongRepository
from repositories.video_repository import VideoRepository
from services.data_updater import DataUpdater


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://vks_db_user:vks_db_pwd@localhost:5432/vks_db",
    )


async def _database() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("Postgres not available for updater crash-recovery tests")
    return (
        engine,
        async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        ),
    )


async def _seed_video(
    session: AsyncSession,
    *,
    channel_id: str,
    video_id: str,
) -> YouTubeVideo:
    channel_repo = ChannelRepository(session)
    video_repo = VideoRepository(session)
    song_repo = SongRepository(session)
    await channel_repo.create(
        YouTubeChannel(
            id=channel_id,
            name="Crash Recovery Test",
            url=f"https://www.youtube.com/channel/{channel_id}",
        )
    )
    video = await video_repo.upsert(
        YouTubeVideo(
            id=video_id,
            title="Original karaoke title",
            url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=channel_id,
            type="karaoke",
            raw_data={"title": "Original karaoke title"},
            metadata_raw_data={"duration": 3600, "live_status": "was_live"},
        )
    )
    video.has_song_list_comment = True
    video.analysis_status = "done"
    video.comments_raw_data = {"comments": [{"text": "0:10 Original Song"}]}
    video.song_list_comment_raw_data = {"text": "0:10 Original Song"}
    await video_repo.update_analysis(video)
    await song_repo.replace_for_video(
        video_id,
        [Song(title="Original Song", video_id=video_id, timestamp="0:10")],
    )
    await session.commit()
    return video


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    *,
    channel_id: str,
    video_id: str,
) -> None:
    async with factory() as session:
        await session.execute(delete(Songs).where(Songs.video_id == video_id))
        await session.execute(delete(Videos).where(Videos.id == video_id))
        await session.execute(delete(Channels).where(Channels.id == channel_id))
        await session.commit()


@pytest.mark.asyncio
async def test_unexpected_analyzer_failure_rolls_back_complete_video_unit(
    monkeypatch,
):
    engine, factory = await _database()
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_crash_{suffix}"
    video_id = f"vid_crash_{suffix}"
    try:
        async with factory() as session:
            queued = await _seed_video(
                session,
                channel_id=channel_id,
                video_id=video_id,
            )
            real_video_repo = VideoRepository(session)
            song_repo = SongRepository(session)
            queue_repo = SimpleNamespace(
                get_analysis_queue=AsyncMock(return_value=[queued]),
                update_analysis=real_video_repo.update_analysis,
            )
            updater = DataUpdater(
                session,
                SimpleNamespace(),
                queue_repo,
                song_repo,
            )

            async def fail_after_all_writes(target: YouTubeVideo) -> None:
                target.title = "Partially updated title"
                target.metadata_raw_data = {
                    "duration": 7200,
                    "live_status": "was_live",
                }
                await real_video_repo.upsert(target)
                await song_repo.replace_for_video(
                    video_id,
                    [
                        Song(
                            title="Partially updated song",
                            video_id=video_id,
                            timestamp="1:00",
                        )
                    ],
                )
                target.comments_raw_data = {
                    "comments": [{"text": "1:00 Partially updated song"}]
                }
                await real_video_repo.update_analysis(target)
                raise RuntimeError("simulated analyzer crash")

            monkeypatch.setattr(updater, "_analyze_video", fail_after_all_writes)
            await updater._process_analysis_queue()

        async with factory() as observer:
            stored = await VideoRepository(observer).get_by_id(video_id)
            songs = await SongRepository(observer).get_by_video_id(video_id)

        assert stored is not None
        assert stored.title == "Original karaoke title"
        assert stored.metadata_raw_data == {
            "duration": 3600,
            "live_status": "was_live",
        }
        assert stored.comments_raw_data == {
            "comments": [{"text": "0:10 Original Song"}]
        }
        assert [song.title for song in songs] == ["Original Song"]
    finally:
        await _cleanup(factory, channel_id=channel_id, video_id=video_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancellation_rolls_back_and_does_not_consume_analysis_attempt(
    monkeypatch,
):
    engine, factory = await _database()
    suffix = uuid.uuid4().hex[:8]
    channel_id = f"ch_cancel_{suffix}"
    video_id = f"vid_cancel_{suffix}"
    try:
        async with factory() as session:
            queued = await _seed_video(
                session,
                channel_id=channel_id,
                video_id=video_id,
            )
            real_video_repo = VideoRepository(session)
            queue_repo = SimpleNamespace(
                get_analysis_queue=AsyncMock(return_value=[queued]),
                update_analysis=real_video_repo.update_analysis,
            )
            updater = DataUpdater(
                session,
                SimpleNamespace(),
                queue_repo,
                SongRepository(session),
            )

            async def cancel_after_write(target: YouTubeVideo) -> None:
                target.analyze_attempts += 1
                target.analysis_status = "retry"
                await real_video_repo.update_analysis(target)
                raise asyncio.CancelledError

            monkeypatch.setattr(updater, "_analyze_video", cancel_after_write)
            with pytest.raises(asyncio.CancelledError):
                await updater._process_analysis_queue()

        async with factory() as observer:
            stored = await VideoRepository(observer).get_by_id(video_id)

        assert stored is not None
        assert stored.analyze_attempts == 0
        assert stored.analysis_status == "done"
    finally:
        await _cleanup(factory, channel_id=channel_id, video_id=video_id)
        await engine.dispose()
