"""Selected setlist-comment attribution normalization."""

from models.video import YouTubeVideo
from services.analyzer.comment_attribution import (
    apply_setlist_comment_attribution,
    clear_setlist_comment_attribution,
)


def _video() -> YouTubeVideo:
    return YouTubeVideo(
        id="video-1",
        title="Karaoke",
        url="https://www.youtube.com/watch?v=video-1",
        channel_id="channel-1",
    )


def test_apply_and_clear_setlist_comment_attribution():
    video = _video()
    apply_setlist_comment_attribution(
        video,
        {
            "author": "  @setlist-helper  ",
            "author_id": "UC-helper",
            "id": "comment-1",
        },
    )

    assert video.setlist_comment_author == "@setlist-helper"
    assert video.setlist_comment_author_id == "UC-helper"
    assert video.setlist_comment_id == "comment-1"

    clear_setlist_comment_attribution(video)
    assert video.setlist_comment_author is None
    assert video.setlist_comment_author_id is None
    assert video.setlist_comment_id is None


def test_attribution_ignores_invalid_values_and_bounds_strings():
    video = _video()
    apply_setlist_comment_attribution(
        video,
        {
            "author": "x" * 300,
            "author_id": 123,
            "id": " ",
        },
    )

    assert video.setlist_comment_author == "x" * 255
    assert video.setlist_comment_author_id is None
    assert video.setlist_comment_id is None
