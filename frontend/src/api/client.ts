import type {
  AuthSession,
  ChannelBulkAddResponse,
  ChannelQueued,
  ChannelVideoRefresh,
  HealthResponse,
  Paginated,
  RecentUpdates,
  SetlistContributor,
  Song,
  SongSearchResult,
  SongSuggestion,
  SummaryReport,
  UpdaterStatus,
  VideoSongReload,
  YouTubeChannel,
  YouTubeVideo,
} from "@/api/types"

/**
 * Browser-facing API base.
 * - Dev: empty → Vite proxies `/v1` to FastAPI (`127.0.0.1:8000`).
 * - Prod / custom: set `VITE_API_BASE_URL` (e.g. `http://localhost:8000`).
 */
const DEFAULT_API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)
    ?.trim()
    .replace(/\/+$/, "") ?? ""

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

function pageQuery(limit: number, offset: number): string {
  return `limit=${limit}&offset=${offset}`
}

export type ApiClientOptions = {
  baseUrl?: string
  fetch?: typeof globalThis.fetch
}

export function createApiClient(options: ApiClientOptions = {}) {
  const apiBase = (options.baseUrl ?? DEFAULT_API_BASE).replace(/\/+$/, "")
  const fetchImplementation =
    options.fetch ??
    ((input: RequestInfo | URL, init?: RequestInit) =>
      globalThis.fetch(input, init))
  let csrfToken: string | null = null

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const method = (init?.method ?? "GET").toUpperCase()
    const headers = new Headers(init?.headers)
    headers.set("Accept", "application/json")
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
      headers.set("X-CSRF-Token", csrfToken)
    }
    const res = await fetchImplementation(`${apiBase}${path}`, {
      ...init,
      credentials: "include",
      headers,
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

  return {
  health: () => request<HealthResponse>("/v1/health"),

  authSession: async () => {
    const session = await request<AuthSession>("/v1/auth/session")
    csrfToken = session.csrf_token
    return session
  },

  login: async (username: string, password: string) => {
    const session = await request<AuthSession>("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
    csrfToken = session.csrf_token
    return session
  },

  logout: async () => {
    const session = await request<AuthSession>("/v1/auth/logout", {
      method: "POST",
    })
    csrfToken = null
    return session
  },

  updaterStatus: () => request<UpdaterStatus>("/v1/updater/status"),

  summaryReport: () => request<SummaryReport>("/v1/report/summary"),

  searchSongs: (
    q: string,
    limit: number,
    offset: number,
    filters?: {
      channelIds?: string[]
      type?: "karaoke" | "song"
      uploadDateFrom?: string
      uploadDateTo?: string
    },
  ) => {
    const params = new URLSearchParams({
      q,
      limit: String(limit),
      offset: String(offset),
    })
    for (const channelId of filters?.channelIds ?? []) {
      params.append("channel_id", channelId)
    }
    if (filters?.type) params.set("type", filters.type)
    if (filters?.uploadDateFrom) {
      params.set("upload_date_from", filters.uploadDateFrom)
    }
    if (filters?.uploadDateTo) {
      params.set("upload_date_to", filters.uploadDateTo)
    }
    return request<Paginated<SongSearchResult>>(
      `/v1/songs/search?${params.toString()}`,
    )
  },

  suggestSongs: (
    q: string,
    limit: number,
    filters?: {
      channelIds?: string[]
      type?: "karaoke" | "song"
      uploadDateFrom?: string
      uploadDateTo?: string
    },
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams({
      q,
      limit: String(limit),
    })
    for (const channelId of filters?.channelIds ?? []) {
      params.append("channel_id", channelId)
    }
    if (filters?.type) params.set("type", filters.type)
    if (filters?.uploadDateFrom) {
      params.set("upload_date_from", filters.uploadDateFrom)
    }
    if (filters?.uploadDateTo) {
      params.set("upload_date_to", filters.uploadDateTo)
    }
    return request<SongSuggestion[]>(
      `/v1/songs/suggestions?${params.toString()}`,
      { signal },
    )
  },

  getSong: (id: number) => request<SongSearchResult>(`/v1/songs/${id}`),

  listSetlistContributors: (limit: number, offset: number) =>
    request<Paginated<SetlistContributor>>(
      `/v1/contributors?${pageQuery(limit, offset)}`,
    ),

  listChannels: (limit: number, offset: number, q?: string) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    if (q?.trim()) params.set("q", q.trim())
    return request<Paginated<YouTubeChannel>>(
      `/v1/channels?${params.toString()}`,
    )
  },

  recentUpdates: () => request<RecentUpdates>("/v1/updates/recent"),

  getChannel: (channelId: string) =>
    request<YouTubeChannel>(
      `/v1/channels/${encodeURIComponent(channelId)}`,
    ),

  createChannel: (url: string) =>
    request<YouTubeChannel | ChannelQueued>("/v1/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),

  createChannelsBulk: (urls: string[]) =>
    request<ChannelBulkAddResponse>("/v1/channels/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    }),

  listChannelVideos: (
    channelId: string,
    limit: number,
    offset: number,
    type?: "karaoke" | "song",
    hasSongList?: boolean,
  ) => {
    const typeQuery = type ? `&type=${encodeURIComponent(type)}` : ""
    const setlistQuery =
      hasSongList === undefined
        ? ""
        : `&has_song_list=${hasSongList ? "true" : "false"}`
    return request<Paginated<YouTubeVideo>>(
      `/v1/channels/${encodeURIComponent(channelId)}/videos?${pageQuery(limit, offset)}${typeQuery}${setlistQuery}`,
    )
  },

  refreshChannelVideos: (channelId: string) =>
    request<ChannelVideoRefresh>(
      `/v1/channels/${encodeURIComponent(channelId)}/videos/refresh`,
      { method: "POST" },
    ),

  reloadVideoSongs: (videoId: string) =>
    request<VideoSongReload>(
      `/v1/videos/${encodeURIComponent(videoId)}/songs/reload`,
      { method: "POST" },
    ),

  listVideoSongs: (videoId: string, limit: number, offset: number) =>
    request<Paginated<Song>>(
      `/v1/videos/${encodeURIComponent(videoId)}/songs?${pageQuery(limit, offset)}`,
    ),

  getVideo: (videoId: string) =>
    request<YouTubeVideo>(`/v1/videos/${encodeURIComponent(videoId)}`),
  }
}

export type ApiClient = ReturnType<typeof createApiClient>
