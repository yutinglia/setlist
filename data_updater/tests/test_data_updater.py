"""DataUpdater orchestration regressions that do not require PostgreSQL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.channel import YouTubeChannel
from models.video import YouTubeVideo
from services.data_updater import DataUpdater


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
    song_repo.replace_for_video.assert_awaited_once_with(video.id, [])


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
