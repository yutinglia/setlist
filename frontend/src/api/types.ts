/** API DTOs matching backend v1 responses. */

export type Paginated<T> = {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type SongSearchResult = {
  id: number
  title: string
  timestamp: string | null
  video_id: string
  video_url: string
  video_title: string | null
  channel_id: string
  channel_name: string
  analyzed_by_llm: boolean
  setlist_comment_author: string | null
  setlist_comment_author_id: string | null
  setlist_comment_id: string | null
  created_at: string | null
  updated_at: string | null
}

export type RecentUpdates = {
  channels: YouTubeChannel[]
  songs: SongSearchResult[]
}

export type SongSuggestion = {
  title: string
  occurrences: number
}

export type SetlistContributor = {
  author: string
  author_id: string
  song_count: number
  video_count: number
}

export type YouTubeChannel = {
  id: string
  name: string
  url: string
  thumbnail_url: string | null
  created_at: string | null
  updated_at: string | null
}

export type ChannelBulkAddStatus =
  | "created"
  | "already_exists"
  | "invalid"
  | "failed"
  | "skipped"

export type ChannelBulkAddItem = {
  url: string
  status: ChannelBulkAddStatus
  channel_id: string | null
  channel_name: string | null
  message: string
}

export type ChannelBulkAddResponse = {
  items: ChannelBulkAddItem[]
  created: number
  already_exists: number
  failed: number
  skipped: number
  max_batch_size: number
  cooldown_seconds: number
}

export type YouTubeVideo = {
  id: string
  title: string
  url: string
  channel_id: string
  upload_date: string | null
  upload_date_precision: "exact" | "approximate" | null
  type: string | null
  has_song_list_comment: boolean
  setlist_comment_author: string | null
  setlist_comment_author_id: string | null
  setlist_comment_id: string | null
  created_at: string | null
  updated_at: string | null
}

export type Song = {
  id: number | null
  title: string
  video_id: string
  timestamp: string | null
  analyzed_by_llm: boolean
  created_at: string | null
  updated_at: string | null
}

export type HealthResponse = {
  status: string
  version?: string
  database?: string
  cache?: "disabled" | "ok" | "unavailable"
}

export type AuthSession = {
  authenticated: boolean
  role: "admin" | null
  username: string | null
  csrf_token: string | null
  management_enabled: boolean
}

export type SummaryReport = {
  generated_at: string
  channels: number
  backfill: {
    pending: number
    running: number
    done: number
    failed: number
  }
  videos: {
    total: number
    karaoke: number
    song: number
    other: number
    with_list_snapshot: number
    with_metadata_snapshot: number
    date_unknown: number
    date_approximate: number
    date_exact: number
    latest_discovered_at: string | null
  }
  analysis: {
    attempted: number
    with_setlist: number
    videos_with_comments: number
    comments: number
    latest_analyzed_at: string | null
    status: {
      pending: number
      retry: number
      no_setlist: number
      done: number
      exhausted: number
      skipped: number
    }
  }
  songs: {
    total: number
    analyzed_by_llm: number
    contributors: number
  }
}

export type ChannelVideoRefresh = {
  channel_id: string
  mode: string
  scraped: number
  deleted: number
  reclassified: number
  cleared: number
  message: string
}

/** Live scraper / analyzer phase from GET /v1/updater/status */
export type UpdaterPhase =
  | "idle"
  | "waiting"
  | "cooldown"
  | "starting"
  | "fetching_channels"
  | "refreshing_channel"
  | "scraping_videos"
  | "backfilling_videos"
  | "reclassifying"
  | "scraping_comments"
  | "analyzing"
  | "llm_cleaning"
  | "jitter"
  | "committing"
  | "error"

export type UpdaterStatus = {
  phase: UpdaterPhase | string
  detail: string | null
  channel_id: string | null
  channel_name: string | null
  video_id: string | null
  video_title: string | null
  cycle_started_at: string | null
  last_cycle_finished_at: string | null
  last_error: string | null
  persistent_cycle_started_at: string | null
  persistent_cycle_finished_at: string | null
  persistent_last_success_at: string | null
  persistent_heartbeat_at: string | null
  persistent_outcome:
    | "never"
    | "running"
    | "success"
    | "cooldown"
    | "error"
    | "cancelled"
    | string
  persistent_owner_id: string | null
  is_stalled: boolean
  heartbeat_stale_seconds: number
  comment_scrapes_this_cycle: number
  comment_scrape_cap: number
  is_cycle_active: boolean
  background_updater_enabled: boolean
  youtube_cooldown_remaining_seconds: number
  update_interval_seconds: number
  steady_scan_interval_seconds: number
  backfill_page_size: number
  backfill_pages_per_cycle: number
  updated_at: string | null
}

export type VideoSongReload = {
  video_id: string
  song_count: number
  has_song_list_comment: boolean
  analysis_status: string
  message: string
}
