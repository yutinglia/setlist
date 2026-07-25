"""DataUpdater orchestration regressions that do not require PostgreSQL."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config import SCRAPE_POLICY
from models.channel import (
    VIDEO_BACKFILL_FAILED,
    VIDEO_BACKFILL_PENDING,
    VIDEO_BACKFILL_RUNNING,
    YouTubeChannel,
)
from models.video import YouTubeVideo
from services.data_updater import DataUpdater
from services.updater_status import UpdaterPhase, updater_status
from services.yt_scraper.channel_video_scraper import ChannelVideoPageResult
from services.yt_scraper.errors import YouTubeAccessBlocked


def _channel(channel_id: str) -> YouTubeChannel:
    return YouTubeChannel(
        id=channel_id,
        name=channel_id,
        url=f"https://www.youtube.com/channel/{channel_id}",
        raw_data={},
    )


def _video() -> YouTubeVideo:
    return YouTubeVideo(
        id="video-1",
        title="Karaoke stream",
        url="https://www.youtube.com/watch?v=video-1",
        channel_id="channel-1",
        type="karaoke",
        raw_data={"duration": 3600, "live_status": "was_live"},
    )


@pytest.mark.asyncio
async def test_comment_cap_does_not_skip_later_channel_metadata(monkeypatch):
    channels = [_channel("channel-1"), _channel("channel-2")]
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(get_all=AsyncMock(return_value=channels)),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    processed: list[str] = []

    async def process(channel: YouTubeChannel) -> None:
        processed.append(channel.id)
        updater._comment_scrapes_this_cycle = 999

    monkeypatch.setattr(updater, "_process_channel", process)
    await updater.update()

    assert processed == ["channel-1", "channel-2"]
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_persisted_cooldown_survives_process_restart():
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=10)
    get_all = AsyncMock(return_value=[])
    channel_repo = SimpleNamespace(
        get_youtube_cooldown_until=AsyncMock(return_value=future),
        get_all=get_all,
    )
    updater = DataUpdater(
        SimpleNamespace(),
        channel_repo,
        SimpleNamespace(),
        SimpleNamespace(),
    )
    DataUpdater._youtube_cooldown_until = None

    await updater.update()

    get_all.assert_not_awaited()
    assert DataUpdater.youtube_cooldown_remaining() > 9 * 60
    DataUpdater._youtube_cooldown_until = None
    updater_status.stop(detail="test cleanup")


@pytest.mark.asyncio
async def test_successful_no_setlist_analysis_clears_old_songs(monkeypatch):
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return [{"text": "Great stream, thank you!"}]

    monkeypatch.setattr(
        "services.data_updater.YouTubeVideoCommentScraper", CommentScraper
    )
    song_repo = SimpleNamespace(replace_for_video=AsyncMock(return_value=[]))
    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        song_repo,
    )

    video = _video()
    video.has_song_list_comment = True
    video.cleaned_song_list_comment = {"text": "old"}
    video.cleaning_attempts = 2
    await updater._analyze_video(video)

    song_repo.replace_for_video.assert_awaited_once_with(video.id, [])
    assert video.has_song_list_comment is False
    assert video.cleaned_song_list_comment is None
    assert video.cleaning_attempts == 0
    video_repo.update_analysis.assert_awaited_once()


@pytest.mark.asyncio
async def test_timestamp_only_comment_is_not_persisted_as_a_setlist(monkeypatch):
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return [{"text": "0:10\n0:20\n0:30"}]

    monkeypatch.setattr(
        "services.data_updater.YouTubeVideoCommentScraper", CommentScraper
    )
    song_repo = SimpleNamespace(replace_for_video=AsyncMock(return_value=[]))
    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        song_repo,
    )
    video = _video()

    await updater._analyze_video(video)

    assert video.has_song_list_comment is False
    assert video.song_list_comment_raw_data is None
    assert video.analysis_status == "no_setlist"
    assert video.next_analysis_at is not None
    song_repo.replace_for_video.assert_awaited_once_with(video.id, [])


@pytest.mark.asyncio
async def test_successful_no_setlist_is_delayed_instead_of_immediate_retry(
    monkeypatch,
):
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return []

    monkeypatch.setattr(
        "services.data_updater.YouTubeVideoCommentScraper", CommentScraper
    )
    policy = replace(SCRAPE_POLICY, analysis_recheck_seconds=3600)
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(update_analysis=AsyncMock()),
        SimpleNamespace(replace_for_video=AsyncMock(return_value=[])),
        policy=policy,
    )
    video = _video()

    before = datetime.now(UTC).replace(tzinfo=None)
    await updater._analyze_video(video)

    assert video.analysis_status == "no_setlist"
    assert video.next_analysis_at is not None
    assert video.next_analysis_at >= before + timedelta(seconds=3599)
    assert video.analyze_attempts == 1


@pytest.mark.asyncio
async def test_youtube_block_does_not_exhaust_video_attempt(monkeypatch):
    class BlockedCommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            raise YouTubeAccessBlocked("HTTP Error 429")

    monkeypatch.setattr(
        "services.data_updater.YouTubeVideoCommentScraper",
        BlockedCommentScraper,
    )
    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        SimpleNamespace(),
    )
    video = _video()
    video.analyze_attempts = 2

    with pytest.raises(YouTubeAccessBlocked):
        await updater._analyze_video(video)

    assert video.analyze_attempts == 2
    assert video.analysis_status == "retry"
    assert video.next_analysis_at is not None
    video_repo.update_analysis.assert_awaited_once()


@pytest.mark.asyncio
async def test_jitter_applies_across_channel_boundary(monkeypatch):
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return []

    monkeypatch.setattr(
        "services.data_updater.YouTubeVideoCommentScraper", CommentScraper
    )
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(update_analysis=AsyncMock()),
        SimpleNamespace(replace_for_video=AsyncMock(return_value=[])),
    )
    updater._comment_scrapes_this_cycle = 1
    jitter = AsyncMock()
    monkeypatch.setattr(updater, "_jitter_sleep", jitter)

    await updater._analyze_video(_video())

    jitter.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_refresh_commits_inside_lock_and_never_cleans_existing_data(
    monkeypatch,
):
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    scraped = [_video()]
    video_repo = SimpleNamespace(upsert_many=AsyncMock(return_value=scraped))
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        video_repo,
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_scrape_channel_videos",
        AsyncMock(return_value=scraped),
    )

    result = await updater.refresh_channel_video_list(_channel("channel-1"))

    assert result.scraped == 1
    assert result.deleted == result.reclassified == result.cleared == 0
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


def test_backfill_priority_retries_failures_and_rotates_oldest_first():
    normal = _channel("normal")
    pending = _channel("pending").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_PENDING,
            "created_at": datetime(2026, 3, 1),
        }
    )
    old_failed = _channel("old-failed").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_FAILED,
            "video_backfill_updated_at": datetime(2026, 1, 1),
        }
    )
    recent_running = _channel("recent-running").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_RUNNING,
            "video_backfill_updated_at": datetime(2026, 2, 1),
        }
    )

    ordered = DataUpdater._prioritize_backfill_channels(
        [normal, recent_running, old_failed, pending]
    )

    assert [channel.id for channel in ordered] == [
        "old-failed",
        "recent-running",
        "pending",
        "normal",
    ]


@pytest.mark.asyncio
async def test_partial_backfill_page_keeps_cursor_and_schedules_retry(monkeypatch):
    channel = _channel("channel-1").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_RUNNING,
            "video_backfill_offset": 21,
        }
    )
    page = ChannelVideoPageResult(
        videos=[_video()],
        raw_entry_count=1,
        exhausted=False,
        all_tabs_succeeded=False,
        failed_tabs=("https://www.youtube.com/@demo/streams",),
        page_size=20,
        playlist_start=21,
        playlist_end=40,
    )
    channel_repo = SimpleNamespace(update_video_backfill=AsyncMock())
    video_repo = SimpleNamespace(upsert_many=AsyncMock(return_value=page.videos))
    updater = DataUpdater(
        SimpleNamespace(),
        channel_repo,
        video_repo,
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        "services.data_updater.asyncio.to_thread",
        AsyncMock(return_value=page),
    )

    await updater._backfill_channel_video_page(channel)

    channel_repo.update_video_backfill.assert_awaited_once_with(
        channel.id,
        status=VIDEO_BACKFILL_FAILED,
        offset=21,
    )


@pytest.mark.asyncio
async def test_backfill_processes_multiple_durable_pages_per_cycle(monkeypatch):
    channel = _channel("channel-1").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_PENDING,
            "video_backfill_offset": 1,
        }
    )
    running = channel.model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_RUNNING,
            "video_backfill_offset": 101,
        }
    )
    done = running.model_copy(update={"video_backfill_status": "done"})
    session = SimpleNamespace(commit=AsyncMock())
    video_repo = SimpleNamespace(
        reclassify_for_channel=AsyncMock(return_value=0),
        delete_non_persisted_for_channel=AsyncMock(return_value=0),
        clear_analysis_for_non_karaoke=AsyncMock(return_value=[]),
    )
    policy = replace(
        SCRAPE_POLICY,
        backfill_pages_per_cycle=3,
        inter_list_sleep_min=0,
        inter_list_sleep_max=0,
    )
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        video_repo,
        SimpleNamespace(replace_for_video=AsyncMock()),
        policy=policy,
    )
    page = AsyncMock(side_effect=[running, done])
    monkeypatch.setattr(updater, "_backfill_channel_video_page", page)
    pause = AsyncMock()
    monkeypatch.setattr(updater, "_list_jitter_sleep", pause)

    await updater._process_channel(channel)

    assert page.await_count == 2
    assert session.commit.await_count == 2
    pause.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_refresh_failure_updates_status_and_rolls_back(monkeypatch):
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_scrape_channel_videos",
        AsyncMock(side_effect=RuntimeError("secret upstream details")),
    )

    with pytest.raises(RuntimeError, match="secret upstream details"):
        await updater.refresh_channel_video_list(_channel("channel-1"))

    snap = updater_status.snapshot()
    assert snap["phase"] == UpdaterPhase.ERROR.value
    assert snap["last_error"] == "A manual video metadata refresh failed"
    assert "secret upstream details" not in (snap["detail"] or "")
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_refresh_commit_failure_does_not_leave_running_status(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(side_effect=RuntimeError("database details")),
        rollback=AsyncMock(),
    )
    scraped = [_video()]
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(upsert_many=AsyncMock(return_value=scraped)),
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_scrape_channel_videos",
        AsyncMock(return_value=scraped),
    )

    with pytest.raises(RuntimeError, match="database details"):
        await updater.refresh_channel_video_list(_channel("channel-1"))

    snap = updater_status.snapshot()
    assert snap["phase"] == UpdaterPhase.ERROR.value
    assert snap["last_error"] == "A manual video metadata refresh failed"
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_refresh_preserves_cooldown_status(monkeypatch):
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_scrape_channel_videos",
        AsyncMock(side_effect=YouTubeAccessBlocked("blocked details")),
    )

    with pytest.raises(YouTubeAccessBlocked):
        await updater.refresh_channel_video_list(_channel("channel-1"))

    snap = updater_status.snapshot()
    assert snap["phase"] == UpdaterPhase.COOLDOWN.value
    assert snap["last_error"] != "A manual video metadata refresh failed"
    session.rollback.assert_awaited_once()
    DataUpdater._youtube_cooldown_until = None
    updater_status.stop(detail="test cleanup")
