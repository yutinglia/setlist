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

    def test_explicit_setlist_accepts_two_songs(self):
        text = _setlist(
            "セトリ [Set list]",
            "01:00 Song A",
            "05:00 Song B",
            "",
            "配信内容",
            "00:10 greeting",
        )
        analyzer = CommentAnalyzer([_comment(text)], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is True
        assert [song.title for song in analyzer.extract_song_list()] == [
            "Song A",
            "Song B",
        ]

    def test_unlabelled_two_song_comment_still_does_not_qualify(self):
        analyzer = CommentAnalyzer(
            [_comment("01:00 Song A\n05:00 Song B")],
            video_id=VIDEO_ID,
        )
        assert analyzer.has_song_list_comment() is False

    def test_invalid_timestamps_do_not_qualify(self):
        text = "1:99 nope\n2:77 nope\n3:60 nope"
        analyzer = CommentAnalyzer([_comment(text)], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is False

    def test_timestamp_cluster_without_enough_titles_does_not_qualify(self):
        text = "31:40 20:56 4:04 1:41:00\nThanks for the wonderful stream!"
        analyzer = CommentAnalyzer([_comment(text)], video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is False

    def test_ignores_non_mapping_comment_items(self):
        analyzer = CommentAnalyzer(
            [None, _comment("0:10 A\n0:20 B\n0:30 C")],  # type: ignore[list-item]
            video_id=VIDEO_ID,
        )
        assert analyzer.has_song_list_comment() is True

    def test_ignores_comment_with_non_string_text(self):
        analyzer = CommentAnalyzer(
            [
                {"text": 12345},
                _comment("0:10 A\n0:20 B\n0:30 C"),
            ],
            video_id=VIDEO_ID,
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

    def test_malformed_like_count_does_not_abort_analysis(self):
        comments = [
            _comment("0:10 A\n0:20 B\n0:30 C", like_count="not-a-number"),  # type: ignore[arg-type]
            _comment("1:10 D\n1:20 E\n1:30 F", like_count="1.2K"),  # type: ignore[arg-type]
        ]
        analyzer = CommentAnalyzer(comments, video_id=VIDEO_ID)
        assert analyzer.has_song_list_comment() is True
        assert analyzer.extract_song_list()[0].title == "D"

    @pytest.mark.parametrize("like_count", [float("nan"), float("inf"), "inf"])
    def test_non_finite_like_count_does_not_abort_analysis(self, like_count):
        analyzer = CommentAnalyzer(
            [_comment("0:10 A\n0:20 B\n0:30 C", like_count=like_count)],
            video_id=VIDEO_ID,
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

    def test_numbered_title_then_timestamp(self):
        songs = self._songs_from("01. Title 0:12:00")
        assert len(songs) == 1
        assert songs[0].title == "Title"
        assert songs[0].timestamp == "0:12:00"

    def test_numbering_after_timestamp_is_stripped(self):
        songs = self._songs_from("0:10 1. HINOTORI")
        assert len(songs) == 1
        assert songs[0].title == "HINOTORI"

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

    def test_compact_timestamp_first_setlist_on_one_line(self):
        songs = self._songs_from("0:10 Song A | 3:20 Song B | 7:30 Song C")
        assert [(song.timestamp, song.title) for song in songs] == [
            ("0:10", "Song A"),
            ("3:20", "Song B"),
            ("7:30", "Song C"),
        ]

    def test_compact_title_first_setlist_on_one_line(self):
        songs = self._songs_from("Song A 0:10 | Song B 3:20 | Song C 7:30")
        assert [(song.timestamp, song.title) for song in songs] == [
            ("0:10", "Song A"),
            ("3:20", "Song B"),
            ("7:30", "Song C"),
        ]

    def test_compact_setlist_heading_is_not_treated_as_first_title(self):
        songs = self._songs_from("Setlist: 0:10 Song A | 3:20 Song B | 7:30 Song C")
        assert [song.title for song in songs] == ["Song A", "Song B", "Song C"]

    def test_cumulative_minutes_timestamp(self):
        songs = self._songs_from("125:04 Long Stream Song")
        assert songs[0].timestamp == "125:04"

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

    def test_extract_from_text_ignores_non_string_input(self):
        analyzer = CommentAnalyzer([], video_id=VIDEO_ID, minimum_timestamp_count=1)
        assert analyzer.extract_from_text(None) == []  # type: ignore[arg-type]

    def test_extract_without_detection_returns_empty(self):
        analyzer = CommentAnalyzer([_comment("nope")], video_id=VIDEO_ID)
        assert analyzer.extract_song_list() == []

    def test_explicit_setlist_excludes_following_stream_chapters(self):
        text = _setlist(
            "セトリ [Set list]",
            "00:09:12 Song A / Artist",
            "00:13:24 Song B / Artist",
            "00:17:13 Song C / Artist",
            "",
            "─── 配信内容 ───",
            "00:02:16 greeting",
            "00:20:00 announcement",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == [
            "Song A / Artist",
            "Song B / Artist",
            "Song C / Artist",
        ]

    def test_explicit_setlist_excludes_other_timestamps_section(self):
        text = _setlist(
            "Setlist:",
            "04:00 Song A - Artist",
            "10:37 Song B - Artist",
            "15:49 Song C - Artist",
            "",
            "Other Timestamps:",
            "01:57 greeting",
            "08:44 talking",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == [
            "Song A - Artist",
            "Song B - Artist",
            "Song C - Artist",
        ]

    def test_explicit_setlist_keeps_encore_then_stops_at_announcement(self):
        text = _setlist(
            "♪ Set List ♪",
            "4:51 Song A",
            "13:48 Song B",
            "♩アンコール / Encore♩",
            "1:13:21 Song C",
            "",
            "🥐告知 / Announcement🥐",
            "54:09 event announcement",
            "↓雑談他 / Talk",
            "1:31 greeting",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == ["Song A", "Song B", "Song C"]

    def test_explicit_setlist_stops_at_plain_divider(self):
        text = _setlist(
            "Set List",
            "10:00 Song A",
            "14:12 Song B",
            "18:25 Song C",
            "---------------------",
            "2:46 :_custom_emoji:",
            "3:18 audience reaction",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == ["Song A", "Song B", "Song C"]

    def test_explicit_setlist_keeps_songs_after_encore_divider(self):
        text = _setlist(
            "Set List",
            "10:00 Song A",
            "14:12 Song B",
            "18:25 Song C",
            "---------------------",
            "Encore",
            "22:40 Song D",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == [
            "Song A",
            "Song B",
            "Song C",
            "Song D",
        ]

    def test_explicit_setlist_stops_at_large_timestamp_regression(self):
        text = _setlist(
            "🕰 セトリ 🥀",
            "01. 0:03:19 ～ Song A／Artist",
            "02. 0:10:04 ～ Song B／Artist",
            "03. 0:17:25 ～ Song C／Artist",
            "04. 1:28:04 ～ Song D／Artist",
            "1:15:40 ～ unrelated event",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == [
            "Song A／Artist",
            "Song B／Artist",
            "Song C／Artist",
            "Song D／Artist",
        ]

    def test_strips_youtube_custom_emoji_tokens_from_titles(self):
        songs = self._songs_from(
            _setlist(
                "Set List",
                "10:00 Song A:_cheer:",
                "14:12 :_sparkle: Song B",
                "18:25 Song C :_thank_you:",
            )
        )
        assert [song.title for song in songs] == ["Song A", "Song B", "Song C"]

    def test_wave_dash_separator_is_stripped(self):
        songs = self._songs_from("0:10 〜 Song A")
        assert songs[0].title == "Song A"

    def test_wave_dash_at_end_of_song_title_is_preserved(self):
        songs = self._songs_from("0:10 Crazy Party Night 〜ぱんぷきんの逆襲〜")
        assert songs[0].title == "Crazy Party Night 〜ぱんぷきんの逆襲〜"

    def test_chapter_only_start_and_end_rows_are_skipped(self):
        songs = self._songs_from(
            _setlist(
                "Set list",
                "0:10 開始｜sᴛᴀʀᴛ",
                "1:00 Song A",
                "2:00 Song B",
                "3:00 Ending",
            )
        )
        assert [song.title for song in songs] == ["Song A", "Song B"]

    def test_late_song_named_start_is_preserved(self):
        songs = self._songs_from("25:12 StaRt")
        assert songs[0].title == "StaRt"

    def test_start_prefix_before_first_song_is_removed(self):
        songs = self._songs_from("0:10 開始 & 01. Song A")
        assert songs[0].title == "Song A"

    def test_setlist_allows_untimestamped_metadata_continuation_lines(self):
        text = _setlist(
            ":_channel: セトリ [Set list] : 曲名 / Artist",
            "00:09:16 Song A / Artist A",
            "　　　　『Series A』OP",
            "00:14:07 Song B / Artist B",
            "　　　　『Series B』ED",
            "00:18:51 Song C / Artist C",
        )
        songs = self._songs_from(text)
        assert [song.title for song in songs] == [
            "Song A / Artist A",
            "Song B / Artist B",
            "Song C / Artist C",
        ]

    def test_mismatched_timestamp_bracket_is_tolerated(self):
        songs = self._songs_from(
            _setlist(
                "Set List",
                "「03:22] Song A",
                "[10:04] Song B",
                "【17:26】 Song C",
            )
        )
        assert [song.title for song in songs] == ["Song A", "Song B", "Song C"]

    def test_no_heading_keeps_existing_all_timestamp_behavior(self):
        songs = self._songs_from(_setlist("0:10 Song A", "0:20 chat", "0:30 Song B"))
        assert [song.title for song in songs] == ["Song A", "chat", "Song B"]

    def test_long_title_is_bounded_to_database_limit(self):
        songs = self._songs_from("0:10 " + ("x" * 600))
        assert len(songs[0].title) == 500


class TestLlmCleaner:
    @pytest.mark.asyncio
    async def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("services.analyzer.llm_cleaner.LLM_CLEANING_ENABLED", False)
        from services.analyzer.llm_cleaner import maybe_clean_song_list_comment

        assert await maybe_clean_song_list_comment("0:10 A\n0:20 B\n0:30 C") is None

    @pytest.mark.asyncio
    async def test_httpx2_success_returns_cleaned_text(self, monkeypatch):
        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [{"message": {"content": "0:10 Song A\n0:20 Song B"}}]
                }

        class FakeAsyncClient:
            def __init__(self, *, timeout):
                captured["timeout"] = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, url, *, json, headers):
                captured.update(url=url, json=json, headers=headers)
                return FakeResponse()

        monkeypatch.setattr("services.analyzer.llm_cleaner.LLM_CLEANING_ENABLED", True)
        monkeypatch.setattr("services.analyzer.llm_cleaner.LLM_API_KEY", "test-key")
        monkeypatch.setattr(
            "services.analyzer.llm_cleaner.LLM_API_URL",
            "https://llm.invalid/v1/chat/completions",
        )
        monkeypatch.setattr(
            "services.analyzer.llm_cleaner.httpx2.AsyncClient",
            FakeAsyncClient,
        )
        from services.analyzer.llm_cleaner import maybe_clean_song_list_comment

        result = await maybe_clean_song_list_comment("0:10 A\n0:20 B")

        assert result == "0:10 Song A\n0:20 Song B"
        assert captured["timeout"] > 0
        assert captured["url"] == "https://llm.invalid/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["json"]["messages"][-1]["content"] == "0:10 A\n0:20 B"

    @pytest.mark.asyncio
    async def test_enabled_without_key_returns_none(self, monkeypatch):
        monkeypatch.setattr("services.analyzer.llm_cleaner.LLM_CLEANING_ENABLED", True)
        monkeypatch.setattr("services.analyzer.llm_cleaner.LLM_API_KEY", "")
        from services.analyzer.llm_cleaner import maybe_clean_song_list_comment

        assert await maybe_clean_song_list_comment("0:10 A\n0:20 B\n0:30 C") is None
