import yt_dlp

from models.video import YouTubeVideo


class YouTubeChannelVideoScraper:
    def __init__(self, channel_url: str) -> None:
        self.channel_url = channel_url
        self.videos: list[YouTubeVideo] = []

    def get_channel_videos(self) -> list[YouTubeVideo]:
        def filter_videos(info: dict, *, incomplete: bool) -> str | None:
            """Filter out shorts, live streams, and videos shorter than 60 seconds."""
            # Check if it's a short
            original_url = info.get("original_url", "")
            url = info.get("url", "")
            if "/shorts/" in original_url or "/shorts/" in url:
                return "Excluding shorts"

            # Check live status
            live_status = info.get("live_status")
            if live_status not in ["was_live", "not_live", None]:
                return "Excluding live streams"

            # Check duration
            duration = info.get("duration")
            if duration is not None and duration <= 60:
                return "Video too short"

            return None

        ydl_opts = {
            "skip_download": True,
            "extract_flat": "in_playlist",  # Use in_playlist mode for better performance
            # "quiet": True,
            # speed limit
            "sleep_interval": 1,
            "max_sleep_interval": 2,
            "match_filter": filter_videos,
            "ignoreerrors": True,  # Continue on errors
        }

        all_videos = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.channel_url, download=False)
            entries = info.get("entries", [])

            # Handle nested playlists (Videos, Live, Shorts)
            for entry in entries:
                if entry is None:
                    continue

                # If entry has its own entries, it's a playlist
                if "entries" in entry:
                    sub_entries = entry.get("entries", [])
                    all_videos.extend([v for v in sub_entries if v is not None])
                else:
                    # It's a direct video entry
                    all_videos.append(entry)

            # for safety, remove duplicates based on video ID
            unique_videos = {}
            for video in all_videos:
                video_id = video.get("id")
                if video_id and video_id not in unique_videos:
                    unique_videos[video_id] = video

            all_videos = list(unique_videos.values())

            # Convert to YouTubeVideo models
            video_models = []
            for video in all_videos:
                video_model = YouTubeVideo(
                    id=video.get("id"),
                    title=video.get("title", ""),
                    url=video.get("url") or f"https://www.youtube.com/watch?v={video.get('id')}",
                    channel_id=video.get("channel_id") or video.get("uploader_id", ""),
                    upload_date=video.get("upload_date"),
                    type="was_live" if video.get("live_status") == "was_live" else "video",
                    raw_data=video,
                )
                video_models.append(video_model)

            self.videos = video_models

            return video_models
