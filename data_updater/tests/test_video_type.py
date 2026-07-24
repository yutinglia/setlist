"""Unit tests for title-based song / karaoke video classification."""

from utils.video_type import (
    KARAOKE_MIN_DURATION_SECONDS,
    VIDEO_TYPE_KARAOKE,
    VIDEO_TYPE_OTHER,
    VIDEO_TYPE_SONG,
    classify_video_type,
    is_karaoke_stream,
    is_karaoke_title,
    is_song_title,
    should_scrape_comments,
)


class TestKaraokeTitles:
    def test_known_keywords(self):
        assert is_karaoke_title("【歌枠】深夜のカラオケ")
        assert is_karaoke_title("歌回！みんなで歌おう")
        assert is_karaoke_title("KARAOKE STREAM")
        assert is_karaoke_title("Singing Stream Archive")
        assert is_karaoke_title("カラOKタイム")
        assert is_karaoke_title("歌配信です")

    def test_non_karaoke(self):
        assert not is_karaoke_title("ゲーム実況")
        assert not is_karaoke_title("【MV】Stellar Stellar")


class TestSongTitles:
    def test_known_keywords(self):
        assert is_song_title("【MV】Stellar Stellar")
        assert is_song_title("Song Cover - Hello")
        assert is_song_title("Official Music Video")
        assert is_song_title("歌ってみた / 曲名")
        assert is_song_title("オリジナル曲を公開")
        assert is_song_title("翻唱：曲名")

    def test_non_song(self):
        assert not is_song_title("雑談配信")
        assert not is_song_title("【歌枠】カラオケ")


class TestKaraokeSoftConfirms:
    def test_title_only_when_metadata_missing(self):
        assert is_karaoke_stream("【歌枠】深夜")
        assert classify_video_type("【歌枠】深夜") == VIDEO_TYPE_KARAOKE

    def test_was_live_and_long_enough(self):
        assert (
            classify_video_type(
                "【歌枠】",
                live_status="was_live",
                duration=KARAOKE_MIN_DURATION_SECONDS,
            )
            == VIDEO_TYPE_KARAOKE
        )

    def test_rejects_not_live(self):
        assert (
            classify_video_type(
                "【歌枠】",
                live_status="not_live",
                duration=3600,
            )
            == VIDEO_TYPE_OTHER
        )

    def test_rejects_short_when_duration_known(self):
        assert (
            classify_video_type(
                "KARAOKE STREAM",
                live_status="was_live",
                duration=KARAOKE_MIN_DURATION_SECONDS - 1,
            )
            == VIDEO_TYPE_OTHER
        )

    def test_cover_is_song_not_karaoke(self):
        assert (
            classify_video_type(
                "Singing Cover Night",
                live_status="was_live",
                duration=3600,
            )
            == VIDEO_TYPE_SONG
        )
        assert not should_scrape_comments(
            "Singing Cover Night",
            live_status="was_live",
            duration=3600,
        )

    def test_strong_karaoke_beats_cover_word(self):
        assert (
            classify_video_type(
                "KARAOKE Cover Night",
                live_status="was_live",
                duration=3600,
            )
            == VIDEO_TYPE_KARAOKE
        )
        assert should_scrape_comments(
            "KARAOKE Cover Night",
            live_status="was_live",
            duration=3600,
        )

    def test_stored_song_type_blocks_comments(self):
        assert not should_scrape_comments(
            "【歌枠】",
            live_status="was_live",
            duration=3600,
            stored_type=VIDEO_TYPE_SONG,
        )


class TestClassifyVideoType:
    def test_karaoke_wins_over_song_when_strong(self):
        assert classify_video_type("KARAOKE Cover Night") == VIDEO_TYPE_KARAOKE

    def test_song(self):
        assert classify_video_type("【MV】新曲") == VIDEO_TYPE_SONG
        assert not should_scrape_comments("【MV】新曲")

    def test_other(self):
        assert classify_video_type("Minecraft 実況") == VIDEO_TYPE_OTHER
        assert classify_video_type("") == VIDEO_TYPE_OTHER
