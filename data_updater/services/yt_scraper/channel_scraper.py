import logging

import yt_dlp

from models.channel import YouTubeChannel
from services.yt_scraper.errors import raise_if_block_error
from utils.youtube_channel_url import normalize_youtube_channel_url

logger = logging.getLogger(__name__)


class YouTubeChannelScraper:
    def __init__(self) -> None:
        self.channel: YouTubeChannel | None = None

    def get_channel_info(self, channel_url: str) -> YouTubeChannel:
        channel_url = normalize_youtube_channel_url(channel_url)
        ydl_opts = {
            "skip_download": True,
            "playlist_items": "0",
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            # speed limit
            "sleep_interval": 1,
            "max_sleep_interval": 2,
        }

        logger.info("Scraping channel metadata: %s", channel_url)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        if info:
            info = yt_dlp.YoutubeDL.sanitize_info(info)
        if not info:
            raise RuntimeError(f"Failed to extract channel info for {channel_url}")

        # Prefer the uncropped avatar, then fall back to the last usable image.
        thumbnails = info.get("thumbnails") or []
        fallback_thumbnail = next(
            (
                thumb.get("url")
                for thumb in reversed(thumbnails)
                if isinstance(thumb, dict) and thumb.get("url")
            ),
            None,
        )
        thumbnail_url = next(
            (
                thumb.get("url")
                for thumb in thumbnails
                if isinstance(thumb, dict)
                and thumb.get("id") == "avatar_uncropped"
                and thumb.get("url")
            ),
            fallback_thumbnail,
        )

        channel_id = info.get("channel_id") or info.get("id") or ""
        self.channel = YouTubeChannel(
            id=channel_id,
            name=info.get("channel") or info.get("uploader") or channel_id,
            url=channel_url,
            thumbnail_url=thumbnail_url,
            raw_data=info,
        )

        logger.info("Scraped channel %s (%s)", self.channel.name, self.channel.id)
        return self.channel
