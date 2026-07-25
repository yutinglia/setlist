"""Detect setlist comments and extract songs from timestamped lines."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from models.song import Song
from utils.youtube_timestamp import timestamp_to_seconds

logger = logging.getLogger(__name__)

# Cumulative mm:ss or hh:mm:ss (after normalizing full-width colons).
# Validation is completed by ``timestamp_to_seconds``.
_TIMESTAMP_RE = re.compile(
    r"(?<![\d:])(?:\d{1,3}:\d{1,2}:\d{2}|\d{1,4}:\d{2})(?![\d:])"
)

# Separators commonly placed around timestamps in setlist comments
_SEPARATORS = r"[-~～–—|｜・·／/\s]+"

# Leading list numbers: "01. ", "1) ", "1、", "(1) ", "[1] "
# Do not treat "1:23" as numbering (colon is reserved for timestamps).
_NUMBERING_RE = re.compile(
    r"^(?:"
    r"[(\[【]\d+[)\]】]|"
    r"\d+[.)\]、．]"
    r")\s*"
)

# Some excellent community comments contain a clean setlist followed by a
# general stream chapter list. When a setlist heading is explicit, keep that
# section and stop at the next clearly non-setlist heading.
_SETLIST_HEADER_RE = re.compile(
    r"(?:set\s*list|setlist|song\s*list|track\s*list|tracklist|"
    r"セトリ|セットリスト|曲目|歌った曲)",
    flags=re.IGNORECASE,
)
_NON_SETLIST_HEADER_RE = re.compile(
    r"(?:配信内容|配信チャプター|チャプター|chapters?|stream\s+contents?)",
    flags=re.IGNORECASE,
)
_TITLE_CHAR_RE = re.compile(r"[\w\u3040-\u30ff\u3400-\u9fff]")


class CommentAnalyzer:
    """Pick the best setlist comment and parse timestamped song lines.

    Selection preference (highest first): pinned → uploader → timestamp count → likes.
    Within one extract, songs are deduped by
    ``(timestamp, casefold(title))``; first wins.
    """

    def __init__(
        self,
        comments: list[dict[str, Any]],
        video_id: str,
        minimum_timestamp_count: int = 3,
    ) -> None:
        self.minimum_timestamp_count: int = max(1, minimum_timestamp_count)
        self.video_id: str = video_id
        self.comments: list[dict[str, Any]] = comments
        self.has_song_list: bool = False
        self.song_list_comment: dict[str, Any] | None = None
        self.song_list: list[Song] = []

    def has_song_list_comment(self) -> bool:
        logger.debug(
            "Analyzing %s comments for video %s", len(self.comments), self.video_id
        )

        self.has_song_list = False
        self.song_list_comment = None
        self.song_list = []

        best: tuple[tuple[int, int, int, int], dict[str, Any]] | None = None
        for comment in self.comments:
            if not isinstance(comment, dict):
                continue
            text = self._comment_text(comment)
            if not self._contains_timestamp(text):
                continue
            score = self._score_comment(comment, text)
            if best is None or score > best[0]:
                best = (score, comment)

        if best is None:
            return False

        self.has_song_list = True
        self.song_list_comment = best[1]
        logger.info(
            "Song list comment found for video %s (score pinned=%s uploader=%s)",
            self.video_id,
            best[0][0],
            best[0][1],
        )
        return True

    def _score_comment(
        self, comment: dict[str, Any], text: str
    ) -> tuple[int, int, int, int]:
        """Higher is better: pinned, uploader, timestamp density, likes."""
        pinned = 1 if comment.get("is_pinned") else 0
        uploader = 1 if comment.get("author_is_uploader") else 0
        ts_count = len(self._timestamp_matches(text))
        likes = self._coerce_like_count(comment.get("like_count"))
        return (pinned, uploader, ts_count, likes)

    def _contains_timestamp(self, text: str) -> bool:
        matches = self._timestamp_matches(text)
        return len(matches) >= self.minimum_timestamp_count

    @staticmethod
    def _timestamp_matches(text: str) -> list[re.Match[str]]:
        return [
            match
            for match in _TIMESTAMP_RE.finditer(text)
            if timestamp_to_seconds(match.group(0)) is not None
        ]

    @staticmethod
    def _coerce_like_count(value: Any) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            try:
                numeric = float(value)
                return max(0, int(numeric)) if math.isfinite(numeric) else 0
            except (OverflowError, ValueError):
                return 0
        if not isinstance(value, str):
            return 0
        text = value.strip().lower().replace(",", "")
        multiplier = 1
        if text.endswith("k"):
            multiplier, text = 1_000, text[:-1]
        elif text.endswith("m"):
            multiplier, text = 1_000_000, text[:-1]
        try:
            numeric = float(text) * multiplier
            return max(0, int(numeric)) if math.isfinite(numeric) else 0
        except (OverflowError, ValueError):
            return 0

    @staticmethod
    def _normalize_text(text: str) -> str:
        # Full-width colon → ASCII so one timestamp regex covers JP setlists
        return text.replace("：", ":")

    @classmethod
    def _comment_text(cls, comment: dict[str, Any]) -> str:
        text = comment.get("text")
        return cls._normalize_text(text) if isinstance(text, str) else ""

    def extract_song_list(self) -> list[Song]:
        if not self.has_song_list or not self.song_list_comment:
            return []

        text = self._comment_text(self.song_list_comment)
        self.song_list = self.extract_from_text(text)
        return self.song_list

    def extract_from_text(
        self,
        text: str,
        *,
        analyzed_by_llm: bool = False,
    ) -> list[Song]:
        """Parse songs from arbitrary setlist text (regex path or LLM-cleaned)."""
        if not isinstance(text, str):
            logger.warning(
                "Ignoring non-string setlist text for video %s", self.video_id
            )
            return []
        songs: list[Song] = []
        lines = self._song_section_lines(self._normalize_text(text).splitlines())
        for line in lines:
            parsed = self._parse_song_line(line)
            for song in parsed:
                if analyzed_by_llm:
                    song.analyzed_by_llm = True
                songs.append(song)
        return self._dedupe_songs(songs)

    @staticmethod
    def _song_section_lines(lines: list[str]) -> list[str]:
        """Keep an explicit setlist section out of a mixed setlist/chapter post."""
        start: int | None = None
        inline_first_line: str | None = None
        for index, line in enumerate(lines):
            header = _SETLIST_HEADER_RE.search(line)
            if header:
                start = index + 1
                suffix = line[header.end() :]
                if _TIMESTAMP_RE.search(suffix):
                    inline_first_line = suffix
                break
        if start is None:
            return lines

        end = len(lines)
        for index in range(start, len(lines)):
            if _NON_SETLIST_HEADER_RE.search(lines[index]):
                end = index
                break
        section = lines[start:end]
        return [inline_first_line, *section] if inline_first_line else section

    def _parse_song_line(self, line: str) -> list[Song]:
        line = line.strip()
        if not line:
            return []

        line = _NUMBERING_RE.sub("", line, count=1).strip()
        if not line:
            return []

        matches = self._timestamp_matches(line)
        if not matches:
            return []

        if len(matches) == 1:
            match = matches[0]
            song = self._song_from_timestamp_parts(
                match.group(0),
                line[: match.start()],
                line[match.end() :],
            )
            return [song] if song is not None else []

        # Compact comments sometimes put an entire setlist on one line:
        # ``0:10 A | 3:20 B`` or ``A 0:10 | B 3:20``. Detect orientation
        # from meaningful text before the first timestamp and parse each entry.
        prefix, _ = self._clean_timestamp_parts(line[: matches[0].start()], "")
        title_before = bool(_TITLE_CHAR_RE.search(prefix)) and not bool(
            _SETLIST_HEADER_RE.search(prefix)
        )
        songs: list[Song] = []
        for index, match in enumerate(matches):
            if title_before:
                previous_end = matches[index - 1].end() if index else 0
                before = line[previous_end : match.start()]
                after = ""
            else:
                next_start = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(line)
                )
                before = ""
                after = line[match.end() : next_start]
            song = self._song_from_timestamp_parts(
                match.group(0),
                before,
                after,
            )
            if song is not None:
                songs.append(song)
        return songs

    @staticmethod
    def _clean_timestamp_parts(before: str, after: str) -> tuple[str, str]:
        before = before.strip()
        after = after.strip()

        # Drop brackets that wrapped the timestamp: "(1:23)", "【1:23】", etc.
        before = re.sub(r"[(\[【（]+$", "", before).strip()
        after = re.sub(r"^[)\]】）]+", "", after).strip()

        before = re.sub(rf"^{_SEPARATORS}|{_SEPARATORS}$", "", before).strip()
        after = re.sub(rf"^{_SEPARATORS}|{_SEPARATORS}$", "", after).strip()
        return before, after

    def _song_from_timestamp_parts(
        self,
        timestamp: str,
        before: str,
        after: str,
    ) -> Song | None:
        before, after = self._clean_timestamp_parts(before, after)
        # Prefer title after timestamp; fall back to title before
        # (covers "1:23 Title", "Title - 1:23", "01. Title 0:12:00").
        title = after or before
        if not title:
            return None

        # Reject titles that are only leftover punctuation / separators
        if not _TITLE_CHAR_RE.search(title):
            return None
        if len(title) > 500:
            title = title[:500].rstrip()
            if not title:
                return None

        return Song(title=title, timestamp=timestamp, video_id=self.video_id)

    @staticmethod
    def _dedupe_songs(songs: list[Song]) -> list[Song]:
        """Keep first occurrence of each (timestamp, casefold(title))."""
        seen: set[tuple[str, str]] = set()
        out: list[Song] = []
        for song in songs:
            key = (song.timestamp or "", (song.title or "").casefold().strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(song)
        return out
