"""Normalize attribution from a selected yt-dlp setlist comment."""

from __future__ import annotations

from typing import Any

from models.video import YouTubeVideo

_MAX_ATTRIBUTION_LENGTH = 255


def apply_setlist_comment_attribution(
    video: YouTubeVideo,
    comment: dict[str, Any] | None,
) -> None:
    """Copy stable public attribution fields from a selected comment."""
    video.setlist_comment_author = _comment_string(comment, "author")
    video.setlist_comment_author_id = _comment_string(comment, "author_id")
    video.setlist_comment_id = _comment_string(comment, "id")


def clear_setlist_comment_attribution(video: YouTubeVideo) -> None:
    """Clear derived attribution when no successful setlist remains."""
    video.setlist_comment_author = None
    video.setlist_comment_author_id = None
    video.setlist_comment_id = None


def _comment_string(
    comment: dict[str, Any] | None,
    key: str,
) -> str | None:
    if not isinstance(comment, dict):
        return None
    value = comment.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()[:_MAX_ATTRIBUTION_LENGTH].rstrip()
    return normalized or None
