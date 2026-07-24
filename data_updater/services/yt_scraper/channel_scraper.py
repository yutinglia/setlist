import logging

import yt_dlp

from models.channel import YouTubeChannel

logger = logging.getLogger(__name__)


class YouTubeChannelScraper:
    def __init__(self) -> None:
        self.channel: YouTubeChannel | None = None

    def get_channel_info(self, channel_url: str) -> YouTubeChannel:
        ydl_opts = {
            "skip_download": True,
            "playlist_items": "0",
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            # speed limit
            "sleep_interval": 1,
            "max_sleep_interval": 2,
            "ignoreerrors": True,
        }

        logger.info("Scraping channel metadata: %s", channel_url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if not info:
                raise RuntimeError(f"Failed to extract channel info for {channel_url}")

            # get channel avatar thumbnail, id = avatar_uncropped
            thumbnail_url = ""
            thumbnails = info.get("thumbnails", [])
            for thumb in thumbnails:
                if thumb.get("id") == "avatar_uncropped":
                    thumbnail_url = thumb.get("url", "")
                    break

            channel_id = info.get("channel_id") or info.get("id") or ""
            self.channel = YouTubeChannel(
                id=channel_id,
                name=info.get("channel") or info.get("uploader") or channel_id,
                url=channel_url,
                thumbnail_url=thumbnail_url or None,
                raw_data=info,
            )

            logger.info("Scraped channel %s (%s)", self.channel.name, self.channel.id)
            return self.channel
