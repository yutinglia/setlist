"""DataUpdater orchestration regressions that do not require PostgreSQL."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from config import SCRAPE_POLICY
from models.channel import (
    VIDEO_BACKFILL_FAILED,
    VIDEO_BACKFILL_PENDING,
    VIDEO_BACKFILL_RUNNING,
    YouTubeChannel,
)
from models.video import YouTubeVideo
from services.data_updater import DataUpdater, RetryableVideoAnalysisError
from services.updater_runtime_state import (
    UPDATER_PROCESS_OWNER_ID,
    UpdaterOutcome,
)
from services.updater_status import UpdaterPhase, updater_status
from services.yt_scraper.channel_video_scraper import ChannelVideoPageResult
from services.yt_scraper.errors import YouTubeAccessBlocked
from services.yt_scraper.video_comment_scraper import VideoCommentScrapeResult


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


class _InlineScrapeExecutor:
    async def run(self, operation, *, production):
        del production
        return operation()


def _comment_scraper_dependencies(scraper):
    return {
        "scraper_factory": SimpleNamespace(
            video_comments=Mock(return_value=scraper),
        ),
        "scrape_executor": _InlineScrapeExecutor(),
    }


@pytest.mark.asyncio
async def test_cycle_persists_successful_runtime_lifecycle():
    runtime_store = SimpleNamespace(
        mark_started=AsyncMock(),
        heartbeat=AsyncMock(return_value=True),
        mark_finished=AsyncMock(return_value=True),
    )
    updater = DataUpdater(
        SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock()),
        SimpleNamespace(get_all=AsyncMock(return_value=[])),
        SimpleNamespace(get_analysis_queue=AsyncMock(return_value=[])),
        SimpleNamespace(),
        runtime_state_store=runtime_store,
    )

    await updater.update()

    runtime_store.mark_started.assert_awaited_once_with(UPDATER_PROCESS_OWNER_ID)
    runtime_store.mark_finished.assert_awaited_once_with(
        UPDATER_PROCESS_OWNER_ID,
        UpdaterOutcome.SUCCESS,
    )


@pytest.mark.asyncio
async def test_cancelled_cycle_persists_cancelled_runtime_outcome(monkeypatch):
    runtime_store = SimpleNamespace(
        mark_started=AsyncMock(),
        heartbeat=AsyncMock(return_value=True),
        mark_finished=AsyncMock(return_value=True),
    )
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        runtime_state_store=runtime_store,
    )

    async def cancel_cycle(**_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(updater, "_update_without_lock", cancel_cycle)

    with pytest.raises(asyncio.CancelledError):
        await updater.update()

    runtime_store.mark_finished.assert_awaited_once_with(
        UPDATER_PROCESS_OWNER_ID,
        UpdaterOutcome.CANCELLED,
    )


@pytest.mark.asyncio
async def test_comment_cap_does_not_skip_later_channel_metadata(monkeypatch):
    channels = [_channel("channel-1"), _channel("channel-2")]
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    cache = SimpleNamespace(invalidate=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(get_all=AsyncMock(return_value=channels)),
        SimpleNamespace(),
        SimpleNamespace(),
        cache=cache,
    )

    processed: list[str] = []

    async def process(channel: YouTubeChannel) -> None:
        processed.append(channel.id)
        updater._comment_scrapes_this_cycle = 999

    monkeypatch.setattr(updater, "_process_channel", process)
    await updater.update()

    assert processed == ["channel-1", "channel-2"]
    assert session.commit.await_count == 2
    cache.invalidate.assert_not_awaited()


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

    await updater.update()

    get_all.assert_not_awaited()
    assert updater.cooldown.remaining() > 9 * 60
    updater_status.stop(detail="test cleanup")


@pytest.mark.asyncio
async def test_negative_reanalysis_preserves_prior_successful_setlist():
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return [{"text": "Great stream, thank you!"}]

    song_repo = SimpleNamespace(replace_for_video=AsyncMock(return_value=[]))
    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        song_repo,
        **_comment_scraper_dependencies(CommentScraper()),
    )

    video = _video()
    video.has_song_list_comment = True
    video.comments_raw_data = {
        "comments": [{"text": "0:10 Old Song"}],
        "comments_available": True,
    }
    video.cleaned_song_list_comment = {"text": "old"}
    video.cleaning_attempts = 2
    await updater._analyze_video(video)

    song_repo.replace_for_video.assert_not_awaited()
    assert video.has_song_list_comment is True
    assert video.comments_raw_data["comments"] == [{"text": "0:10 Old Song"}]
    assert video.comments_raw_data["last_negative_observation"]["comments"] == [
        {"text": "Great stream, thank you!"}
    ]
    assert video.cleaned_song_list_comment == {"text": "old"}
    assert video.analysis_status == "done"
    video_repo.update_analysis.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_setlist_persists_comment_attribution():
    source_comment = {
        "id": "comment-1",
        "author": "@setlist-helper",
        "author_id": "UC-helper",
        "text": "0:10 Song A\n1:20 Song B\n2:30 Song C",
    }

    class CommentScraper:
        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return [source_comment]

    song_repo = SimpleNamespace(replace_for_video=AsyncMock(return_value=[]))
    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        song_repo,
        **_comment_scraper_dependencies(CommentScraper()),
    )
    video = _video()

    await updater._analyze_video(video)

    assert video.has_song_list_comment is True
    assert video.song_list_comment_raw_data == source_comment
    assert video.setlist_comment_author == "@setlist-helper"
    assert video.setlist_comment_author_id == "UC-helper"
    assert video.setlist_comment_id == "comment-1"
    persisted_songs = song_repo.replace_for_video.await_args.args[1]
    assert [song.title for song in persisted_songs] == ["Song A", "Song B", "Song C"]
    video_repo.update_analysis.assert_awaited_once_with(video)


@pytest.mark.asyncio
async def test_comment_request_upgrades_approximate_date_without_another_scrape():
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            self.video_metadata = {
                "upload_date": "20260725",
                "timestamp": 1_784_997_784,
                "duration": 3600,
                "live_status": "was_live",
            }

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return []

    video_repo = SimpleNamespace(
        upsert=AsyncMock(),
        update_analysis=AsyncMock(),
    )
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        SimpleNamespace(replace_for_video=AsyncMock(return_value=[])),
        **_comment_scraper_dependencies(CommentScraper()),
    )
    video = _video().model_copy(
        update={
            "upload_date": "20260726",
            "upload_date_precision": "approximate",
        }
    )

    await updater._analyze_video(video)

    assert video.upload_date == "20260725"
    assert video.upload_date_precision == "exact"
    assert video.metadata_raw_data is not None
    assert video.metadata_raw_data["data"]["upload_date"] == "20260725"
    video_repo.upsert.assert_awaited_once_with(video)


@pytest.mark.asyncio
async def test_full_metadata_reclassifies_false_positive_and_keeps_observations():
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            self.video_metadata = {
                "title": "Short chat clip",
                "duration": 45,
                "live_status": "not_live",
            }

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return [{"text": "Useful raw comment"}]

    video_repo = SimpleNamespace(
        upsert=AsyncMock(),
        update_analysis=AsyncMock(),
    )
    song_repo = SimpleNamespace(replace_for_video=AsyncMock(return_value=[]))
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        song_repo,
        **_comment_scraper_dependencies(CommentScraper()),
    )
    video = _video()

    await updater._analyze_video(video)

    assert video.type == "other"
    assert video.analysis_status == "skipped"
    assert video.comments_raw_data["comments"] == [{"text": "Useful raw comment"}]
    assert video.metadata_raw_data["data"]["duration"] == 45
    song_repo.replace_for_video.assert_awaited_once_with(video.id, [])
    video_repo.upsert.assert_awaited_once_with(video)
    video_repo.update_analysis.assert_awaited_once_with(video)


@pytest.mark.asyncio
async def test_timestamp_only_comment_is_not_persisted_as_a_setlist():
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return [{"text": "0:10\n0:20\n0:30"}]

    song_repo = SimpleNamespace(replace_for_video=AsyncMock(return_value=[]))
    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        song_repo,
        **_comment_scraper_dependencies(CommentScraper()),
    )
    video = _video()

    await updater._analyze_video(video)

    assert video.has_song_list_comment is False
    assert video.song_list_comment_raw_data is None
    assert video.analysis_status == "no_setlist"
    assert video.next_analysis_at is not None
    song_repo.replace_for_video.assert_awaited_once_with(video.id, [])


@pytest.mark.asyncio
async def test_successful_no_setlist_is_delayed_instead_of_immediate_retry():
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return []

    policy = replace(SCRAPE_POLICY, analysis_recheck_seconds=3600)
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(update_analysis=AsyncMock()),
        SimpleNamespace(replace_for_video=AsyncMock(return_value=[])),
        policy=policy,
        **_comment_scraper_dependencies(CommentScraper()),
    )
    video = _video()

    before = datetime.now(UTC).replace(tzinfo=None)
    await updater._analyze_video(video)

    assert video.analysis_status == "no_setlist"
    assert video.next_analysis_at is not None
    assert video.next_analysis_at >= before + timedelta(seconds=3599)
    assert video.analyze_attempts == 1


@pytest.mark.parametrize(("prior_attempts", "expected_limit"), [(0, 7), (1, 19)])
@pytest.mark.asyncio
async def test_comment_rechecks_use_deeper_top_comment_window(
    prior_attempts,
    expected_limit,
):
    seen_limits: list[int] = []

    class CommentScraper:
        def scrape(self, max_comments: int) -> VideoCommentScrapeResult:
            seen_limits.append(max_comments)
            return VideoCommentScrapeResult(
                comments=[],
                comments_available=True,
                metadata_raw_data={},
                scraped_at=datetime.now(UTC).replace(tzinfo=None),
            )

    policy = replace(
        SCRAPE_POLICY,
        max_comments_per_video=7,
        max_recheck_comments_per_video=19,
    )
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(update_analysis=AsyncMock()),
        SimpleNamespace(replace_for_video=AsyncMock(return_value=[])),
        policy=policy,
        **_comment_scraper_dependencies(CommentScraper()),
    )
    video = _video()
    video.analyze_attempts = prior_attempts

    await updater._analyze_video(video)

    assert seen_limits == [expected_limit]


@pytest.mark.asyncio
async def test_youtube_block_does_not_exhaust_video_attempt():
    class BlockedCommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            raise YouTubeAccessBlocked("HTTP Error 429")

    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        SimpleNamespace(),
        **_comment_scraper_dependencies(BlockedCommentScraper()),
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
async def test_scraper_failure_records_retry_state_with_explicit_exception():
    class FailingCommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            raise RuntimeError("temporary upstream failure")

    video_repo = SimpleNamespace(update_analysis=AsyncMock())
    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        video_repo,
        SimpleNamespace(),
        **_comment_scraper_dependencies(FailingCommentScraper()),
    )
    video = _video()

    with pytest.raises(
        RetryableVideoAnalysisError,
        match="temporary upstream failure",
    ):
        await updater._analyze_video(video)

    assert video.analyze_attempts == 1
    assert video.analysis_status == "retry"
    assert video.next_analysis_at is not None
    video_repo.update_analysis.assert_awaited_once_with(video)


@pytest.mark.asyncio
async def test_analysis_queue_commits_only_explicit_retryable_failure(monkeypatch):
    video = _video()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(get_analysis_queue=AsyncMock(return_value=[video])),
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_analyze_video",
        AsyncMock(side_effect=RetryableVideoAnalysisError("retry")),
    )

    await updater._process_analysis_queue()

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_analysis_queue_rolls_back_unexpected_failure(monkeypatch):
    video = _video()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(get_analysis_queue=AsyncMock(return_value=[video])),
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_analyze_video",
        AsyncMock(side_effect=RuntimeError("analyzer bug")),
    )

    await updater._process_analysis_queue()

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_analysis_queue_cancellation_rolls_back_and_propagates(monkeypatch):
    video = _video()
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    updater = DataUpdater(
        session,
        SimpleNamespace(),
        SimpleNamespace(get_analysis_queue=AsyncMock(return_value=[video])),
        SimpleNamespace(),
    )
    monkeypatch.setattr(
        updater,
        "_analyze_video",
        AsyncMock(side_effect=asyncio.CancelledError),
    )

    with pytest.raises(asyncio.CancelledError):
        await updater._process_analysis_queue()

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_jitter_applies_across_channel_boundary(monkeypatch):
    class CommentScraper:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def get_video_top_comments(self, _max_comments: int) -> list[dict]:
            return []

    updater = DataUpdater(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(update_analysis=AsyncMock()),
        SimpleNamespace(replace_for_video=AsyncMock(return_value=[])),
        **_comment_scraper_dependencies(CommentScraper()),
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
    scraped = [_video().model_copy(update={"title": "Chat", "type": "other"})]
    video_repo = SimpleNamespace(
        upsert_many=AsyncMock(return_value=scraped),
        reclassify_for_channel=AsyncMock(return_value=1),
    )
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
    assert result.deleted == result.cleared == 0
    assert result.reclassified == 1
    video_repo.upsert_many.assert_awaited_once_with(scraped)
    video_repo.reclassify_for_channel.assert_awaited_once_with("channel-1")
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


def test_explicit_new_channel_priority_overrides_backfill_rotation():
    old_failed = _channel("old-failed").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_FAILED,
            "video_backfill_updated_at": datetime(2026, 1, 1),
        }
    )
    newly_added = _channel("newly-added").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_PENDING,
            "created_at": datetime(2026, 3, 1),
        }
    )

    ordered = DataUpdater._prioritize_backfill_channels(
        [old_failed, newly_added],
        priority_channel_id=newly_added.id,
    )

    assert [channel.id for channel in ordered] == ["newly-added", "old-failed"]


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
    video_repo = SimpleNamespace(
        upsert_many=AsyncMock(return_value=page.videos),
        reclassify_by_ids=AsyncMock(return_value=0),
        clear_analysis_for_non_karaoke_by_ids=AsyncMock(return_value=[]),
    )
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
    video_repo.reclassify_by_ids.assert_awaited_once_with([page.videos[0].id])
    video_repo.clear_analysis_for_non_karaoke_by_ids.assert_awaited_once_with(
        [page.videos[0].id],
        max_attempts=updater.policy.max_analysis_attempts,
    )


@pytest.mark.asyncio
async def test_backfill_commits_cleanup_and_cursor_as_one_ordered_unit(monkeypatch):
    channel = _channel("channel-1").model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_PENDING,
            "video_backfill_offset": 1,
        }
    )
    video = _video()
    page = ChannelVideoPageResult(
        videos=[video],
        raw_entry_count=1,
        exhausted=False,
        all_tabs_succeeded=True,
        failed_tabs=(),
        page_size=20,
        playlist_start=1,
        playlist_end=20,
    )
    events: list[str] = []

    async def record(name, result=None):
        events.append(name)
        return result

    async def commit():
        return await record("commit")

    async def update_cursor(*_args, **_kwargs):
        return await record("cursor", running)

    async def upsert(_videos):
        return await record("upsert", [video])

    async def reclassify(_ids):
        return await record("reclassify", 1)

    async def clear(_ids, **_kwargs):
        return await record("clear", [video.id])

    async def replace_songs(*_args):
        return await record("songs", [])

    running = channel.model_copy(
        update={
            "video_backfill_status": VIDEO_BACKFILL_RUNNING,
            "video_backfill_offset": 21,
        }
    )
    session = SimpleNamespace(commit=AsyncMock(side_effect=commit))
    channel_repo = SimpleNamespace(
        update_video_backfill=AsyncMock(side_effect=update_cursor)
    )
    video_repo = SimpleNamespace(
        upsert_many=AsyncMock(side_effect=upsert),
        reclassify_by_ids=AsyncMock(side_effect=reclassify),
        clear_analysis_for_non_karaoke_by_ids=AsyncMock(side_effect=clear),
    )
    song_repo = SimpleNamespace(replace_for_video=AsyncMock(side_effect=replace_songs))
    policy = replace(
        SCRAPE_POLICY,
        backfill_pages_per_cycle=1,
        inter_list_sleep_min=0,
        inter_list_sleep_max=0,
    )
    updater = DataUpdater(
        session,
        channel_repo,
        video_repo,
        song_repo,
        policy=policy,
    )
    monkeypatch.setattr(
        "services.data_updater.asyncio.to_thread",
        AsyncMock(return_value=page),
    )

    await updater._process_channel(channel)

    assert events == ["upsert", "reclassify", "clear", "songs", "cursor", "commit"]


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
        SimpleNamespace(
            upsert_many=AsyncMock(return_value=scraped),
            reclassify_for_channel=AsyncMock(return_value=0),
        ),
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
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    updater.cooldown.clear()
    updater_status.stop(detail="test cleanup")


@pytest.mark.asyncio
async def test_cooldown_commit_failure_rolls_back_without_local_cache():
    session = SimpleNamespace(
        commit=AsyncMock(side_effect=RuntimeError("database unavailable")),
        rollback=AsyncMock(),
    )
    channel_repo = SimpleNamespace(set_youtube_cooldown_until=AsyncMock())
    updater = DataUpdater(
        session,
        channel_repo,
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await updater._activate_youtube_cooldown()

    channel_repo.set_youtube_cooldown_until.assert_awaited_once()
    session.rollback.assert_awaited_once()
    assert updater.cooldown.remaining() == 0
