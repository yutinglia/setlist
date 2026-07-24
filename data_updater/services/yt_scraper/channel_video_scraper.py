import logging

import yt_dlp

from models.video import YouTubeVideo
from utils.video_type import classify_video_type
from utils.youtube_channel_url import channel_list_urls
from utils.youtube_upload_date import upload_date_from_entry

logger = logging.getLogger(__name__)


class YouTubeChannelVideoScraper:
    def __init__(self, channel_url: str, *, max_videos: int | None = None) -> None:
        self.channel_url = channel_url
        self.max_videos = max_videos
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

        # Cap how many playlist entries yt-dlp walks (Tier B / prefer recent).
        # Split budget across Videos + Streams tabs when both are scraped.
        list_urls = channel_list_urls(self.channel_url)
        per_tab_end: int | None = None
        if self.max_videos is not None and self.max_videos > 0:
            # Extra headroom so shorts/live filtered out still leave enough.
            per_tab_end = self.max_videos * 2

        all_videos: list[dict] = []
        for tab_url in list_urls:
            ydl_opts: dict = {
                "skip_download": True,
                "extract_flat": "in_playlist",
                "quiet": True,
                "no_warnings": True,
                # speed limit
                "sleep_interval": 1,
                "max_sleep_interval": 2,
                "match_filter": filter_videos,
                "ignoreerrors": True,
            }
            if per_tab_end is not None:
                ydl_opts["playlistend"] = per_tab_end

            logger.info(
                "Scraping channel video list: %s (playlistend=%s)",
                tab_url,
                ydl_opts.get("playlistend", "all"),
            )
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(tab_url, download=False)
            except Exception:
                logger.exception("Failed scraping tab %s", tab_url)
                continue

            if not info:
                logger.warning("Empty extract for %s", tab_url)
                continue

            entries = info.get("entries", []) or []

            # Handle nested playlists (Videos, Live, Shorts)
            for entry in entries:
                if entry is None:
                    continue

                # If entry has its own entries, it's a playlist
                if "entries" in entry:
                    sub_entries = entry.get("entries", []) or []
                    all_videos.extend([v for v in sub_entries if v is not None])
                else:
                    # It's a direct video entry
                    all_videos.append(entry)

        if not all_videos and list_urls:
            raise RuntimeError(
                f"Failed to extract video list for {self.channel_url}"
            )

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
            video_id = video.get("id")
            if not video_id:
                continue
            title = video.get("title") or video_id
            video_model = YouTubeVideo(
                id=video_id,
                title=title,
                url=video.get("url")
                or f"https://www.youtube.com/watch?v={video_id}",
                channel_id=video.get("channel_id")
                or video.get("uploader_id")
                or "",
                # Flat extracts omit upload_date; derive from timestamp fields.
                upload_date=upload_date_from_entry(video),
                # Title keywords + soft duration / live_status confirms.
                type=classify_video_type(
                    title,
                    live_status=video.get("live_status"),
                    duration=video.get("duration"),
                ),
                raw_data=video,
            )
            video_models.append(video_model)

        # Merge Streams + Videos tabs into one newest-first list.
        video_models.sort(key=lambda v: v.upload_date or "", reverse=True)

        self.videos = video_models
        logger.info(
            "Scraped %s videos from %s (%s tabs)",
            len(video_models),
            self.channel_url,
            len(list_urls),
        )
        return video_models
