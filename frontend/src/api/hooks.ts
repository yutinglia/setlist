import { useQuery } from "@tanstack/react-query"

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
    enabled: Number.isFinite(id) && id > 0,
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

export function useChannelVideos(channelId: string, page: number) {
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["channels", channelId, "videos", page],
    queryFn: () => api.listChannelVideos(channelId, PAGE_SIZE, offset),
    enabled: channelId.length > 0,
    placeholderData: (prev) => prev,
  })
}

export function useVideoSongs(videoId: string, page: number) {
  const offset = page * PAGE_SIZE
  return useQuery({
    queryKey: ["videos", videoId, "songs", page],
    queryFn: () => api.listVideoSongs(videoId, PAGE_SIZE, offset),
    enabled: videoId.length > 0,
    placeholderData: (prev) => prev,
  })
}
