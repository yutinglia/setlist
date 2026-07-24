import type {
  ChannelVideoRefresh,
  HealthResponse,
  Paginated,
  Song,
  SongSearchResult,
  YouTubeChannel,
  YouTubeVideo,
} from "@/api/types"

/**
 * Browser-facing API base.
 * - Dev: empty → Vite proxies `/v1` to FastAPI (`127.0.0.1:8000`).
 * - Prod / custom: set `VITE_API_BASE_URL` (e.g. `http://localhost:8000`).
 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
  /\/$/,
  "",
) ?? ""

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

function pageQuery(limit: number, offset: number): string {
  return `limit=${limit}&offset=${offset}`
}

export const api = {
  health: () => request<HealthResponse>("/v1/health"),

  searchSongs: (q: string, limit: number, offset: number) =>
    request<Paginated<SongSearchResult>>(
      `/v1/songs/search?q=${encodeURIComponent(q)}&${pageQuery(limit, offset)}`,
    ),

  getSong: (id: number) => request<SongSearchResult>(`/v1/songs/${id}`),

  listChannels: (limit: number, offset: number) =>
    request<Paginated<YouTubeChannel>>(
      `/v1/channels?${pageQuery(limit, offset)}`,
    ),

  listChannelVideos: (channelId: string, limit: number, offset: number) =>
    request<Paginated<YouTubeVideo>>(
      `/v1/channels/${encodeURIComponent(channelId)}/videos?${pageQuery(limit, offset)}`,
    ),

  refreshChannelVideos: (channelId: string) =>
    request<ChannelVideoRefresh>(
      `/v1/channels/${encodeURIComponent(channelId)}/videos/refresh`,
      { method: "POST" },
    ),

  listVideoSongs: (videoId: string, limit: number, offset: number) =>
    request<Paginated<Song>>(
      `/v1/videos/${encodeURIComponent(videoId)}/songs?${pageQuery(limit, offset)}`,
    ),
}
