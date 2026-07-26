"""Unit tests for channel video list URL expansion (Videos + Streams tabs)."""

import pytest

from utils.youtube_channel_url import (
    channel_list_urls,
    normalize_youtube_channel_url,
)


class TestChannelListUrls:
    def test_videos_tab_expands_to_streams_and_videos(self):
        assert channel_list_urls(
            "https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/videos"
        ) == [
            "https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/streams",
            "https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/videos",
        ]

    def test_streams_tab_still_expands_both(self):
        assert channel_list_urls(
            "https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/streams"
        ) == [
            "https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/streams",
            "https://www.youtube.com/channel/UC5CwaMl1eIgY8h02uZw7u8A/videos",
        ]

    def test_channel_root_expands_both(self):
        assert channel_list_urls("https://www.youtube.com/@suisei") == [
            "https://www.youtube.com/@suisei/streams",
            "https://www.youtube.com/@suisei/videos",
        ]

    def test_empty(self):
        assert channel_list_urls("") == []
        assert channel_list_urls("   ") == []

    def test_canonicalizes_host_query_fragment_and_tab(self):
        assert (
            normalize_youtube_channel_url(
                "http://m.youtube.com/@suisei/videos?view=0#top"
            )
            == "https://www.youtube.com/@suisei"
        )

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "https://youtube.com.evil.example/@channel",
            "https://www.youtube.com/watch?v=abc",
            "https://www.youtube.com:8443/@channel",
            "https://www.youtube.com/embed/abc",
            "https://www.youtube.com/@channel/unexpected/path",
            "https://www.youtube.com/channel/id/extra",
            "https://www.youtube.com/@",
        ],
    )
    def test_rejects_non_channel_or_unsafe_urls(self, url: str):
        with pytest.raises(ValueError):
            normalize_youtube_channel_url(url)
