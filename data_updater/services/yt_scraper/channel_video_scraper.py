import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import yt_dlp

from models.video import YouTubeVideo
from services.yt_scraper.errors import raise_if_block_error
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
    # Cursor movement is safe only when every non-missing tab succeeded.
    all_tabs_succeeded: bool
    failed_tabs: tuple[str, ...]
    page_size: int
    playlist_start: int
    playlist_end: int


def should_exclude_channel_list_entry(
    info: dict, *, incomplete: bool = False
) -> str | None:
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
        metadata_limit: int | None = None,
        playlist_start: int | None = None,
        playlist_end: int | None = None,
    ) -> None:
        self.channel_url = channel_url
        self.max_videos = max_videos
        # Flat tab lists omit upload_date. When True, enrich dates via per-video
        # metadata fetches after the flat list (full tab extract is unreliable).
        self.full_metadata = full_metadata
        self.metadata_limit = metadata_limit
        self.playlist_start = playlist_start
        self.playlist_end = playlist_end
        self.videos: list[YouTubeVideo] = []

    @staticmethod
    def _video_url(entry: dict, video_id: str) -> str:
        """Return a browser URL even when a flat entry's ``url`` is only an id."""
        for key in ("webpage_url", "original_url", "url"):
            candidate = entry.get(key)
            if not isinstance(candidate, str):
                continue
            parsed = urlsplit(candidate)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return candidate
        return f"https://www.youtube.com/watch?v={video_id}"

    @staticmethod
    def _is_missing_channel_tab_error(exc: Exception, tab_url: str) -> bool:
        """Recognize yt-dlp's expected error for a channel without a tab."""
        tab_name = urlsplit(tab_url).path.rstrip("/").rsplit("/", 1)[-1].casefold()
        if tab_name not in {"streams", "videos"}:
            return False
        expected = f"this channel does not have a {tab_name} tab"
        return expected in str(exc).casefold()

    def get_channel_videos(self) -> list[YouTubeVideo]:
        """Scrape recent channel tab entries (optional ``max_videos`` / window)."""
        list_urls = channel_list_urls(self.channel_url)
        if not list_urls:
            raise ValueError(f"Invalid YouTube channel URL: {self.channel_url!r}")

        per_tab_start: int | None = self.playlist_start
        per_tab_end: int | None = self.playlist_end
        if per_tab_end is None and self.max_videos is not None and self.max_videos > 0:
            # Extra headroom so shorts/live filtered out still leave enough.
            per_tab_end = self.max_videos * 2

        tab_groups: list[list[dict]] = []
        failed_tabs: list[str] = []
        for tab_url in list_urls:
            entries, _raw_count, ok = self._extract_tab_entries(
                tab_url,
                playlist_start=per_tab_start,
                playlist_end=per_tab_end,
                use_match_filter=True,
            )
            if not ok:
                failed_tabs.append(tab_url)
                continue
            tab_groups.append(entries)

        if not tab_groups:
            raise RuntimeError(
                "Failed to extract any channel tab: " + ", ".join(failed_tabs)
            )
        if failed_tabs:
            # Missing/disabled Streams tabs are normal. Since callers only
            # upsert and never infer deletions from this list, partial success
            # is safe and preferable to rejecting the usable tab.
            logger.warning(
                "Using partial channel video list; failed tabs: %s",
                ", ".join(failed_tabs),
            )

        # Interleave Streams and Videos so a bounded enrichment/list cannot be
        # monopolized by the first tab.
        all_videos: list[dict] = []
        max_group_size = max((len(group) for group in tab_groups), default=0)
        for index in range(max_group_size):
            for group in tab_groups:
                if index < len(group):
                    all_videos.append(group[index])

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
        if not list_urls:
            raise ValueError(f"Invalid YouTube channel URL: {self.channel_url!r}")

        all_raw: list[dict] = []
        successful_raw_counts: list[int] = []
        failed_tabs: list[str] = []

        for tab_url in list_urls:
            entries, raw_count, ok = self._extract_tab_entries(
                tab_url,
                playlist_start=playlist_start,
                playlist_end=playlist_end,
                use_match_filter=False,
            )
            if not ok:
                failed_tabs.append(tab_url)
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

        all_tabs_succeeded = not failed_tabs
        exhausted = (
            all_tabs_succeeded
            and bool(successful_raw_counts)
            and all(count < page_size for count in successful_raw_counts)
        )
        logger.info(
            "Backfill page %s-%s for %s: raw=%s kept=%s exhausted=%s "
            "(tab_raw=%s failed_tabs=%s)",
            playlist_start,
            playlist_end,
            self.channel_url,
            sum(successful_raw_counts),
            len(video_models),
            exhausted,
            successful_raw_counts,
            len(failed_tabs),
        )
        return ChannelVideoPageResult(
            videos=video_models,
            raw_entry_count=sum(successful_raw_counts),
            exhausted=exhausted,
            all_tabs_succeeded=all_tabs_succeeded,
            failed_tabs=tuple(failed_tabs),
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
        except Exception as exc:
            raise_if_block_error(exc)
            if self._is_missing_channel_tab_error(exc, tab_url):
                logger.info("Channel has no %s tab; treating it as empty", tab_url)
                return [], 0, True
            logger.exception("Failed scraping tab %s", tab_url)
            return [], 0, False

        if not info:
            logger.warning("Empty extract for %s", tab_url)
            return [], 0, False

        entries = info.get("entries", []) or []
        flat: list[dict] = []
        raw_count = 0
        for entry in entries:
            if not isinstance(entry, dict):
                # Unavailable/deleted playlist slots still count toward the
                # requested page window and must not signal early exhaustion.
                raw_count += 1
                continue
            if "entries" in entry:
                sub_entries = entry.get("entries", []) or []
                raw_count += len(sub_entries)
                flat.extend([v for v in sub_entries if isinstance(v, dict)])
            else:
                raw_count += 1
                flat.append(entry)
        return flat, raw_count, True

    def _entries_to_models(self, all_videos: list[dict]) -> list[YouTubeVideo]:
        # for safety, remove duplicates based on video ID
        unique_videos: dict[str, dict] = {}
        for video in all_videos:
            video_id = video.get("id")
            if video_id and video_id not in unique_videos:
                unique_videos[video_id] = video

        all_videos = list(unique_videos.values())

        if self.full_metadata:
            # Cap per-video metadata requests independently from list size.
            enrich_cap = (
                self.metadata_limit
                if self.metadata_limit is not None
                else self.max_videos
            )
            if enrich_cap is None:
                enrich_cap = len(all_videos)
            enrich_cap = max(0, enrich_cap)
            all_videos = (
                self._enrich_metadata(all_videos[:enrich_cap]) + all_videos[enrich_cap:]
            )

        video_models: list[YouTubeVideo] = []
        for video in all_videos:
            video_id = video.get("id")
            if not video_id:
                continue
            title = video.get("title") or video_id
            safe_video = yt_dlp.YoutubeDL.sanitize_info(video)
            video_model = YouTubeVideo(
                id=video_id,
                title=title,
                url=self._video_url(video, video_id),
                channel_id=video.get("channel_id") or video.get("uploader_id") or "",
                # Flat extracts omit upload_date; derive from timestamp fields.
                upload_date=upload_date_from_entry(video),
                # Title keywords + soft duration / live_status confirms.
                type=classify_video_type(
                    title,
                    live_status=video.get("live_status"),
                    duration=video.get("duration"),
                ),
                raw_data=safe_video,
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

                url = self._video_url(entry, video_id)
                logger.info(
                    "Enriching metadata %s/%s for %s",
                    index + 1,
                    len(entries),
                    video_id,
                )
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as exc:
                    raise_if_block_error(exc)
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
