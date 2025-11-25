from video_comment_scraper import YouTubeVideoCommentScraper
from channel_video_scraper import YouTubeChannelVideoScraper
from channel_scraper import YouTubeChannelScraper
from analyzer.yt_comment_analyzer import CommentAnalyzer


def test() -> None:
    video_url = "https://www.youtube.com/watch?v=u0MoCudW5eM"
    scraper = YouTubeVideoCommentScraper(video_url)
    comments = scraper.get_video_top_comments(max_comments=15)
    print(f"Top {len(comments)} comments fetched successfully.")
    analyzer = CommentAnalyzer(comments, minimum_timestamp_count=5)
    has_song_list = analyzer.has_song_list_comment()
    print(f"Has song list comment: {has_song_list}")
    if has_song_list:
        print("Song list comment text:")
        print(analyzer.song_list_comment.get("text", ""))
        song_list = analyzer.extract_song_list()
        print("Extracted Song List:")
        for song in song_list:
            print(f"- {song.title} at {song.timestamp}")


def test2() -> None:
    channel_url = "https://www.youtube.com/@Leona_Shishigami"
    scraper = YouTubeChannelVideoScraper(channel_url)
    videos = scraper.get_channel_videos()
    print(f"Total videos fetched from channel: {len(videos)}")
    # debugging
    if videos:
        # group by live_status
        type_count = {}
        for video in videos:
            vtype = video.get("live_status", "unknown")
            type_count[vtype] = type_count.get(vtype, 0) + 1

        print("Video types count:")
        for vtype, count in type_count.items():
            print(f"{vtype}: {count}")


def test3() -> None:
    channel_url = "https://www.youtube.com/@Leona_Shishigami"
    scraper = YouTubeChannelScraper()
    channel = scraper.get_channel_info(channel_url)
    print("Channel Info:")
    print(f"ID: {channel.channel_id}")
    print(f"Name: {channel.name}")
    print(f"URL: {channel.url}")
    print(f"Thumbnail URL: {channel.thumbnail_url}")


if __name__ == "__main__":
    # test()
    # test2()
    test3()
