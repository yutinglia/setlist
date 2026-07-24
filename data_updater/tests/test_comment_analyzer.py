import pytest

from services.analyzer.yt_comment_analyzer import CommentAnalyzer

VIDEO_ID = "test_video_abc"


def _comment(
    text: str,
    *,
    is_pinned: bool = False,
    author_is_uploader: bool = False,
    like_count: int = 1,
    author: str = "viewer",
) -> dict:
    return {
        "text": text,
        "author": author,
        "like_count": like_count,
        "is_pinned": is_pinned,
        "author_is_uploader": author_is_uploader,
    }


def _setlist(*lines: str) -> str:
    return "\n".join(lines)


class TestCommentAnalyzerDetection:
    def test_detects_pinned_style_multiline_setlist(self):
        text = _setlist(
            "00:01:23 曲A",
            "00:05:00 曲B",
            "00:12:34 曲C",
            "01:00:00 曲D",
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


class TestCommentPreference:
    def test_prefers_pinned_over_earlier_viewer_setlist(self):
        viewer = _comment(
            _setlist("0:10 A", "0:20 B", "0:30 C"),
            like_count=99,
        )
        pinned = _comment(
            _setlist("1:00 PinA", "2:00 PinB", "3:00 PinC"),
            is_pinned=True,
            like_count=1,
        )
        analyzer = CommentAnalyzer([viewer, pinned], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is True
        songs = analyzer.extract_song_list()
        assert songs[0].title == "PinA"

    def test_prefers_uploader_over_viewer_when_neither_pinned(self):
        viewer = _comment(
            _setlist("0:10 A", "0:20 B", "0:30 C"),
            like_count=50,
        )
        uploader = _comment(
            _setlist("1:00 UpA", "2:00 UpB", "3:00 UpC"),
            author_is_uploader=True,
            author="VTuber",
        )
        analyzer = CommentAnalyzer([viewer, uploader], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is True
        songs = analyzer.extract_song_list()
        assert songs[0].title == "UpA"

    def test_pinned_beats_uploader(self):
        uploader = _comment(
            _setlist("1:00 UpA", "2:00 UpB", "3:00 UpC"),
            author_is_uploader=True,
        )
        pinned = _comment(
            _setlist("4:00 PinA", "5:00 PinB", "6:00 PinC"),
            is_pinned=True,
        )
        analyzer = CommentAnalyzer([uploader, pinned], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is True
        assert analyzer.extract_song_list()[0].title == "PinA"


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

    def test_numbered_title_then_timestamp(self):
        songs = self._songs_from("01. Title 0:12:00")
        assert len(songs) == 1
        assert songs[0].title == "Title"
        assert songs[0].timestamp == "0:12:00"

    def test_numbered_title_dash_timestamp(self):
        songs = self._songs_from("1) 曲名 - 1:23")
        assert len(songs) == 1
        assert songs[0].title == "曲名"
        assert songs[0].timestamp == "1:23"

    def test_parenthesized_timestamp(self):
        songs = self._songs_from("(0:05:30) Stellar Stellar")
        assert len(songs) == 1
        assert songs[0].title == "Stellar Stellar"
        assert songs[0].timestamp == "0:05:30"

    def test_fullwidth_colon_timestamp(self):
        songs = self._songs_from("12：34 曲名")
        assert len(songs) == 1
        assert songs[0].timestamp == "12:34"
        assert songs[0].title == "曲名"

    def test_skips_empty_titles(self):
        text = _setlist("0:10", "0:20 有歌名", "0:30 ---")
        songs = self._songs_from(text)
        assert len(songs) == 1
        assert songs[0].title == "有歌名"

    def test_strips_numbering_prefix(self):
        songs = self._songs_from("01. 0:06:46 Song Title")
        assert len(songs) == 1
        assert songs[0].title == "Song Title"
        assert songs[0].timestamp == "0:06:46"

    def test_does_not_eat_timestamp_as_numbering(self):
        songs = self._songs_from("1:23 Real Title")
        assert len(songs) == 1
        assert songs[0].timestamp == "1:23"
        assert songs[0].title == "Real Title"

    def test_dedupes_identical_timestamp_and_title(self):
        text = _setlist(
            "0:10 Same",
            "0:10 Same",
            "0:20 Other",
            "0:10 same",  # casefold duplicate of first
        )
        songs = self._songs_from(text)
        assert [(s.timestamp, s.title) for s in songs] == [
            ("0:10", "Same"),
            ("0:20", "Other"),
        ]

    def test_keeps_same_timestamp_different_titles(self):
        text = _setlist("0:10 First", "0:10 Second")
        songs = self._songs_from(text)
        assert len(songs) == 2

    def test_extract_from_text_marks_llm(self):
        analyzer = CommentAnalyzer([], video_id=VIDEO_ID, minimum_timestamp_count=1)
        songs = analyzer.extract_from_text(
            "0:10 A\n0:20 B",
            analyzed_by_llm=True,
        )
        assert len(songs) == 2
        assert all(s.analyzed_by_llm for s in songs)

    def test_extract_without_detection_returns_empty(self):
        analyzer = CommentAnalyzer([_comment("nope")], video_id=VIDEO_ID)
        assert analyzer.extract_song_list() == []


class TestLlmCleanerSkip:
    @pytest.mark.asyncio
    async def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "services.analyzer.llm_cleaner.LLM_CLEANING_ENABLED", False
        )
        from services.analyzer.llm_cleaner import maybe_clean_song_list_comment

        assert await maybe_clean_song_list_comment("0:10 A\n0:20 B\n0:30 C") is None

    @pytest.mark.asyncio
    async def test_enabled_without_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "services.analyzer.llm_cleaner.LLM_CLEANING_ENABLED", True
        )
        monkeypatch.setattr("services.analyzer.llm_cleaner.LLM_API_KEY", "")
        from services.analyzer.llm_cleaner import maybe_clean_song_list_comment

        assert await maybe_clean_song_list_comment("0:10 A\n0:20 B\n0:30 C") is None
