import logging
from typing import Any

import yt_dlp

from services.yt_scraper.errors import (
    YouTubeAccessBlocked,
    comments_look_blocked,
    raise_if_block_error,
)

logger = logging.getLogger(__name__)


class YouTubeVideoCommentScraper:
    def __init__(
        self,
        video_url: str,
        *,
        sleep_interval: float = 2.0,
        max_sleep_interval: float = 10.0,
    ) -> None:
        self.video_url = video_url
        self.sleep_interval = sleep_interval
        self.max_sleep_interval = max_sleep_interval

    def get_video_top_comments(self, max_comments: int) -> list[dict[str, Any]]:
        ydl_opts = {
            "skip_download": True,
            "getcomments": True,
            "quiet": True,
            "no_warnings": True,
            # Raised sleep vs list scrapers (Tier B)
            "sleep_interval": self.sleep_interval,
            "max_sleep_interval": self.max_sleep_interval,
            "extractor_args": {
                "youtube": {
                    # max-comments, max-parents, max-replies, max-replies-per-thread
                    "max_comments": [str(max_comments), str(max_comments), "0", "0"],
                    "comment_sort": ["top"],
                }
            },
        }

        logger.info(
            "Scraping top %s comments: %s (yt-dlp sleep %.1f–%.1fs)",
            max_comments,
            self.video_url,
            self.sleep_interval,
            self.max_sleep_interval,
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
        except Exception as exc:
            raise_if_block_error(exc)
            raise

        if not info:
            raise YouTubeAccessBlocked(
                f"Empty extract_info response for comments: {self.video_url}"
            )

        # Missing comments key after getcomments=True is treated as a block signal.
        if "comments" not in info:
            if comments_look_blocked(None):
                raise YouTubeAccessBlocked(
                    f"Comments payload missing for {self.video_url}"
                )

        comments = info.get("comments") or []
        logger.info(
            "Fetched %s comments for %s", len(comments), self.video_url
        )
        return comments
