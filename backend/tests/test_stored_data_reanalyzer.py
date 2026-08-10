"""Offline replay of stored metadata/comments is safe and transaction-owned."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from models.song import Song
from models.video import YouTubeVideo
from services.stored_data_reanalyzer import StoredDataReanalyzer


def _video(
    video_id: str,
    comments: list[dict],
    *,
    has_setlist: bool = False,
    cleaned: bool = False,
) -> YouTubeVideo:
    return YouTubeVideo(
        id=video_id,
        title=f"Karaoke {video_id}",
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_id="channel-1",
        type="karaoke",
        analysis_status="done" if has_setlist else "no_setlist",
        has_song_list_comment=has_setlist,
        comments_raw_data={
            "schema_version": 1,
            "comments": comments,
            "comments_available": True,
        },
        cleaned_song_list_comment={"text": "cleaned"} if cleaned else None,
    )


@pytest.mark.asyncio
async def test_dry_run_reclassifies_replays_and_rolls_back():
    recovered = _video(
        "recovered",
        [
            {
                "id": "comment-1",
                "author": "@helper",
                "author_id": "UC-helper",
                "text": "Set list\n0:10 Song A\n0:20 Song B",
            }
        ],
    )
    preserved_negative = _video(
        "negative",
        [{"text": "Thanks for the stream"}],
        has_setlist=True,
    )
    skipped_cleaned = _video(
        "cleaned",
        [{"text": "0:10 New A\n0:20 New B\n0:30 New C"}],
        has_setlist=True,
        cleaned=True,
    )
    existing = {
        "recovered": [],
        "negative": [Song(title="Old", timestamp="0:10", video_id="negative")],
        "cleaned": [Song(title="LLM result", timestamp="0:10", video_id="cleaned")],
    }

    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    channel_repo = SimpleNamespace(
        get_all=AsyncMock(return_value=[SimpleNamespace(id="channel-1")])
    )
    video_repo = SimpleNamespace(
        reclassify_for_channel=AsyncMock(return_value=3),
        clear_analysis_for_non_karaoke=AsyncMock(return_value=["not-karaoke"]),
        get_with_stored_comments=AsyncMock(
            return_value=[recovered, preserved_negative, skipped_cleaned]
        ),
        update_analysis=AsyncMock(),
    )
    song_repo = SimpleNamespace(
        get_by_video_id=AsyncMock(side_effect=lambda video_id: existing[video_id]),
        replace_for_video=AsyncMock(return_value=[]),
    )
    service = StoredDataReanalyzer(
        session,
        channel_repo,
        video_repo,
        song_repo,
        max_analysis_attempts=3,
    )

    result = await service.run(apply=False)

    assert result.applied is False
    assert result.reclassified_videos == 3
    assert result.cleared_non_karaoke_videos == 1
    assert result.stored_comment_videos == 3
    assert result.detected_setlists == 1
    assert result.recovered_setlists == 1
    assert result.changed_setlists == 1
    assert result.skipped_existing_setlists == 2
    assert result.skipped_cleaned_setlists == 0
    assert result.requeued_unresolved_videos == 0
    assert result.songs_before == 2
    assert result.songs_after == 4
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    assert song_repo.replace_for_video.await_args_list[0] == call("not-karaoke", [])
    replay_call = song_repo.replace_for_video.await_args_list[1]
    assert replay_call.args[0] == "recovered"
    assert [song.title for song in replay_call.args[1]] == ["Song A", "Song B"]
    assert recovered.setlist_comment_author == "@helper"
    assert recovered.setlist_comment_author_id == "UC-helper"
    assert recovered.setlist_comment_id == "comment-1"
    video_repo.update_analysis.assert_awaited_once_with(recovered)


@pytest.mark.asyncio
async def test_apply_commits_complete_empty_pass():
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = StoredDataReanalyzer(
        session,
        SimpleNamespace(get_all=AsyncMock(return_value=[])),
        SimpleNamespace(get_with_stored_comments=AsyncMock(return_value=[])),
        SimpleNamespace(),
        max_analysis_attempts=3,
    )

    result = await service.run(apply=True)

    assert result.applied is True
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_setlists_are_rewritten_only_when_explicitly_enabled():
    successful = _video(
        "successful",
        [{"text": "0:10 New A\n0:20 New B\n0:30 New C"}],
        has_setlist=True,
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    video_repo = SimpleNamespace(
        get_with_stored_comments=AsyncMock(return_value=[successful]),
        update_analysis=AsyncMock(),
    )
    song_repo = SimpleNamespace(
        get_by_video_id=AsyncMock(
            return_value=[Song(title="Old", timestamp="0:10", video_id="successful")]
        ),
        replace_for_video=AsyncMock(return_value=[]),
    )
    service = StoredDataReanalyzer(
        session,
        SimpleNamespace(get_all=AsyncMock(return_value=[])),
        video_repo,
        song_repo,
        max_analysis_attempts=5,
    )

    result = await service.run(apply=False, include_successful=True)

    assert result.changed_setlists == 1
    assert result.skipped_existing_setlists == 0
    assert result.recovered_setlists == 0
    video_repo.update_analysis.assert_awaited_once_with(successful)


@pytest.mark.asyncio
async def test_unresolved_requeue_is_explicit_and_reported():
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    video_repo = SimpleNamespace(
        get_with_stored_comments=AsyncMock(return_value=[]),
        requeue_unresolved_karaoke=AsyncMock(return_value=12),
    )
    service = StoredDataReanalyzer(
        session,
        SimpleNamespace(get_all=AsyncMock(return_value=[])),
        video_repo,
        SimpleNamespace(),
        max_analysis_attempts=5,
    )

    result = await service.run(apply=False, requeue_unresolved=True)

    assert result.requeued_unresolved_videos == 12
    video_repo.requeue_unresolved_karaoke.assert_awaited_once_with(max_attempts=5)
