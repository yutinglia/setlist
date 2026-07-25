import logging
from typing import Any

import yt_dlp

from services.yt_scraper.errors import raise_if_block_error

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

        if not isinstance(info, dict) or not info:
            # Empty/malformed output is a transient per-video extraction error,
            # not evidence that the whole process/IP has been blocked.
            raise RuntimeError(
                f"Empty or invalid comment response for {self.video_url}"
            )

        # A missing field is also how disabled/unavailable comments are exposed;
        # it is not enough evidence for a process-wide YouTube cooldown.
        raw_comments = info.get("comments")
        if raw_comments is None:
            comments: list[dict[str, Any]] = []
        elif not isinstance(raw_comments, list):
            raise RuntimeError(f"Unexpected comments response for {self.video_url}")
        else:
            comments = [
                comment for comment in raw_comments if isinstance(comment, dict)
            ]
            if len(comments) != len(raw_comments):
                logger.warning(
                    "Discarded %s malformed comment item(s) for %s",
                    len(raw_comments) - len(comments),
                    self.video_url,
                )
        logger.info("Fetched %s comments for %s", len(comments), self.video_url)
        return comments
