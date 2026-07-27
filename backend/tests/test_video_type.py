"""Unit tests for title-based song / karaoke video classification."""

from utils.video_type import (
    KARAOKE_MIN_DURATION_SECONDS,
    VIDEO_TYPE_KARAOKE,
    VIDEO_TYPE_OTHER,
    VIDEO_TYPE_SONG,
    classify_video_type,
    is_karaoke_stream,
    is_karaoke_title,
    is_non_singing_branded_title,
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
        assert is_karaoke_title("今夜はカラオケ！")
        assert is_karaoke_title("深夜にまったり弾き語り")
        assert is_karaoke_title("久しぶりにアカペラ")
        assert is_karaoke_title("【3D LIVE】Birthday concert")

    def test_non_karaoke(self):
        assert not is_karaoke_title("ゲーム実況")
        assert not is_karaoke_title("【MV】Stellar Stellar")
        assert not is_karaoke_title("【Among Us】#歌うま宇宙人狼")
        assert not is_karaoke_title("【雑談】歌うセトリを決める")
        # Outing / vlog — mentions カラオケ but is not a 歌枠 stream.
        outing = "tuki.ちゃんと星街すいせいでカラオケ行ってみた‼🌙✨（前編）"
        assert not is_karaoke_title(outing)
        assert classify_video_type(outing) == VIDEO_TYPE_OTHER

    def test_karaoke_stream_context(self):
        assert is_karaoke_title("今夜はカラオケ配信！")
        assert is_karaoke_title("【カラオケ】みんなで歌おう")
        assert is_karaoke_title("カラオケ枠します")

    def test_trailing_creator_role_does_not_make_talk_or_game_karaoke(self):
        game = "【トモコレ】ガンダムと友達になりたい #ウタノライブ【KARAOKE/Vsinger】"
        talk = "【TALK】旅のおもひで #ウタノライブ【KARAOKE/Vsinger/Vtuber】"
        assert is_non_singing_branded_title(game)
        assert is_non_singing_branded_title(talk)
        assert (
            classify_video_type(game, live_status="was_live", duration=3600)
            == VIDEO_TYPE_OTHER
        )
        assert (
            classify_video_type(talk, live_status="was_live", duration=3600)
            == VIDEO_TYPE_OTHER
        )

    def test_independent_singing_marker_beats_trailing_creator_role(self):
        title = "【歌枠】歌います #ウタノライブ【KARAOKE/Vsinger】"
        assert not is_non_singing_branded_title(title)
        assert (
            classify_video_type(title, live_status="was_live", duration=3600)
            == VIDEO_TYPE_KARAOKE
        )

    def test_3d_live_recap_is_not_a_performance_marker(self):
        for title in (
            "【振り返り】一緒に3D LIVEを見ながら振り返ろう",
            "Let's watch together at the same time! [#ReGLOSS3DLIVE]",
        ):
            assert (
                classify_video_type(
                    title,
                    live_status="was_live",
                    duration=3600,
                )
                == VIDEO_TYPE_OTHER
            )


class TestSongTitles:
    def test_known_keywords(self):
        assert is_song_title("【MV】Stellar Stellar")
        assert is_song_title("Song Cover - Hello")
        assert is_song_title("革命道中 / Covered by VTuber")
        assert is_song_title("Official Music Video")
        assert is_song_title("歌ってみた / 曲名")
        assert is_song_title("オリジナル曲を公開")
        assert is_song_title("翻唱：曲名")
        assert is_song_title("【original】ころねの最凶天災")
        assert is_song_title("サヨナラは、まだ / 大神ミオ (Original)")
        assert is_song_title("【Original原創曲】流星會降落在你心上")
        assert is_song_title("Happy Birthday (original ukulele song)")
        assert is_song_title("ホロライブ運動会テーマソング")

    def test_non_song(self):
        assert not is_song_title("雑談配信")
        assert not is_song_title("【歌枠】カラオケ")
        assert not is_song_title("Official birthday stream")
        assert not is_song_title("Music news and chat")
        assert not is_song_title("My favorite song tier list")


class TestKaraokeSoftConfirms:
    def test_rejects_live_upcoming_and_post_live_even_with_strong_title(self):
        for status in ("is_live", "is_upcoming", "post_live"):
            assert (
                classify_video_type(
                    "【歌枠】KARAOKE",
                    live_status=status,
                    duration=3600,
                )
                == VIDEO_TYPE_OTHER
            )
            assert not should_scrape_comments(
                "【歌枠】KARAOKE",
                live_status=status,
                duration=3600,
            )

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

    def test_strong_karaoke_keeps_not_live(self):
        # Videos-tab VODs / reuploads are often not_live; strong titles still count.
        assert (
            classify_video_type(
                "【歌枠】",
                live_status="not_live",
                duration=3600,
            )
            == VIDEO_TYPE_KARAOKE
        )
        assert should_scrape_comments(
            "【歌枠】",
            live_status="not_live",
            duration=3600,
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

    def test_cover_is_song_not_karaoke_when_short(self):
        assert (
            classify_video_type(
                "Singing Cover Night",
                live_status="not_live",
                duration=5 * 60,
            )
            == VIDEO_TYPE_SONG
        )
        assert not should_scrape_comments(
            "Singing Cover Night",
            live_status="not_live",
            duration=5 * 60,
        )

    def test_long_cover_is_not_song(self):
        # Song keywords block weak karaoke; long duration blocks song → other.
        assert (
            classify_video_type(
                "Singing Cover Night",
                live_status="was_live",
                duration=3600,
            )
            == VIDEO_TYPE_OTHER
        )
        assert (
            classify_video_type(
                "『シカ色デイズ』歌って踊ってみた",
                duration=3600,
            )
            == VIDEO_TYPE_OTHER
        )

    def test_weak_singing_still_needs_was_live(self):
        assert (
            classify_video_type(
                "Singing Stream Archive",
                live_status="not_live",
                duration=3600,
            )
            == VIDEO_TYPE_OTHER
        )
        assert (
            classify_video_type(
                "Singing Stream Archive",
                live_status="was_live",
                duration=3600,
            )
            == VIDEO_TYPE_KARAOKE
        )

    def test_observed_weak_singing_phrases_need_was_live(self):
        for title in (
            "【告知アリ】歌う【Sing♪】",
            "今夜はすきな歌をうたって過ごします",
            "狼、歌います",
            "唱歌🎵",
            "【歌雜】開飲料派對",
        ):
            assert (
                classify_video_type(
                    title,
                    live_status="not_live",
                    duration=3600,
                )
                == VIDEO_TYPE_OTHER
            )
            assert (
                classify_video_type(
                    title,
                    live_status="was_live",
                    duration=3600,
                )
                == VIDEO_TYPE_KARAOKE
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
        # Strong title + not_live still karaoke when long enough.
        assert (
            classify_video_type(
                "KARAOKE Cover Night",
                live_status="not_live",
                duration=3600,
            )
            == VIDEO_TYPE_KARAOKE
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
        assert classify_video_type("Official Audio - Title") == VIDEO_TYPE_SONG
        assert (
            classify_video_type("【MV】新曲", duration=9 * 60 + 59) == VIDEO_TYPE_SONG
        )
        assert classify_video_type("【MV】新曲", duration=10 * 60) == VIDEO_TYPE_SONG

    def test_other(self):
        assert classify_video_type("Minecraft 実況") == VIDEO_TYPE_OTHER
        assert classify_video_type("") == VIDEO_TYPE_OTHER
