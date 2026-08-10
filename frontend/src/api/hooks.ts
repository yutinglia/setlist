import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import type { ApiClient } from "@/api/client"
import { useApi } from "@/api/context"
import type { YouTubeChannel } from "@/api/types"

export const PAGE_SIZE = 20
export const SONG_SUGGESTION_LIMIT = 8
const CHANNEL_OPTIONS_PAGE_SIZE = 100

export const authSessionQueryKey = ["auth", "session"] as const

export function authSessionQueryOptions(api: ApiClient) {
  return queryOptions({
    queryKey: authSessionQueryKey,
    queryFn: () => api.authSession(),
    staleTime: 5 * 60_000,
    retry: false,
  })
}

export function useAuthSession() {
  const api = useApi()
  return useQuery(authSessionQueryOptions(api))
}

export function useLogin() {
  const api = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      username,
      password,
    }: {
      username: string
      password: string
    }) => api.login(username, password),
    onSuccess: (session) => {
      queryClient.setQueryData(authSessionQueryKey, session)
    },
  })
}

export function useLogout() {
  const api = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: (session) => {
      queryClient.setQueryData(authSessionQueryKey, session)
      queryClient.removeQueries({ queryKey: ["updater"] })
    },
  })
}

export function useHealth() {
  const api = useApi()
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    staleTime: 60_000,
    retry: 1,
  })
}

export function useUpdaterStatus() {
  const api = useApi()
  const auth = useAuthSession()
  const isAdmin =
    auth.data?.authenticated === true && auth.data.role === "admin"
  return useQuery({
    queryKey: ["updater", "status"],
    queryFn: () => api.updaterStatus(),
    enabled: isAdmin,
    refetchInterval: isAdmin ? 2_000 : false,
    refetchIntervalInBackground: isAdmin,
    retry: 1,
  })
}

export function useSummaryReport() {
  const api = useApi()
  return useQuery({
    queryKey: ["report", "summary"],
    queryFn: () => api.summaryReport(),
    staleTime: 15_000,
    retry: 1,
  })
}

export function useRecentUpdates() {
  const api = useApi()
  return useQuery({
    queryKey: ["updates", "recent"],
    queryFn: () => api.recentUpdates(),
    staleTime: 60_000,
  })
}

export type SongSearchFilters = {
  channelIds?: string[]
  type?: "karaoke" | "song"
  uploadDateFrom?: string
  uploadDateTo?: string
}

export function useSongSearch(
  q: string,
  page: number,
  filters: SongSearchFilters = {},
) {
  const api = useApi()
  const offset = page * PAGE_SIZE
  const channelIds = filters.channelIds
  const type = filters.type
  const uploadDateFrom = filters.uploadDateFrom
  const uploadDateTo = filters.uploadDateTo
  return useQuery({
    queryKey: [
      "songs",
      "search",
      q,
      page,
      channelIds ?? null,
      type ?? null,
      uploadDateFrom ?? null,
      uploadDateTo ?? null,
    ],
    queryFn: () =>
      api.searchSongs(q, PAGE_SIZE, offset, {
        channelIds,
        type,
        uploadDateFrom,
        uploadDateTo,
      }),
    enabled: q.trim().length > 0,
    placeholderData: (prev) => prev,
  })
}

export function useSongSuggestions(
  q: string,
  filters: SongSearchFilters = {},
  options?: { enabled?: boolean },
) {
  const api = useApi()
  const normalizedQuery = q.trim()
  const channelIds = filters.channelIds
  const type = filters.type
  const uploadDateFrom = filters.uploadDateFrom
  const uploadDateTo = filters.uploadDateTo
  return useQuery({
    queryKey: [
      "songs",
      "suggestions",
      normalizedQuery,
      channelIds ?? null,
      type ?? null,
      uploadDateFrom ?? null,
      uploadDateTo ?? null,
    ],
    queryFn: ({ signal }) =>
      api.suggestSongs(
        normalizedQuery,
        SONG_SUGGESTION_LIMIT,
        {
          channelIds,
          type,
          uploadDateFrom,
          uploadDateTo,
        },
        signal,
      ),
    enabled:
      normalizedQuery.length >= 2 && (options?.enabled ?? true),
    staleTime: 60_000,
    retry: false,
  })
}

async function listAllChannelOptions(api: ApiClient) {
  const items: YouTubeChannel[] = []
  let total = 0
  let offset = 0

  do {
    const page = await api.listChannels(CHANNEL_OPTIONS_PAGE_SIZE, offset)
    total = page.total
    items.push(...page.items)
    if (page.items.length === 0) break
    offset += page.items.length
  } while (offset < total)

  return {
    items,
    total,
    limit: CHANNEL_OPTIONS_PAGE_SIZE,
    offset: 0,
  }
}

/** Complete channel options for advanced search (not page-sized browse). */
export function useChannelOptions() {
  const api = useApi()
  return useQuery({
    queryKey: ["channels", "options"],
    queryFn: () => listAllChannelOptions(api),
    staleTime: 60_000,
  })
}

export function useSong(id: number) {
  const api = useApi()
  return useQuery({
    queryKey: ["songs", id],
    queryFn: () => api.getSong(id),
    enabled: Number.isSafeInteger(id) && id > 0,
  })
}

export function useSetlistContributors(page: number) {
  const api = useApi()
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["setlist-contributors", page],
    queryFn: () => api.listSetlistContributors(PAGE_SIZE, offset),
    placeholderData: (prev) => prev,
    staleTime: 60_000,
  })
}

export function useChannels(page: number, query = "") {
  const api = useApi()
  const offset = page * PAGE_SIZE
  const normalizedQuery = query.trim()
  return useQuery({
    queryKey: ["channels", "browse", normalizedQuery, page],
    queryFn: () => api.listChannels(PAGE_SIZE, offset, normalizedQuery || undefined),
    placeholderData: (prev) => prev,
  })
}

export function useChannel(channelId: string) {
  const api = useApi()
  return useQuery({
    queryKey: ["channels", channelId],
    queryFn: () => api.getChannel(channelId),
    enabled: channelId.length > 0,
    staleTime: 60_000,
  })
}

export function useCreateChannel() {
  const api = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => api.createChannel(url),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["channels"] })
      await queryClient.invalidateQueries({ queryKey: ["channels", "options"] })
      await queryClient.invalidateQueries({ queryKey: ["updates", "recent"] })
    },
  })
}

export function useCreateChannelsBulk() {
  const api = useApi()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (urls: string[]) => api.createChannelsBulk(urls),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["channels"] })
      await queryClient.invalidateQueries({ queryKey: ["channels", "options"] })
      await queryClient.invalidateQueries({ queryKey: ["updates", "recent"] })
    },
  })
}

export function useChannelVideos(
  channelId: string,
  page: number,
  type: "karaoke" | "song",
  hasSongList: boolean | undefined,
  limit: number,
) {
  const api = useApi()
  const offset = page * limit
  return useQuery({
    queryKey: [
      "channels",
      channelId,
      "videos",
      type,
      hasSongList ?? null,
      page,
      limit,
    ],
    queryFn: () =>
      api.listChannelVideos(channelId, limit, offset, type, hasSongList),
    enabled: channelId.length > 0,
    placeholderData: (prev) => prev,
  })
}

export function useVideo(videoId: string) {
  const api = useApi()
  return useQuery({
    queryKey: ["videos", videoId],
    queryFn: () => api.getVideo(videoId),
    enabled: videoId.length > 0,
  })
}

export function useVideoSongs(
  videoId: string,
  page: number,
  options?: { enabled?: boolean },
) {
  const api = useApi()
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["videos", videoId, "songs", page],
    queryFn: () => api.listVideoSongs(videoId, PAGE_SIZE, offset),
    enabled: videoId.length > 0 && (options?.enabled ?? true),
    placeholderData: (prev) => prev,
  })
}
