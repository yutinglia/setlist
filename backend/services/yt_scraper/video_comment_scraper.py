import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import yt_dlp

from services.yt_scraper.errors import raise_if_block_error
from services.yt_scraper.options import bounded_network_options
from utils.ytdlp_snapshot import snapshot_payload, snapshot_ytdlp_info

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoCommentScrapeResult:
    comments: list[dict[str, Any]]
    comments_available: bool
    metadata_raw_data: dict[str, Any]
    scraped_at: datetime
    requested_max_comments: int | None = None
    reported_comment_count: int | None = None
    comment_sort: str | None = None
    max_replies: int | None = None
    max_depth: int | None = None
    yt_dlp_version: str | None = None


class YouTubeVideoCommentScraper:
    def __init__(
        self,
        video_url: str,
        *,
        sleep_interval: float = 2.0,
        max_sleep_interval: float = 10.0,
        socket_timeout: float = 30.0,
        retries: int = 2,
        extractor_retries: int = 2,
    ) -> None:
        self.video_url = video_url
        self.sleep_interval = sleep_interval
        self.max_sleep_interval = max_sleep_interval
        self.socket_timeout = socket_timeout
        self.retries = retries
        self.extractor_retries = extractor_retries
        # The comment request already performs a full video extraction. Keep a
        # bounded stable-field snapshot so callers can upgrade dates and reuse
        # richer metadata without making another YouTube request.
        self.video_metadata: dict[str, Any] = {}
        self.last_result: VideoCommentScrapeResult | None = None

    def scrape(self, max_comments: int) -> VideoCommentScrapeResult:
        ydl_opts = {
            "skip_download": True,
            "getcomments": True,
            "quiet": True,
            "no_warnings": True,
            # Raised sleep vs list scrapers (Tier B)
            "sleep_interval": self.sleep_interval,
            "max_sleep_interval": self.max_sleep_interval,
            **bounded_network_options(
                socket_timeout=self.socket_timeout,
                retries=self.retries,
                extractor_retries=self.extractor_retries,
            ),
            "extractor_args": {
                "youtube": {
                    # max-comments, max-parents, max-replies,
                    # max-replies-per-thread, max-depth. yt-dlp numbers the
                    # top-level comment collection as depth 1, so keep that
                    # depth while disabling replies.
                    "max_comments": [
                        str(max_comments),
                        str(max_comments),
                        "0",
                        "0",
                        "1",
                    ],
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

        scraped_at = datetime.now(UTC).replace(tzinfo=None)
        metadata_raw_data = snapshot_ytdlp_info(
            info,
            source="video_comments",
            captured_at=scraped_at,
        )
        self.video_metadata = snapshot_payload(metadata_raw_data)

        # A missing field is also how disabled/unavailable comments are exposed;
        # it is not enough evidence for a process-wide YouTube cooldown.
        raw_comments = info.get("comments")
        comments_available = raw_comments is not None
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
        sanitized = yt_dlp.YoutubeDL.sanitize_info({"comments": comments})
        safe_comments = sanitized.get("comments") if isinstance(sanitized, dict) else []
        if not isinstance(safe_comments, list):
            raise RuntimeError(f"Comments did not sanitize for {self.video_url}")
        comments = [comment for comment in safe_comments if isinstance(comment, dict)]
        raw_comment_count = info.get("comment_count")
        reported_comment_count = (
            raw_comment_count
            if isinstance(raw_comment_count, int)
            and not isinstance(raw_comment_count, bool)
            and raw_comment_count >= 0
            else None
        )
        logger.info("Fetched %s comments for %s", len(comments), self.video_url)
        self.last_result = VideoCommentScrapeResult(
            comments=comments,
            comments_available=comments_available,
            metadata_raw_data=metadata_raw_data,
            scraped_at=scraped_at,
            requested_max_comments=max_comments,
            reported_comment_count=reported_comment_count,
            comment_sort="top",
            max_replies=0,
            max_depth=1,
            yt_dlp_version=yt_dlp.version.__version__,
        )
        return self.last_result

    def get_video_top_comments(self, max_comments: int) -> list[dict[str, Any]]:
        """Compatibility wrapper for callers that only need comment objects."""
        return self.scrape(max_comments).comments
