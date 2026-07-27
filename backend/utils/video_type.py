"""Classify song uploads and multi-song singing streams from title metadata."""

from __future__ import annotations

import re

# Reliable karaoke *stream* markers (not "went to karaoke" vlogs).
_STRONG_KARAOKE_KEYWORDS: tuple[str, ...] = (
    "歌回",
    "karaoke",
    "歌枠",
    "カラok",
    "歌配信",
    "カラオケ",
    "弾き語り",
    "アカペラ",
    "お歌放送",
)

# Outings / vlogs that mention karaoke but are not singing streams.
_KARAOKE_EXCLUDE_PHRASES: tuple[str, ...] = (
    "行ってみた",
    "行ってきた",
    "に行って",
    "に行った",
    "へ行った",
    "へ行って",
    "に行きたい",
    "カラオケデート",
    "went to karaoke",
    "karaoke trip",
    "karaoke date",
)

# Weaker performance hints — accepted only for archived streams, not ordinary
# uploads. These cover real titles observed in the production archive without
# treating every mention of 「歌」 as a singing stream.
_WEAK_KARAOKE_KEYWORDS: tuple[str, ...] = (
    "singing",
    "sing",
    "歌う",
    "歌います",
    "歌いたい",
    "歌いまく",
    "歌って",
    "うたう",
    "うたって",
    "うたいた",
    "唱歌",
    "歌雜",
    "歌杂",
)

# Standalone song / MV / cover uploads — never scrape setlist comments.
_SONG_KEYWORDS: tuple[str, ...] = (
    "mv",
    "cover",
    "covered by",
    "music video",
    "official audio",
    "original song",
    "歌ってみた",
    "歌って踊ってみた",
    "オリジナル曲",
    "official music video",
    "カバー",
    "翻唱",
    "カバー曲",
    "オリ曲",
    "原創曲",
    "原创曲",
    "テーマソング",
    "主題曲",
    "主题曲",
)

# English original-song uploads often use a bare bracketed/parenthesized
# ``Original`` instead of the phrase ``original song``.
_SONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:【|\[)\s*original\s*(?:】|\])", flags=re.IGNORECASE),
    re.compile(r"\(\s*original\s*\)", flags=re.IGNORECASE),
    re.compile(
        r"(?<![a-z])original(?:\s+[\w-]+){0,2}\s+song(?![a-z])",
        flags=re.IGNORECASE,
    ),
    re.compile(r"[/／]\s*original\s*(?:】|\])", flags=re.IGNORECASE),
)

# 3D concerts/lives are multi-song vocal performances and use the same setlist
# extraction path as karaoke archives. Requiring the marker inside brackets
# avoids recap/watchalong titles that merely mention a 3D live.
_BRACKETED_PERFORMANCE_RE = re.compile(
    r"(?:【|\[)[^】\]\r\n]{0,80}"
    r"(?:[3３]\s*[dｄＤ]\s*(?:live|concert)|[3３]\s*[dｄＤ]live)"
    r"[^】\]\r\n]{0,80}(?:】|\])",
    flags=re.IGNORECASE,
)
_PERFORMANCE_EXCLUDE_RE = re.compile(
    r"(?:"
    r"\bwatch(?:along|party)\b|\bwatch\b.*\b(?:together|same\s+time)\b|"
    r"振り返り|recap|after\s*talk|アフタートーク|"
    r"直前(?:トーク|雑談)"
    r")",
    flags=re.IGNORECASE,
)
_NON_SINGING_TOPIC_RE = re.compile(
    r"(?:セトリ|set\s*list)\s*(?:を)?\s*(?:決め|考え|組)",
    flags=re.IGNORECASE,
)
_SINGER_SKILL_HASHTAG_RE = re.compile(r"#?歌うま")

# Some creators append ``【KARAOKE/Vsinger[/Vtuber]】`` as a role/category
# boilerplate even on games, talk, and watchalong streams. Only suppress that
# suffix when the remaining title has an explicit non-singing activity and no
# independent singing marker.
_TRAILING_KARAOKE_ROLE_RE = re.compile(
    r"【\s*karaoke\s*/\s*v?singer"
    r"(?:\s*/\s*vtuber)?\s*】",
    flags=re.IGNORECASE,
)
_NON_SINGING_ACTIVITY_RE = re.compile(
    r"(?:"
    r"同時視聴|watch\s*(?:along|party)|"
    r"(?<![a-z])talk(?![a-z])|雑談|スパチャ読み|"
    r"トモコレ|it\s+takes\s+two|ゲーム実況|"
    r"振り返り"
    r")",
    flags=re.IGNORECASE,
)

VIDEO_TYPE_KARAOKE = "karaoke"
VIDEO_TYPE_SONG = "song"
VIDEO_TYPE_OTHER = "other"

# yt-dlp statuses that are not safe archive records. ``post_live`` is the
# short processing window after a broadcast ends; comments/duration may still
# be incomplete, so discovery waits for ``was_live``.
ACTIVE_LIVE_STATUSES = frozenset({"is_live", "is_upcoming", "post_live"})

# Karaoke streams are usually long; short clips with karaoke words are not archives.
KARAOKE_MIN_DURATION_SECONDS = 20 * 60

# Standalone song / MV / cover uploads are usually short.
SONG_MAX_DURATION_SECONDS = 10 * 60


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


def is_karaoke_outing_title(title: str) -> bool:
    """True for 'went to karaoke' style titles (not stream archives)."""
    if not title:
        return False
    folded = title.casefold()
    return any(phrase.casefold() in folded for phrase in _KARAOKE_EXCLUDE_PHRASES)


def is_strong_karaoke_title(title: str) -> bool:
    """True for karaoke *stream* titles; excludes karaoke outing vlogs."""
    if not title:
        return False
    # 歌枠 / 歌回 still win even if the title also jokes about 行ってみた.
    has_definitive = _title_has_any(title, ("歌枠", "歌回", "歌配信"))
    if is_karaoke_outing_title(title) and not has_definitive:
        return False
    bracketed_performance = (
        _BRACKETED_PERFORMANCE_RE.search(title) is not None
        and _PERFORMANCE_EXCLUDE_RE.search(title) is None
    )
    return _title_has_any(title, _STRONG_KARAOKE_KEYWORDS) or bracketed_performance


def is_weak_karaoke_title(title: str) -> bool:
    if is_karaoke_outing_title(title):
        return False
    if _NON_SINGING_TOPIC_RE.search(title):
        return False
    content_title = _SINGER_SKILL_HASHTAG_RE.sub("", title)
    return _title_has_any(content_title, _WEAK_KARAOKE_KEYWORDS)


def is_karaoke_title(title: str) -> bool:
    """True when the title looks like a karaoke / singing stream record."""
    return is_strong_karaoke_title(title) or is_weak_karaoke_title(title)


def is_song_title(title: str) -> bool:
    """True when the title looks like a standalone song / MV / cover."""
    return _title_has_any(title, _SONG_KEYWORDS) or any(
        pattern.search(title) for pattern in _SONG_PATTERNS
    )


def is_non_singing_branded_title(title: str) -> bool:
    """True when a trailing karaoke role tag conflicts with the real topic."""
    if not title or _TRAILING_KARAOKE_ROLE_RE.search(title) is None:
        return False
    content_title = _TRAILING_KARAOKE_ROLE_RE.sub(" ", title)
    has_independent_singing_marker = (
        _title_has_any(content_title, _STRONG_KARAOKE_KEYWORDS)
        or _title_has_any(content_title, _WEAK_KARAOKE_KEYWORDS)
        or _BRACKETED_PERFORMANCE_RE.search(content_title) is not None
    )
    return (
        not has_independent_singing_marker
        and _NON_SINGING_ACTIVITY_RE.search(content_title) is not None
    )


def _karaoke_live_status_ok(live_status: str | None) -> bool:
    """Soft confirm for *weak* karaoke only: unknown OK; known non-archives rejected.

    Strong title markers (歌枠 / KARAOKE / …) do not use this — Videos-tab VODs
    and reuploads are often ``not_live`` even when they are karaoke archives.
    """
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


def _song_duration_ok(duration: float | int | None) -> bool:
    """Soft confirm: unknown OK; known long videos rejected.

    When duration is present, standalone songs must be shorter than
    ``SONG_MAX_DURATION_SECONDS`` (default 10 minutes).
    """
    if duration is None:
        return True
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return True
    return seconds <= SONG_MAX_DURATION_SECONDS


def is_song_video(
    title: str,
    *,
    duration: float | int | None = None,
) -> bool:
    """Standalone song/MV/cover: title keywords + soft short-duration confirm."""
    return is_song_title(title) and _song_duration_ok(duration)


def is_karaoke_stream(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
) -> bool:
    """True only for karaoke stream archives worth setlist comment scraping.

    Priority:
    1. Strong stream/performance keywords (歌枠 / KARAOKE / 弾き語り /
       bracketed 3D LIVE / …) + soft duration confirm (``live_status`` is
       ignored — strong titles are reliable enough)
    2. Song/MV/cover keywords → never karaoke (no comment scrape)
    3. Weak singing phrases + soft ``was_live`` / duration confirms

    Outing titles like 「カラオケ行ってみた」 are excluded.
    """
    if (live_status or "").casefold() in ACTIVE_LIVE_STATUSES:
        return False
    if not _karaoke_duration_ok(duration):
        return False
    if is_non_singing_branded_title(title):
        return False
    if is_strong_karaoke_title(title):
        return True
    if is_song_title(title):
        return False
    if not _karaoke_live_status_ok(live_status):
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
    return is_karaoke_stream(title, live_status=live_status, duration=duration)


def classify_video_type(
    title: str,
    *,
    live_status: str | None = None,
    duration: float | int | None = None,
) -> str:
    """Return ``karaoke``, ``song``, or ``other``.

    Karaoke: strong stream/performance keywords + soft ``>= 20 min`` when
    duration is known. Weak singing phrases also need soft ``was_live``.
    Song: MV/cover/official/… keywords + soft ``< 10 min``.
    Missing duration does not block either class (flat-extract gaps).
    """
    if is_karaoke_stream(title, live_status=live_status, duration=duration):
        return VIDEO_TYPE_KARAOKE
    if is_song_video(title, duration=duration):
        return VIDEO_TYPE_SONG
    return VIDEO_TYPE_OTHER
