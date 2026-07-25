import logging
from dataclasses import dataclass

import yt_dlp

from models.video import YouTubeVideo
from utils.video_type import classify_video_type
from utils.youtube_channel_url import channel_list_urls
from utils.youtube_upload_date import upload_date_from_entry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelVideoPageResult:
    """One paced window across Streams + Videos tabs."""

    videos: list[YouTubeVideo]
    # Raw yt-dlp entries before shorts/live/duration filtering (sum across tabs).
    raw_entry_count: int
    # True when every tab returned fewer than ``page_size`` raw entries.
    exhausted: bool
    page_size: int
    playlist_start: int
    playlist_end: int


def should_exclude_channel_list_entry(info: dict, *, incomplete: bool = False) -> str | None:
    """Filter out shorts, live streams, and videos shorter than 60 seconds."""
    del incomplete  # yt-dlp match_filter signature
    original_url = info.get("original_url", "")
    url = info.get("url", "")
    if "/shorts/" in original_url or "/shorts/" in url:
        return "Excluding shorts"

    live_status = info.get("live_status")
    if live_status not in ["was_live", "not_live", None]:
        return "Excluding live streams"

    duration = info.get("duration")
    if duration is not None and duration <= 60:
        return "Video too short"

    return None


class YouTubeChannelVideoScraper:
    def __init__(
        self,
        channel_url: str,
        *,
        max_videos: int | None = None,
        full_metadata: bool = False,
        playlist_start: int | None = None,
        playlist_end: int | None = None,
    ) -> None:
        self.channel_url = channel_url
        self.max_videos = max_videos
        # Flat tab lists omit upload_date. When True, enrich dates via per-video
        # metadata fetches after the flat list (full tab extract is unreliable).
        self.full_metadata = full_metadata
        self.playlist_start = playlist_start
        self.playlist_end = playlist_end
        self.videos: list[YouTubeVideo] = []

    def get_channel_videos(self) -> list[YouTubeVideo]:
        """Scrape recent channel tab entries (optional ``max_videos`` / window)."""
        list_urls = channel_list_urls(self.channel_url)
        per_tab_start: int | None = self.playlist_start
        per_tab_end: int | None = self.playlist_end
        if per_tab_end is None and self.max_videos is not None and self.max_videos > 0:
            # Extra headroom so shorts/live filtered out still leave enough.
            per_tab_end = self.max_videos * 2
            per_tab_start = per_tab_start or 1

        all_videos: list[dict] = []
        for tab_url in list_urls:
            entries, _raw_count, ok = self._extract_tab_entries(
                tab_url,
                playlist_start=per_tab_start,
                playlist_end=per_tab_end,
                use_match_filter=True,
            )
            if ok:
                all_videos.extend(entries)

        if not all_videos and list_urls:
            raise RuntimeError(
                f"Failed to extract video list for {self.channel_url}"
            )

        video_models = self._entries_to_models(all_videos)
        self.videos = video_models
        logger.info(
            "Scraped %s videos from %s (%s tabs, full_metadata=%s)",
            len(video_models),
            self.channel_url,
            len(list_urls),
            self.full_metadata,
        )
        return video_models

    def get_channel_videos_page(
        self,
        *,
        playlist_start: int,
        page_size: int,
    ) -> ChannelVideoPageResult:
        """Scrape one ``page_size`` window from each tab (paced backfill).

        Filtering is applied in Python so empty filtered pages do not look
        like playlist exhaustion while older entries still remain.
        """
        if playlist_start < 1:
            raise ValueError("playlist_start must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")

        playlist_end = playlist_start + page_size - 1
        list_urls = channel_list_urls(self.channel_url)
        all_raw: list[dict] = []
        successful_raw_counts: list[int] = []

        for tab_url in list_urls:
            entries, raw_count, ok = self._extract_tab_entries(
                tab_url,
                playlist_start=playlist_start,
                playlist_end=playlist_end,
                use_match_filter=False,
            )
            if not ok:
                continue
            successful_raw_counts.append(raw_count)
            all_raw.extend(entries)

        if list_urls and not successful_raw_counts:
            raise RuntimeError(
                f"Failed to extract backfill page for {self.channel_url} "
                f"(offset={playlist_start})"
            )

        filtered = [
            entry
            for entry in all_raw
            if should_exclude_channel_list_entry(entry) is None
        ]
        video_models = self._entries_to_models(filtered)
        self.videos = video_models

        exhausted = bool(successful_raw_counts) and all(
            count < page_size for count in successful_raw_counts
        )
        logger.info(
            "Backfill page %s-%s for %s: raw=%s kept=%s exhausted=%s "
            "(tab_raw=%s)",
            playlist_start,
            playlist_end,
            self.channel_url,
            sum(successful_raw_counts),
            len(video_models),
            exhausted,
            successful_raw_counts,
        )
        return ChannelVideoPageResult(
            videos=video_models,
            raw_entry_count=sum(successful_raw_counts),
            exhausted=exhausted,
            page_size=page_size,
            playlist_start=playlist_start,
            playlist_end=playlist_end,
        )

    def _extract_tab_entries(
        self,
        tab_url: str,
        *,
        playlist_start: int | None,
        playlist_end: int | None,
        use_match_filter: bool,
    ) -> tuple[list[dict], int, bool]:
        ydl_opts: dict = {
            "skip_download": True,
            # Flat list is reliable for channel tabs; full tab extract often
            # fails or times out. Dates are filled in _enrich_metadata later.
            "extract_flat": "in_playlist",
            "quiet": True,
            "no_warnings": True,
            "sleep_interval": 1,
            "max_sleep_interval": 2,
            "ignoreerrors": True,
        }
        if use_match_filter:
            ydl_opts["match_filter"] = should_exclude_channel_list_entry
        if playlist_start is not None and playlist_start > 1:
            ydl_opts["playliststart"] = playlist_start
        if playlist_end is not None:
            ydl_opts["playlistend"] = playlist_end

        logger.info(
            "Scraping channel video list: %s (playliststart=%s playlistend=%s)",
            tab_url,
            ydl_opts.get("playliststart", 1),
            ydl_opts.get("playlistend", "all"),
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(tab_url, download=False)
        except Exception:
            logger.exception("Failed scraping tab %s", tab_url)
            return [], 0, False

        if not info:
            logger.warning("Empty extract for %s", tab_url)
            return [], 0, True

        entries = info.get("entries", []) or []
        flat: list[dict] = []
        for entry in entries:
            if entry is None:
                continue
            if "entries" in entry:
                sub_entries = entry.get("entries", []) or []
                flat.extend([v for v in sub_entries if v is not None])
            else:
                flat.append(entry)
        return flat, len(flat), True

    def _entries_to_models(self, all_videos: list[dict]) -> list[YouTubeVideo]:
        # for safety, remove duplicates based on video ID
        unique_videos: dict[str, dict] = {}
        for video in all_videos:
            video_id = video.get("id")
            if video_id and video_id not in unique_videos:
                unique_videos[video_id] = video

        all_videos = list(unique_videos.values())

        if self.full_metadata:
            # Cap enrichment to the newest N entries (flat order ≈ recent).
            enrich_cap = self.max_videos * 2 if self.max_videos else len(all_videos)
            all_videos = self._enrich_metadata(all_videos[:enrich_cap]) + all_videos[
                enrich_cap:
            ]

        video_models: list[YouTubeVideo] = []
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
        return video_models

    def _enrich_metadata(self, entries: list[dict]) -> list[dict]:
        """Fill upload_date / live_status / duration via per-video extracts."""
        if not entries:
            return entries

        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "sleep_interval": 1,
            "max_sleep_interval": 2,
        }
        enriched: list[dict] = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for index, entry in enumerate(entries):
                video_id = entry.get("id")
                if not video_id:
                    enriched.append(entry)
                    continue

                if upload_date_from_entry(entry) and entry.get("duration") is not None:
                    enriched.append(entry)
                    continue

                url = (
                    entry.get("url")
                    or entry.get("webpage_url")
                    or f"https://www.youtube.com/watch?v={video_id}"
                )
                logger.info(
                    "Enriching metadata %s/%s for %s",
                    index + 1,
                    len(entries),
                    video_id,
                )
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception:
                    logger.exception("Failed enriching metadata for %s", video_id)
                    enriched.append(entry)
                    continue

                if not info:
                    enriched.append(entry)
                    continue

                merged = dict(entry)
                for key in (
                    "upload_date",
                    "timestamp",
                    "release_timestamp",
                    "live_status",
                    "duration",
                    "was_live",
                    "title",
                ):
                    value = info.get(key)
                    if value is not None and value != "":
                        merged[key] = value
                enriched.append(merged)

        return enriched
