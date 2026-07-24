import pytest

from services.analyzer.yt_comment_analyzer import CommentAnalyzer

VIDEO_ID = "test_video_abc"


def _comment(text: str) -> dict:
    return {"text": text, "author": "viewer", "like_count": 1}


class TestCommentAnalyzerDetection:
    def test_detects_pinned_style_multiline_setlist(self):
        text = "\n".join(
            [
                "00:01:23 曲A",
                "00:05:00 曲B",
                "00:12:34 曲C",
                "01:00:00 曲D",
            ]
        )
        analyzer = CommentAnalyzer([_comment(text)], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is True
        songs = analyzer.extract_song_list()
        assert len(songs) == 4
        assert all(s.video_id == VIDEO_ID for s in songs)
        assert songs[0].title == "曲A"
        assert songs[0].timestamp == "00:01:23"

    def test_no_timestamps_is_not_song_list(self):
        analyzer = CommentAnalyzer(
            [_comment("Great stream! Thank you!")],
            video_id=VIDEO_ID,
        )
        assert analyzer.has_song_list_comment() is False
        assert analyzer.extract_song_list() == []

    def test_too_few_timestamps_respects_minimum(self):
        text = "0:30 Intro\n1:00 Only two songs"
        analyzer = CommentAnalyzer(
            [_comment(text)],
            video_id=VIDEO_ID,
            minimum_timestamp_count=3,
        )
        assert analyzer.has_song_list_comment() is False

    def test_minimum_timestamp_count_configurable(self):
        text = "0:30 A\n1:00 B"
        analyzer = CommentAnalyzer(
            [_comment(text)],
            video_id=VIDEO_ID,
            minimum_timestamp_count=2,
        )
        assert analyzer.has_song_list_comment() is True


class TestCommentAnalyzerParsing:
    def _songs_from(self, text: str) -> list:
        analyzer = CommentAnalyzer(
            [_comment(text)],
            video_id=VIDEO_ID,
            minimum_timestamp_count=1,
        )
        assert analyzer.has_song_list_comment()
        return analyzer.extract_song_list()

    def test_title_after_timestamp(self):
        songs = self._songs_from("12:34 Hello World")
        assert len(songs) == 1
        assert songs[0].title == "Hello World"
        assert songs[0].timestamp == "12:34"
        assert songs[0].video_id == VIDEO_ID

    def test_title_before_timestamp(self):
        songs = self._songs_from("Hello World 12:34")
        assert len(songs) == 1
        assert songs[0].title == "Hello World"
        assert songs[0].timestamp == "12:34"

    def test_strips_separators_both_sides(self):
        songs = self._songs_from("12:34 - ~ 曲名 ～")
        assert len(songs) == 1
        assert songs[0].title == "曲名"

    def test_title_before_with_separator(self):
        songs = self._songs_from("曲名 - 1:23")
        assert len(songs) == 1
        assert songs[0].title == "曲名"
        assert songs[0].timestamp == "1:23"

    def test_skips_empty_titles(self):
        text = "\n".join(["0:10", "0:20 有歌名", "0:30 ---"])
        songs = self._songs_from(text)
        assert len(songs) == 1
        assert songs[0].title == "有歌名"

    def test_strips_numbering_prefix(self):
        songs = self._songs_from("01. 0:06:46 Song Title")
        assert len(songs) == 1
        assert songs[0].title == "Song Title"
        assert songs[0].timestamp == "0:06:46"

    def test_extract_without_detection_returns_empty(self):
        analyzer = CommentAnalyzer([_comment("nope")], video_id=VIDEO_ID)
        assert analyzer.extract_song_list() == []
