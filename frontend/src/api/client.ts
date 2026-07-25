import type {
  ChannelVideoRefresh,
  HealthResponse,
  Paginated,
  Song,
  SongSearchResult,
  UpdaterStatus,
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
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body.detail === "string") {
        detail = body.detail
      } else if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((item) =>
            typeof item === "object" && item && "msg" in item
              ? String((item as { msg: unknown }).msg)
              : String(item),
          )
          .join("; ")
      }
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

  updaterStatus: () => request<UpdaterStatus>("/v1/updater/status"),

  searchSongs: (q: string, limit: number, offset: number) =>
    request<Paginated<SongSearchResult>>(
      `/v1/songs/search?q=${encodeURIComponent(q)}&${pageQuery(limit, offset)}`,
    ),

  getSong: (id: number) => request<SongSearchResult>(`/v1/songs/${id}`),

  listChannels: (limit: number, offset: number) =>
    request<Paginated<YouTubeChannel>>(
      `/v1/channels?${pageQuery(limit, offset)}`,
    ),

  createChannel: (url: string) =>
    request<YouTubeChannel>("/v1/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),

  listChannelVideos: (
    channelId: string,
    limit: number,
    offset: number,
    type?: "karaoke" | "song",
  ) => {
    const typeQuery = type ? `&type=${encodeURIComponent(type)}` : ""
    return request<Paginated<YouTubeVideo>>(
      `/v1/channels/${encodeURIComponent(channelId)}/videos?${pageQuery(limit, offset)}${typeQuery}`,
    )
  },

  refreshChannelVideos: (channelId: string) =>
    request<ChannelVideoRefresh>(
      `/v1/channels/${encodeURIComponent(channelId)}/videos/refresh`,
      { method: "POST" },
    ),

  listVideoSongs: (videoId: string, limit: number, offset: number) =>
    request<Paginated<Song>>(
      `/v1/videos/${encodeURIComponent(videoId)}/songs?${pageQuery(limit, offset)}`,
    ),

  getVideo: (videoId: string) =>
    request<YouTubeVideo>(`/v1/videos/${encodeURIComponent(videoId)}`),
}
