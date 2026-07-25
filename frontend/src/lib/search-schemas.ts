import { z } from "zod"

const MAX_PAGE = 50_000

/** Shared offset pagination query (`?page=0`). Invalid values fall back to unset. */
export const pageSearchSchema = z.object({
  page: z.coerce.number().int().min(0).max(MAX_PAGE).optional().catch(undefined),
})

/** Channel detail tabs: karaoke streams vs song uploads (`?tab=&page=&has_song_list=`). */
export const channelVideosSearchSchema = z.object({
  tab: z.enum(["karaoke", "videos"]).optional().catch(undefined),
  page: z.coerce.number().int().min(0).max(MAX_PAGE).optional().catch(undefined),
  has_song_list: z.enum(["true", "false"]).optional().catch(undefined),
})

/** Home search query (`?q=&page=`). */
export const songSearchSchema = z.object({
  q: z.string().trim().max(200).optional().catch(undefined),
  page: z.coerce.number().int().min(0).max(MAX_PAGE).optional().catch(undefined),
})

export type PageSearch = z.infer<typeof pageSearchSchema>
export type ChannelVideosSearch = z.infer<typeof channelVideosSearchSchema>
export type SongSearch = z.infer<typeof songSearchSchema>
