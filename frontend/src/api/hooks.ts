import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/api/client"

export const PAGE_SIZE = 20

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 60_000,
    retry: 1,
  })
}

export function useUpdaterStatus() {
  return useQuery({
    queryKey: ["updater", "status"],
    queryFn: () => api.updaterStatus(),
    refetchInterval: 2_000,
    refetchIntervalInBackground: true,
    retry: 1,
  })
}

export function useSummaryReport() {
  return useQuery({
    queryKey: ["report", "summary"],
    queryFn: () => api.summaryReport(),
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 1,
  })
}

export function useSongSearch(q: string, page: number) {
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["songs", "search", q, page],
    queryFn: () => api.searchSongs(q, PAGE_SIZE, offset),
    enabled: q.trim().length > 0,
    placeholderData: (prev) => prev,
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
    },
  })
}

export function useChannelVideos(
  channelId: string,
  page: number,
  type: "karaoke" | "song",
  hasSongList?: boolean,
) {
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["channels", channelId, "videos", type, hasSongList ?? null, page],
    queryFn: () =>
      api.listChannelVideos(channelId, PAGE_SIZE, offset, type, hasSongList),
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
