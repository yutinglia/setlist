"""Detect setlist comments and extract songs from timestamped lines."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
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
_LEADING_SEPARATORS = r"[-~～〜–—|｜・·／/\s]+"

# Leading list numbers: "01. ", "1) ", "1、", "(1) ", "[1] ", "① "
# Do not treat "1:23" as numbering (colon is reserved for timestamps).
_NUMBERING_RE = re.compile(
    r"^(?:"
    r"[(\[【]\d+[)\]】]|"
    r"[①-⑳㉑-㉟㊱-㊿]|"
    r"\d+\s*[.)\]、．]|"
    r"#\d+(?:\s+|[.)\]、．]\s*)|"
    r"(?:ex|encore)\s*[.)\]、．:]"
    r")\s*",
    flags=re.IGNORECASE,
)
_CIRCLED_NUMBER_CHARS = frozenset(
    "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿"
)
_MIN_CONVENTIONAL_NUMBERED_ROWS = 5

# Some excellent community comments contain a clean setlist followed by a
# general stream chapter list. When a setlist heading is explicit, keep that
# section and stop at the next clearly non-setlist heading.
_LEGACY_SETLIST_HEADER_RE = re.compile(
    r"(?:set\s*list|setlist|song\s*list|track\s*list|tracklist|"
    r"セトリ|セットリスト|曲目|歌った曲)",
    flags=re.IGNORECASE,
)
_SETLIST_HEADER_RE = re.compile(
    r"(?:set\s*list|setlist|song\s*list|track\s*list|tracklist|"
    r"set\s*rest|"
    r"セトリ|セットリスト|曲目|歌った曲|"
    r"歌單(?:時間軸(?:在此|如下)?)?|歌单(?:时间轴(?:在此|如下)?)?)",
    flags=re.IGNORECASE,
)
_NON_SETLIST_HEADER_RE = re.compile(
    r"(?:"
    r"(?:other|more)\s+(?:time\s*stamps?|chapters?)|"
    r"talk\s*part|"
    r"announcements?|"
    r"配信内容|配信チャプター|チャプター|その他の?タイムスタンプ|"
    r"告知|お知らせ|雑談(?:など)?|"
    r"chapters?|stream\s+contents?"
    r")",
    flags=re.IGNORECASE,
)
_SETLIST_PREFACE_RE = re.compile(
    r"(?:後ろ|後半|下(?:記|方)|以下|later|below|after(?:wards)?|following)",
    flags=re.IGNORECASE,
)
_SECTION_DIVIDER_RE = re.compile(r"^\s*[-_=─━—~～・･*＊#＃]{3,}\s*$")
_SETLIST_CONTINUATION_HEADER_RE = re.compile(
    r"(?:encore|アンコール|安可|앵콜)",
    flags=re.IGNORECASE,
)
_TITLE_CHAR_RE = re.compile(r"[\w\u3040-\u30ff\u3400-\u9fff]")
_CUSTOM_EMOJI_RE = re.compile(r":[\w+-]{2,}:")
_RANGE_SEPARATOR_RE = re.compile(r"[-~～〜–—]")
_NON_SONG_ROW_RE = re.compile(
    r"^(?:"
    r"(?:【|\[|\()\s*(?:雑談|mc|talk|chat|告知|お知らせ|announcement)"
    r"\s*(?:】|\]|\))|"
    r"(?:雑談|告知|お知らせ|重大発表|タイトルコール|声入り)"
    r"(?:\s|[/／:：-]|$)|"
    r"(?:mc|talk|chat|announcement)(?:"
    r"\s*$|\s+\d+\s*$|\s*[/／:：-]|"
    r"\s+(?:part|time|section|break|segment|starts?|ends?|chat(?:ting)?)\b"
    r")|"
    r"(?:intro|outro)(?:\s*\+\s*(?:superchat\s+)?talk(?:\s+\d+)?)?\s*$|"
    r"(?:歌單|歌单)(?:不足|不完整|未完成|待補|待补)\s*$|"
    r".+(?:の)?(?:告知|お知らせ|announcement)\s*$|"
    r".+(?:info|いんふぉ|インフォ)\s*$"
    r")",
    flags=re.IGNORECASE,
)
_CHAPTER_ONLY_TITLE_RE = re.compile(
    r"(?:"
    r"(?:start|sᴛᴀʀᴛ|stream\s+start)"
    r"(?:\s*(?:[|｜/]|\()\s*(?:開始|配信開始|スタート)\s*\)?)?|"
    r"(?:開始|配信開始|スタート)"
    r"(?:\s*(?:[|｜/]|\()\s*(?:start|sᴛᴀʀᴛ|stream\s+start)\s*\)?)?|"
    r"ending?|stream\s+end|end|終了|配信終了|ed|outro|"
    r"bye(?:\s+bye)?|終わりの挨拶|声入り|voice\s+in|chat"
    r")",
    flags=re.IGNORECASE,
)
_CHAPTER_PREFIX_RE = re.compile(
    r"(?:開始|配信開始|start|stream\s+start)\s*[&＆]\s*",
    flags=re.IGNORECASE,
)
_ASCII_START_ONLY_TITLE_RE = re.compile(
    r"(?:start|sᴛᴀʀᴛ|stream\s+start)",
    flags=re.IGNORECASE,
)
_EARLY_CHAPTER_MAX_SECONDS = 10 * 60
_TIMESTAMP_REGRESSION_TOLERANCE_SECONDS = 60


class CommentAnalyzer:
    """Pick the best setlist comment and parse timestamped song lines.

    Selection preference (highest first): pinned → uploader → parsed songs → likes.
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

        best: tuple[tuple[int, int, int, int], dict[str, Any], list[Song]] | None = None
        for comment in self.comments:
            if not isinstance(comment, dict):
                continue
            text = self._comment_text(comment)
            songs = self.extract_from_text(text)
            # Two real songs are enough when the author explicitly labels the
            # section as a setlist. Unlabelled timestamp clusters keep the
            # normal (default three-song) threshold to reject chat chapters.
            explicit_two_song_setlist = len(songs) >= 2 and (
                self._has_explicit_setlist_header(text)
            )
            if (
                len(songs) < self.minimum_timestamp_count
                and not explicit_two_song_setlist
            ):
                continue
            score = self._score_comment(comment, len(songs))
            if best is None or score > best[0]:
                best = (score, comment, songs)

        if best is None:
            return False

        self.has_song_list = True
        self.song_list_comment = best[1]
        self.song_list = best[2]
        logger.info(
            "Song list comment found for video %s "
            "(score pinned=%s uploader=%s songs=%s)",
            self.video_id,
            best[0][0],
            best[0][1],
            best[0][2],
        )
        return True

    def _score_comment(
        self, comment: dict[str, Any], song_count: int
    ) -> tuple[int, int, int, int]:
        """Higher is better: pinned, uploader, parsed songs, likes."""
        pinned = 1 if comment.get("is_pinned") else 0
        uploader = 1 if comment.get("author_is_uploader") else 0
        likes = self._coerce_like_count(comment.get("like_count"))
        return (pinned, uploader, song_count, likes)

    @staticmethod
    def _timestamp_matches(text: str) -> list[re.Match[str]]:
        return [
            match
            for match in _TIMESTAMP_RE.finditer(text)
            if timestamp_to_seconds(match.group(0)) is not None
            and re.match(
                r"\s*(?:a\.?m\.?|p\.?m\.?)\b",
                text[match.end() :],
                flags=re.IGNORECASE,
            )
            is None
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
        # Full-width colon → ASCII so one timestamp regex covers JP setlists.
        # Zero-width characters frequently precede copied YouTube timestamps.
        return text.replace("：", ":").replace("\u200b", "").replace("\ufeff", "")

    @classmethod
    def _searchable_text(cls, text: str) -> str:
        """Normalize decorative Unicode only for heading classification."""
        return unicodedata.normalize("NFKC", cls._normalize_text(text))

    @classmethod
    def _has_explicit_setlist_header(cls, text: str) -> bool:
        if _LEGACY_SETLIST_HEADER_RE.search(text) is not None:
            return True
        return any(cls._is_setlist_header_line(line) for line in text.splitlines())

    @classmethod
    def _comment_text(cls, comment: dict[str, Any]) -> str:
        text = comment.get("text")
        return cls._normalize_text(text) if isinstance(text, str) else ""

    def extract_song_list(self) -> list[Song]:
        if not self.has_song_list or not self.song_list_comment:
            return []
        if self.song_list:
            return self.song_list

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
        lines, explicit_section = self._song_section_lines(
            self._normalize_text(text).splitlines()
        )
        if not explicit_section:
            # Community setlists often number only the song rows while mixing
            # them with an unnumbered chapter list. Once enough numbered,
            # timestamped rows exist, that is a stronger signal than every
            # timestamp in the comment. Also support a numbered title followed
            # by its timestamp on the next line.
            combined_lines = self._combine_split_title_timestamps(lines)
            numbered_lines = [
                line
                for line in combined_lines
                if self._is_numbered_timestamp_line(line)
                and self._parse_song_line(line)
            ]
            has_circled_numbering = any(
                not _CIRCLED_NUMBER_CHARS.isdisjoint(line) for line in numbered_lines
            )
            numbered_threshold = (
                self.minimum_timestamp_count
                if has_circled_numbering
                else max(
                    self.minimum_timestamp_count,
                    _MIN_CONVENTIONAL_NUMBERED_ROWS,
                )
            )
            if len(numbered_lines) >= numbered_threshold:
                lines = numbered_lines
        latest_timestamp_seconds: int | None = None
        for line in lines:
            parsed = self._parse_song_line(line)
            for song in parsed:
                timestamp_seconds = timestamp_to_seconds(song.timestamp)
                if (
                    explicit_section
                    and len(songs) >= 2
                    and timestamp_seconds is not None
                    and latest_timestamp_seconds is not None
                    and timestamp_seconds
                    < latest_timestamp_seconds - _TIMESTAMP_REGRESSION_TOLERANCE_SECONDS
                ):
                    logger.debug(
                        "Stopping explicit setlist for video %s at "
                        "out-of-order timestamp %s",
                        self.video_id,
                        song.timestamp,
                    )
                    return self._dedupe_songs(songs)
                if analyzed_by_llm:
                    song.analyzed_by_llm = True
                songs.append(song)
                if timestamp_seconds is not None:
                    latest_timestamp_seconds = max(
                        latest_timestamp_seconds or 0,
                        timestamp_seconds,
                    )
        return self._dedupe_songs(songs)

    @classmethod
    def _song_section_lines(cls, lines: list[str]) -> tuple[list[str], bool]:
        """Keep an explicit setlist section out of a mixed setlist/chapter post."""
        start, inline_first_line = cls._find_setlist_section_start(lines)
        if start is None:
            return lines, False

        section: list[str] = []
        saw_timestamp = inline_first_line is not None
        for index in range(start, len(lines)):
            line = lines[index]
            line_timestamps = cls._timestamp_matches(line)
            action = cls._setlist_section_line_action(
                lines,
                index,
                saw_timestamp=saw_timestamp,
                line_timestamps=line_timestamps,
            )
            if action == "stop":
                break
            if action == "skip":
                continue
            section.append(line)
            saw_timestamp = saw_timestamp or bool(line_timestamps)
        if inline_first_line:
            section.insert(0, inline_first_line)
        return cls._combine_split_title_timestamps(section), True

    @classmethod
    def _find_setlist_section_start(
        cls,
        lines: list[str],
    ) -> tuple[int | None, str | None]:
        # Preserve the established parser's first plain-text header choice.
        # The enhanced Unicode/locale-aware matcher is a fallback so a later
        # translated header cannot replace an already-valid original section.
        for index, line in enumerate(lines):
            header = _LEGACY_SETLIST_HEADER_RE.search(line)
            if header is not None:
                suffix = line[header.end() :]
                inline = suffix if cls._timestamp_matches(suffix) else None
                return index + 1, inline
        for index, line in enumerate(lines):
            if cls._is_setlist_header_line(line):
                timestamp = next(iter(cls._timestamp_matches(line)), None)
                inline = line[timestamp.start() :] if timestamp is not None else None
                return index + 1, inline
        return None, None

    @classmethod
    def _setlist_section_line_action(
        cls,
        lines: list[str],
        index: int,
        *,
        saw_timestamp: bool,
        line_timestamps: list[re.Match[str]],
    ) -> str:
        line = lines[index]
        searchable = cls._searchable_text(line)
        if saw_timestamp and cls._is_setlist_header_line(line):
            return "stop"
        if _NON_SETLIST_HEADER_RE.search(searchable):
            if saw_timestamp:
                return "stop"
            if not line_timestamps:
                return (
                    "skip"
                    if _SETLIST_PREFACE_RE.search(searchable) is not None
                    else "stop"
                )
        if (
            saw_timestamp
            and _SECTION_DIVIDER_RE.fullmatch(line)
            and cls._divider_ends_song_section(lines, index)
        ):
            return "stop"
        return "keep"

    @classmethod
    def _is_setlist_header_line(cls, line: str) -> bool:
        searchable = cls._searchable_text(line)
        header = _SETLIST_HEADER_RE.search(searchable)
        if header is None:
            return False
        # Japanese song rows commonly start with ``2曲目 10:17 ...``.
        # ``曲目`` can also mean a setlist heading in Chinese, so only reject
        # it here when it is directly used as an ordinal song label.
        if re.search(
            r"(?:\d+|[一二三四五六七八九十百]+)\s*曲目\s*$",
            searchable[: header.end()],
        ):
            return False
        timestamps = cls._timestamp_matches(line)
        if timestamps:
            first_timestamp = timestamps[0]
            # Inline headings are valid only when the heading introduces the
            # timestamp. A chapter such as ``1:11:26 歌單不足`` merely mentions
            # the word after its timestamp and must not hide earlier songs.
            if header.start() > first_timestamp.start():
                return False
            between = searchable[header.end() : first_timestamp.start()]
            between = _CUSTOM_EMOJI_RE.sub(" ", between)
            between = re.sub(r"[-_=─━—~～・･*＊#＃♪♫♩:：\s]+", "", between)
            return not bool(_TITLE_CHAR_RE.search(between))

        prefix = _CUSTOM_EMOJI_RE.sub(" ", searchable[: header.start()])
        prefix = re.sub(r"[-_=─━—~～・･*＊#＃♪♫♩\s]+", "", prefix)
        if _TITLE_CHAR_RE.search(prefix):
            return False

        suffix = searchable[header.end() :].strip()
        # A late prose remark such as 「セトリで見ると…」 is not a section
        # heading and must not hide timestamp rows that came before it.
        if re.match(r"^(?:で|を|の|が|は|について)", suffix):
            return False
        return True

    @classmethod
    def _combine_split_title_timestamps(cls, lines: list[str]) -> list[str]:
        """Join numbered title rows whose timestamp is on the following line."""
        combined: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if not cls._is_numbered_title_only_line(line):
                combined.append(line)
                index += 1
                continue

            next_index = index + 1
            while next_index < len(lines) and not lines[next_index].strip():
                next_index += 1
            if next_index >= len(lines) or not cls._is_timestamp_only_line(
                lines[next_index]
            ):
                combined.append(line)
                index += 1
                continue

            combined.append(f"{line.strip()} {lines[next_index].strip()}")
            index = next_index + 1
        return combined

    @classmethod
    def _is_numbered_title_only_line(cls, line: str) -> bool:
        normalized = cls._normalize_text(line).strip()
        if not normalized or cls._timestamp_matches(normalized):
            return False
        if _NUMBERING_RE.match(normalized) is None:
            return False
        title = _NUMBERING_RE.sub("", normalized, count=1).strip()
        return bool(_TITLE_CHAR_RE.search(title))

    @classmethod
    def _is_timestamp_only_line(cls, line: str) -> bool:
        normalized = cls._normalize_text(line).strip()
        matches = cls._timestamp_matches(normalized)
        if len(matches) != 1:
            return False
        match = matches[0]
        remainder = normalized[: match.start()] + normalized[match.end() :]
        remainder = _CUSTOM_EMOJI_RE.sub("", remainder)
        remainder = re.sub(r"[()\[\]【】「」『』\s]", "", remainder)
        return not remainder

    @classmethod
    def _is_numbered_timestamp_line(cls, line: str) -> bool:
        """Return whether a timestamped row has numbering before its title."""
        normalized = cls._normalize_text(line).strip()
        matches = cls._timestamp_matches(normalized)
        if not matches:
            return False
        if _NUMBERING_RE.match(normalized) is not None:
            return True

        # Also accept YouTube's common ``0:10 ① Song`` layout.
        after_timestamp = normalized[matches[0].end() :]
        _, after_timestamp = cls._clean_timestamp_parts("", after_timestamp)
        return _NUMBERING_RE.match(after_timestamp) is not None

    @classmethod
    def _divider_ends_song_section(cls, lines: list[str], index: int) -> bool:
        """Allow decorative dividers before an encore or more song rows."""
        for candidate in lines[index + 1 :]:
            candidate = candidate.strip()
            if not candidate:
                continue
            if _SETLIST_CONTINUATION_HEADER_RE.search(candidate):
                return False
            if _SETLIST_HEADER_RE.search(candidate):
                return False
            return not cls._line_has_timestamp_title(candidate)
        return True

    @classmethod
    def _line_has_timestamp_title(cls, line: str) -> bool:
        """Cheap look-ahead check used only to classify section dividers."""
        matches = cls._timestamp_matches(line)
        if not matches:
            return False
        remainder = _NUMBERING_RE.sub("", line, count=1)
        for match in reversed(cls._timestamp_matches(remainder)):
            remainder = remainder[: match.start()] + " " + remainder[match.end() :]
        remainder = _CUSTOM_EMOJI_RE.sub(" ", remainder)
        remainder = re.sub(r"[\[\]【】（）()「」『』]", " ", remainder)
        remainder = re.sub(_SEPARATORS, " ", remainder)
        remainder = re.sub(r"\s+", " ", remainder).strip()
        remainder = cls._strip_decorative_edges(remainder)
        if not _TITLE_CHAR_RE.search(remainder):
            return False
        if _NON_SONG_ROW_RE.match(remainder):
            return False
        return _CHAPTER_ONLY_TITLE_RE.fullmatch(remainder) is None

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

        ranged = self._song_from_timestamp_range(line, matches)
        if ranged is not None:
            return [ranged]

        # Compact comments sometimes put an entire setlist on one line:
        # ``0:10 A | 3:20 B`` or ``A 0:10 | B 3:20``. Detect orientation
        # from meaningful text before the first timestamp and parse each entry.
        prefix, _ = self._clean_timestamp_parts(line[: matches[0].start()], "")
        prefix = _CUSTOM_EMOJI_RE.sub(" ", prefix).strip()
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

    def _song_from_timestamp_range(
        self,
        line: str,
        matches: list[re.Match[str]],
    ) -> Song | None:
        """Use a range's start while taking its title outside the two times."""
        if len(matches) != 2:
            return None
        first, second = matches
        between = line[first.end() : second.start()]
        searchable_between = _CUSTOM_EMOJI_RE.sub(" ", between)
        if _RANGE_SEPARATOR_RE.search(searchable_between) is None:
            return None
        if re.sub(_SEPARATORS, "", searchable_between).strip():
            return None

        before = _CUSTOM_EMOJI_RE.sub(" ", line[: first.start()])
        after = _CUSTOM_EMOJI_RE.sub(" ", line[second.end() :])
        return self._song_from_timestamp_parts(first.group(0), before, after)

    @staticmethod
    def _clean_timestamp_parts(before: str, after: str) -> tuple[str, str]:
        before = before.strip()
        after = after.strip()

        # Drop brackets that wrapped the timestamp: "(1:23)", "【1:23】", etc.
        before = re.sub(r"[(\[【（]+$", "", before).strip()
        after = re.sub(r"^[)\]】）]+", "", after).strip()

        before = re.sub(rf"^{_LEADING_SEPARATORS}|{_SEPARATORS}$", "", before).strip()
        after = re.sub(rf"^{_LEADING_SEPARATORS}|{_SEPARATORS}$", "", after).strip()
        return before, after

    @staticmethod
    def _strip_decorative_edges(title: str) -> str:
        """Strip emoji/symbol wrappers without removing normal punctuation."""
        start = 0
        end = len(title)
        cluster_categories = {"So", "Sk", "Mn", "Cf"}
        symbol_categories = {"So", "Sk"}

        while start < end:
            while start < end and title[start].isspace():
                start += 1
            cluster_end = start
            has_symbol = False
            while (
                cluster_end < end
                and unicodedata.category(title[cluster_end]) in cluster_categories
            ):
                has_symbol = (
                    has_symbol
                    or unicodedata.category(title[cluster_end]) in symbol_categories
                )
                cluster_end += 1
            if not has_symbol:
                break
            start = cluster_end

        while end > start:
            while end > start and title[end - 1].isspace():
                end -= 1
            cluster_start = end
            has_symbol = False
            while (
                cluster_start > start
                and unicodedata.category(title[cluster_start - 1]) in cluster_categories
            ):
                cluster_start -= 1
                has_symbol = (
                    has_symbol
                    or unicodedata.category(title[cluster_start]) in symbol_categories
                )
            if not has_symbol:
                break
            end = cluster_start
        return title[start:end].strip()

    def _song_from_timestamp_parts(
        self,
        timestamp: str,
        before: str,
        after: str,
    ) -> Song | None:
        before, after = self._clean_timestamp_parts(before, after)
        # Numbering appears on either side of a timestamp in real community
        # comments: ``1. Title 0:10`` and ``0:10 1. Title``.
        before = _NUMBERING_RE.sub("", before, count=1).strip()
        after = _NUMBERING_RE.sub("", after, count=1).strip()
        # Prefer title after timestamp; fall back to title before
        # (covers "1:23 Title", "Title - 1:23", "01. Title 0:12:00").
        title = after or before
        if not title:
            return None

        title = _CUSTOM_EMOJI_RE.sub(" ", title)
        title = _CHAPTER_PREFIX_RE.sub("", title, count=1).strip()
        title = _NUMBERING_RE.sub("", title, count=1).strip()
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(rf"^{_LEADING_SEPARATORS}", "", title).strip()
        title = re.sub(rf"{_SEPARATORS}$", "", title).strip()
        title = self._strip_decorative_edges(title)

        # Reject titles that are only leftover punctuation / separators
        if not _TITLE_CHAR_RE.search(title):
            return None
        if _NON_SONG_ROW_RE.match(title):
            return None
        if _CHAPTER_ONLY_TITLE_RE.fullmatch(title):
            timestamp_seconds = timestamp_to_seconds(timestamp)
            # Bare ``Start`` is also a real song title. Treat it as a chapter
            # only near the beginning; bilingual/CJK start and explicit end
            # labels remain unambiguous chapter rows at any position.
            is_late_song_named_start = (
                _ASCII_START_ONLY_TITLE_RE.fullmatch(title) is not None
                and timestamp_seconds is not None
                and timestamp_seconds > _EARLY_CHAPTER_MAX_SECONDS
            )
            if not is_late_song_named_start:
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
