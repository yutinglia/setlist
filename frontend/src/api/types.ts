/** API DTOs matching `data_updater` v1 responses. */

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
}

export type YouTubeChannel = {
  id: string
  name: string
  url: string
  thumbnail_url: string | null
  video_backfill_status?: "pending" | "running" | "done" | "failed"
  video_backfill_offset?: number
  video_backfill_updated_at?: string | null
  created_at: string | null
  updated_at: string | null
}

export type YouTubeVideo = {
  id: string
  title: string
  url: string
  channel_id: string
  upload_date: string | null
  type: string | null
  has_song_list_comment: boolean
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
  comment_scrapes_this_cycle: number
  comment_scrape_cap: number
  is_cycle_active: boolean
  youtube_cooldown_remaining_seconds: number
  update_interval_seconds: number
  updated_at: string | null
}
