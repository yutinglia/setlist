"""Classify videos from title keywords, with soft karaoke confirms."""

from __future__ import annotations

import re

# Explicit karaoke / 歌枠 stream markers (checked before song keywords).
_STRONG_KARAOKE_KEYWORDS: tuple[str, ...] = (
    "歌回",
    "karaoke",
    "歌枠",
    "カラok",
    "歌配信",
    "カラオケ",
)

# Weaker stream hint — only used if the title is not a standalone song/MV/cover.
_WEAK_KARAOKE_KEYWORDS: tuple[str, ...] = ("singing",)

# Standalone song / MV / cover uploads — never scrape setlist comments.
_SONG_KEYWORDS: tuple[str, ...] = (
    "mv",
    "cover",
    "music",
    "song",
    "歌ってみた",
    "オリジナル曲",
    "original song",
    "official music video",
    "カバー",
    "翻唱",
    "カバー曲",
)

VIDEO_TYPE_KARAOKE = "karaoke"
VIDEO_TYPE_SONG = "song"
VIDEO_TYPE_OTHER = "other"

# Karaoke streams are usually long; short clips with karaoke words are not archives.
KARAOKE_MIN_DURATION_SECONDS = 20 * 60


def _title_has_keyword(title: str, keyword: str) -> bool:
    """Case-insensitive substring match; ASCII keywords use word boundaries."""
    if not title or not keyword:
        return False
    # CJK / mixed keywords: plain casefold substring is enough.
    if any(ord(ch) > 127 for ch in keyword):
        return keyword.casefold() in title.casefold()
    pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
    return re.search(pattern, title, flags=re.IGNORECASE) is not None


def _title_has_any(title: str, keywords: tuple[str, ...]) -> bool:
    return any(_title_has_keyword(title, kw) for kw in keywords)


def is_strong_karaoke_title(title: str) -> bool:
    return _title_has_any(title, _STRONG_KARAOKE_KEYWORDS)


def is_weak_karaoke_title(title: str) -> bool:
    return _title_has_any(title, _WEAK_KARAOKE_KEYWORDS)


def is_karaoke_title(title: str) -> bool:
    """True when the title looks like a karaoke / singing stream record."""
    return is_strong_karaoke_title(title) or is_weak_karaoke_title(title)


def is_song_title(title: str) -> bool:
    """True when the title looks like a standalone song / MV / cover."""
    return _title_has_any(title, _SONG_KEYWORDS)


def _karaoke_live_status_ok(live_status: str | None) -> bool:
    """Soft confirm: unknown OK; known non-archives rejected."""
    if live_status is None or live_status == "":
        return True
    return live_status == "was_live"


def _karaoke_duration_ok(duration: float | int | None) -> bool:
    """Soft confirm: unknown OK; known short clips rejected."""
    if duration is None:
        return True
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return True
    return seconds >= KARAOKE_MIN_DURATION_SECONDS


def _karaoke_meta_ok(
    *,
    live_status: str | None,
    duration: float | int | None,
) -> bool:
    return _karaoke_live_status_ok(live_status) and _karaoke_duration_ok(duration)


def is_karaoke_stream(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
) -> bool:
    """True only for karaoke stream archives worth setlist comment scraping.

    Priority:
    1. Strong karaoke keywords (歌枠 / 歌回 / KARAOKE / …) + soft meta confirms
    2. Song/MV/cover keywords → never karaoke (no comment scrape)
    3. Weak ``Singing`` keyword + soft meta confirms
    """
    if not _karaoke_meta_ok(live_status=live_status, duration=duration):
        return False
    if is_strong_karaoke_title(title):
        return True
    if is_song_title(title):
        return False
    return is_weak_karaoke_title(title)


def should_scrape_comments(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
    stored_type: str | None = None,
) -> bool:
    """Whether this video should have comments fetched for setlist extraction.

    Re-evaluates from title/metadata. ``stored_type == song`` always blocks.
    """
    if (stored_type or "").lower() == VIDEO_TYPE_SONG:
        return False
    return is_karaoke_stream(
        title, live_status=live_status, duration=duration
    )


def classify_video_type(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
) -> str:
    """Return ``karaoke``, ``song``, or ``other``.

    Song/MV/cover titles win over weak ``Singing`` markers so standalone covers
    are never treated as karaoke streams. Strong karaoke markers (歌枠, etc.)
    still win when soft live_status/duration confirms pass.
    """
    if is_karaoke_stream(title, live_status=live_status, duration=duration):
        return VIDEO_TYPE_KARAOKE
    if is_song_title(title):
        return VIDEO_TYPE_SONG
    return VIDEO_TYPE_OTHER
