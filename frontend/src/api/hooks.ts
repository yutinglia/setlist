import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { api } from "@/api/client"

export const PAGE_SIZE = 20
export const SONG_SUGGESTION_LIMIT = 8

export const authSessionQueryOptions = queryOptions({
  queryKey: ["auth", "session"],
  queryFn: () => api.authSession(),
  staleTime: 5 * 60_000,
  retry: false,
})

export function useAuthSession() {
  return useQuery(authSessionQueryOptions)
}

export function useLogin() {
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
      queryClient.setQueryData(authSessionQueryOptions.queryKey, session)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: (session) => {
      queryClient.setQueryData(authSessionQueryOptions.queryKey, session)
      queryClient.removeQueries({ queryKey: ["updater"] })
    },
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    staleTime: 60_000,
    retry: 1,
  })
}

export function useUpdaterStatus() {
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
  return useQuery({
    queryKey: ["report", "summary"],
    queryFn: () => api.summaryReport(),
    staleTime: 15_000,
    retry: 1,
  })
}

export type SongSearchFilters = {
  channelId?: string
  type?: "karaoke" | "song"
  uploadDateFrom?: string
  uploadDateTo?: string
}

export function useSongSearch(
  q: string,
  page: number,
  filters: SongSearchFilters = {},
) {
  const offset = page * PAGE_SIZE
  const channelId = filters.channelId
  const type = filters.type
  const uploadDateFrom = filters.uploadDateFrom
  const uploadDateTo = filters.uploadDateTo
  return useQuery({
    queryKey: [
      "songs",
      "search",
      q,
      page,
      channelId ?? null,
      type ?? null,
      uploadDateFrom ?? null,
      uploadDateTo ?? null,
    ],
    queryFn: () =>
      api.searchSongs(q, PAGE_SIZE, offset, {
        channelId,
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
  const normalizedQuery = q.trim()
  const channelId = filters.channelId
  const type = filters.type
  const uploadDateFrom = filters.uploadDateFrom
  const uploadDateTo = filters.uploadDateTo
  return useQuery({
    queryKey: [
      "songs",
      "suggestions",
      normalizedQuery,
      channelId ?? null,
      type ?? null,
      uploadDateFrom ?? null,
      uploadDateTo ?? null,
    ],
    queryFn: ({ signal }) =>
      api.suggestSongs(
        normalizedQuery,
        SONG_SUGGESTION_LIMIT,
        {
          channelId,
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

/** Channel options for advanced search (not page-sized browse). */
export function useChannelOptions() {
  return useQuery({
    queryKey: ["channels", "options"],
    queryFn: () => api.listChannels(100, 0),
    staleTime: 60_000,
  })
}

export function useSong(id: number) {
  return useQuery({
    queryKey: ["songs", id],
    queryFn: () => api.getSong(id),
    enabled: Number.isSafeInteger(id) && id > 0,
  })
}

export function useChannels(page: number) {
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["channels", page],
    queryFn: () => api.listChannels(PAGE_SIZE, offset),
    placeholderData: (prev) => prev,
  })
}

export function useCreateChannel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => api.createChannel(url),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["channels"] })
      await queryClient.invalidateQueries({ queryKey: ["channels", "options"] })
    },
  })
}

export function useCreateChannelsBulk() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (urls: string[]) => api.createChannelsBulk(urls),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["channels"] })
      await queryClient.invalidateQueries({ queryKey: ["channels", "options"] })
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
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["videos", videoId, "songs", page],
    queryFn: () => api.listVideoSongs(videoId, PAGE_SIZE, offset),
    enabled: videoId.length > 0 && (options?.enabled ?? true),
    placeholderData: (prev) => prev,
  })
}
