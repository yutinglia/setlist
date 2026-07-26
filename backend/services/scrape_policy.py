"""Environment-independent scraper scheduling policy.

Development and production use the same defaults and the same orchestration
code. Tests can inject a smaller/faster policy without changing ``APP_ENV``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScrapePolicy:
    """Bounded work and pacing controls for one updater process."""

    worker_interval_seconds: int
    steady_scan_interval_seconds: int
    steady_retry_base_seconds: int
    steady_channels_per_cycle: int
    recent_videos_per_channel: int
    metadata_scrapes_per_refresh: int
    backfill_page_size: int
    backfill_pages_per_cycle: int
    backfill_channels_per_cycle: int
    comment_scrapes_per_cycle: int
    max_comments_per_video: int
    max_analysis_attempts: int
    analysis_recheck_seconds: int
    analysis_retry_base_seconds: int
    inter_list_sleep_min: float
    inter_list_sleep_max: float
    inter_comment_sleep_min: float
    inter_comment_sleep_max: float
    ytdlp_list_sleep_interval: float
    ytdlp_list_max_sleep_interval: float
    ytdlp_comment_sleep_interval: float
    ytdlp_comment_max_sleep_interval: float
    ytdlp_socket_timeout_seconds: float
    ytdlp_retries: int
    ytdlp_extractor_retries: int
    ytdlp_operation_timeout_seconds: float
    ytdlp_terminate_grace_seconds: float
    youtube_cooldown_seconds: int
