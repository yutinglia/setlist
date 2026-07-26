"""Unit tests for YouTube timestamp deep-link helpers."""

from utils.youtube_timestamp import timestamp_to_seconds, youtube_url_with_timestamp


class TestTimestampToSeconds:
    def test_mm_ss(self):
        assert timestamp_to_seconds("12:34") == 12 * 60 + 34

    def test_hh_mm_ss(self):
        assert timestamp_to_seconds("1:02:03") == 3600 + 120 + 3

    def test_zero_padded(self):
        assert timestamp_to_seconds("00:01:23") == 83

    def test_cumulative_minutes(self):
        assert timestamp_to_seconds("75:04") == 75 * 60 + 4

    def test_fullwidth_colons(self):
        assert timestamp_to_seconds("1：02：03") == 3723

    def test_none_and_empty(self):
        assert timestamp_to_seconds(None) is None
        assert timestamp_to_seconds("") is None
        assert timestamp_to_seconds("   ") is None

    def test_invalid(self):
        assert timestamp_to_seconds("not-a-time") is None
        assert timestamp_to_seconds("12:60") is None
        assert timestamp_to_seconds("1:2:3:4") is None


class TestYoutubeUrlWithTimestamp:
    def test_appends_t_with_existing_query(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert (
            youtube_url_with_timestamp(url, "12:34")
            == "https://www.youtube.com/watch?v=abc123&t=754s"
        )

    def test_uses_question_mark_when_no_query(self):
        url = "https://youtu.be/abc123"
        assert (
            youtube_url_with_timestamp(url, "1:00") == "https://youtu.be/abc123?t=60s"
        )

    def test_passthrough_when_unparseable(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert youtube_url_with_timestamp(url, None) == url
        assert youtube_url_with_timestamp(url, "bad") == url

    def test_replaces_existing_t_and_preserves_fragment(self):
        url = "https://www.youtube.com/watch?v=abc123&t=1s#comments"
        assert (
            youtube_url_with_timestamp(url, "2:00")
            == "https://www.youtube.com/watch?v=abc123&t=120s#comments"
        )
