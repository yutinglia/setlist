from typing import Any
import logging
import re

from models.song import Song

logger = logging.getLogger(__name__)

# Regex pattern to match timestamps in the format mm:ss or hh:mm:ss
youtube_timestamp_pattern = r"\d{1,2}:\d{2}(?::\d{2})?"

# Separators commonly placed around timestamps in setlist comments
_SEPARATORS = r"[-~～–—|｜・·\s]+"


class CommentAnalyzer:
    def __init__(
        self,
        comments: list[dict[str, Any]],
        video_id: str,
        minimum_timestamp_count: int = 3,
    ) -> None:
        # at least n timestamps to consider it a song list comment
        self.minimum_timestamp_count: int = minimum_timestamp_count
        self.video_id: str = video_id
        self.comments: list[dict[str, Any]] = comments
        self.has_song_list: bool = False
        self.song_list_comment: dict[str, Any] | None = None
        self.song_list: list[Song] = []

    def has_song_list_comment(self) -> bool:
        logger.debug("Analyzing %s comments for video %s", len(self.comments), self.video_id)

        for comment in self.comments:
            text: str = comment.get("text", "")
            if self._contains_timestamp(text):
                self.has_song_list = True
                self.song_list_comment = comment
                logger.info("Song list comment found for video %s", self.video_id)
                return True

        return False

    def _contains_timestamp(self, text: str) -> bool:
        matches = re.findall(youtube_timestamp_pattern, text)
        return len(matches) >= self.minimum_timestamp_count

    def extract_song_list(self) -> list[Song]:
        if not self.has_song_list or not self.song_list_comment:
            return []

        text: str = self.song_list_comment.get("text", "")
        self.song_list = []

        for line in text.split("\n"):
            song = self._parse_song_line(line)
            if song is not None:
                self.song_list.append(song)

        return self.song_list

    def _parse_song_line(self, line: str) -> Song | None:
        line = line.strip()
        if not line:
            return None

        # Remove optional numbering at the start (e.g., "01. " or "1) ")
        line = re.sub(r"^\d+[.)、]\s*", "", line)

        match = re.search(youtube_timestamp_pattern, line)
        if not match:
            return None

        timestamp: str = match.group(0)
        before = line[: match.start()].strip()
        after = line[match.end() :].strip()

        # Strip separators on both sides of the timestamp
        before = re.sub(rf"^{_SEPARATORS}|{_SEPARATORS}$", "", before).strip()
        after = re.sub(rf"^{_SEPARATORS}|{_SEPARATORS}$", "", after).strip()

        # Prefer title after timestamp; fall back to title before
        title = after or before
        if not title:
            return None

        return Song(title=title, timestamp=timestamp, video_id=self.video_id)
