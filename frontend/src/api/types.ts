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
  analyzed_by_llm: boolean | null
}

export type YouTubeChannel = {
  id: string
  name: string
  url: string
  thumbnail_url: string | null
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
  has_song_list_comment: boolean | null
  created_at: string | null
  updated_at: string | null
}

export type Song = {
  id: number | null
  title: string
  video_id: string
  timestamp: string | null
  analyzed_by_llm: boolean | null
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
