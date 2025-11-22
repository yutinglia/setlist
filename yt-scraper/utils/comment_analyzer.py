from typing import Any
import re
from models.song import Song


# Regex pattern to match timestamps in the format mm:ss or hh:mm:ss
# Matches patterns like 00:06:46 or 1:23 at the start of timestamp position
youtube_timestamp_pattern = r"\d{1,2}:\d{2}(?::\d{2})?"


class CommentAnalyzer:
    def __init__(
        self, comments: list[dict[str, Any]], minimum_timestamp_count: int = 3
    ) -> None:
        # at least n timestamps to consider it a song list comment
        self.minimum_timestamp_count: int = minimum_timestamp_count
        self.comments: list[dict[str, Any]] = comments
        self.has_song_list: bool = False
        self.song_list_comment: dict[str, Any] | None = None
        self.song_list: list[Song] = []

    def has_song_list_comment(self) -> bool:
        # test
        print(f"Analyzing {len(self.comments)} comments...")

        for comment in self.comments:
            text: str = comment.get("text", "")
            if self._contains_timestamp(text):
                self.has_song_list = True
                self.song_list_comment = comment
                print("Song list comment found.")
                return True

        return False

    def _contains_timestamp(self, text: str) -> bool:
        # Check if the text has enough timestamps to be considered a song list
        matches = re.findall(youtube_timestamp_pattern, text)
        return len(matches) >= self.minimum_timestamp_count

    def extract_song_list(self) -> list[Song]:
        if not self.has_song_list or not self.song_list_comment:
            return []

        text: str = self.song_list_comment.get("text", "")
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove optional numbering at the start (e.g., "01. ")
            line = re.sub(r"^\d+\.?\s+", "", line)

            # Check if line contains a timestamp
            match = re.search(youtube_timestamp_pattern, line)
            if match:
                timestamp: str = match.group(0)
                # Extract the title which is the text after the timestamp
                title = line[match.end() :].strip()
                # Remove common separators at the start (-, ~, etc.)
                title = re.sub(r"^[-~\s]+", "", title)
                title = title.strip()

                if title:  # Only add if there's a valid title
                    song = Song(title=title, timestamp=timestamp)
                    self.song_list.append(song)

        return self.song_list
