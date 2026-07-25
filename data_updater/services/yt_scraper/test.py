"""Manual yt-dlp smoke checks.

This is intentionally not part of pytest because it performs live YouTube calls.
Run from ``data_updater/`` with ``python services/yt_scraper/test.py``.
"""

from services.analyzer.yt_comment_analyzer import CommentAnalyzer
from services.yt_scraper.channel_scraper import YouTubeChannelScraper
from services.yt_scraper.channel_video_scraper import YouTubeChannelVideoScraper
from services.yt_scraper.video_comment_scraper import YouTubeVideoCommentScraper


def inspect_comments() -> None:
    video_url = "https://www.youtube.com/watch?v=u0MoCudW5eM"
    scraper = YouTubeVideoCommentScraper(video_url)
    comments = scraper.get_video_top_comments(max_comments=15)
    print(f"Top {len(comments)} comments fetched successfully.")
    analyzer = CommentAnalyzer(
        comments, video_id="u0MoCudW5eM", minimum_timestamp_count=5
    )

    has_song_list = analyzer.has_song_list_comment()
    print(f"Has song list comment: {has_song_list}")
    if has_song_list:
        print("Song list comment text:")
        print(analyzer.song_list_comment.get("text", ""))
        song_list = analyzer.extract_song_list()
        print("Extracted Song List:")
        for song in song_list:
            print(f"- {song.title} at {song.timestamp}")


def inspect_videos() -> None:
    channel_url = "https://www.youtube.com/@Leona_Shishigami"
    scraper = YouTubeChannelVideoScraper(channel_url)
    videos = scraper.get_channel_videos()
    print(f"Total videos fetched from channel: {len(videos)}")
    # debugging
    if videos:
        # group by live_status
        type_count = {}
        for video in videos:
            raw = video.raw_data if isinstance(video.raw_data, dict) else {}
            vtype = raw.get("live_status", "unknown")
            type_count[vtype] = type_count.get(vtype, 0) + 1

        print("Video types count:")
        for vtype, count in type_count.items():
            print(f"{vtype}: {count}")


def inspect_channel() -> None:
    channel_url = "https://www.youtube.com/@Leona_Shishigami"
    scraper = YouTubeChannelScraper()
    channel = scraper.get_channel_info(channel_url)
    print("Channel Info:")
    print(f"ID: {channel.id}")
    print(f"Name: {channel.name}")
    print(f"URL: {channel.url}")
    print(f"Thumbnail URL: {channel.thumbnail_url}")


if __name__ == "__main__":
    inspect_channel()
