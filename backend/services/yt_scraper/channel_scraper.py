import logging

import yt_dlp

from models.channel import YouTubeChannel
from services.yt_scraper.errors import raise_if_block_error
from services.yt_scraper.options import bounded_network_options
from utils.youtube_channel_url import normalize_youtube_channel_url
from utils.ytdlp_snapshot import snapshot_payload, snapshot_ytdlp_info

logger = logging.getLogger(__name__)


class YouTubeChannelScraper:
    def __init__(
        self,
        *,
        sleep_interval: float = 1.0,
        max_sleep_interval: float = 2.0,
        socket_timeout: float = 30.0,
        retries: int = 2,
        extractor_retries: int = 2,
    ) -> None:
        self.sleep_interval = sleep_interval
        self.max_sleep_interval = max_sleep_interval
        self.socket_timeout = socket_timeout
        self.retries = retries
        self.extractor_retries = extractor_retries
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
            "sleep_interval": self.sleep_interval,
            "max_sleep_interval": self.max_sleep_interval,
            **bounded_network_options(
                socket_timeout=self.socket_timeout,
                retries=self.retries,
                extractor_retries=self.extractor_retries,
            ),
        }

        logger.info("Scraping channel metadata: %s", channel_url)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        if not isinstance(info, dict) or not info:
            raise RuntimeError(f"Failed to extract channel info for {channel_url}")
        raw_snapshot = snapshot_ytdlp_info(info, source="channel")
        stable_info = snapshot_payload(raw_snapshot)

        # Prefer the uncropped avatar, then fall back to the last usable image.
        thumbnails = stable_info.get("thumbnails") or []
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

        channel_id = stable_info.get("channel_id") or stable_info.get("id")
        if not isinstance(channel_id, str) or not channel_id.strip():
            raise RuntimeError(
                f"Channel id missing from extractor response: {channel_url}"
            )
        self.channel = YouTubeChannel(
            id=channel_id,
            name=(
                stable_info.get("channel") or stable_info.get("uploader") or channel_id
            ),
            url=channel_url,
            thumbnail_url=thumbnail_url,
            raw_data=raw_snapshot,
        )

        logger.info("Scraped channel %s (%s)", self.channel.name, self.channel.id)
        return self.channel
