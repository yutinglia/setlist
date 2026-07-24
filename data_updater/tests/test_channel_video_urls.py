"""Unit tests for channel video list URL expansion (Videos + Streams tabs)."""

from utils.youtube_channel_url import channel_list_urls


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
        assert channel_list_urls(
            "https://www.youtube.com/@suisei"
        ) == [
            "https://www.youtube.com/@suisei/streams",
            "https://www.youtube.com/@suisei/videos",
        ]

    def test_empty(self):
        assert channel_list_urls("") == []
        assert channel_list_urls("   ") == []
