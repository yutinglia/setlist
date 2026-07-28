"""Administrator-triggered single-video setlist reload transaction behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.video import YouTubeVideo
from services.data_updater import DataUpdater


@pytest.mark.asyncio
async def test_manual_song_reload_analyzes_counts_then_commits():
    order: list[str] = []
    session = SimpleNamespace(
        commit=AsyncMock(side_effect=lambda: order.append("commit")),
        rollback=AsyncMock(),
    )
    channel_repo = SimpleNamespace(
        get_youtube_cooldown_until=AsyncMock(return_value=None),
    )
    song_repo = SimpleNamespace(
        count_by_video_id=AsyncMock(
            side_effect=lambda _video_id: order.append("count") or 4
        ),
    )
    updater = DataUpdater(
        session,
        channel_repo,
        SimpleNamespace(),
        song_repo,
    )
    video = YouTubeVideo(
        id="video-1",
        title="Karaoke archive",
        url="https://www.youtube.com/watch?v=video-1",
        channel_id="channel-1",
        type="karaoke",
    )

    async def analyze(target):
        order.append("analyze")
        target.has_song_list_comment = True
        target.analysis_status = "done"

    updater._analyze_video = analyze

    result = await updater.reload_video_song_list(video)

    assert result.video_id == video.id
    assert result.song_count == 4
    assert result.has_song_list_comment is True
    assert order == ["analyze", "count", "commit"]
    session.rollback.assert_not_awaited()
