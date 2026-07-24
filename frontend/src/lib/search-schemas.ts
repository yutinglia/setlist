import { z } from "zod"

/** Shared offset pagination query (`?page=0`). Invalid values fall back to unset. */
export const pageSearchSchema = z.object({
  page: z.coerce.number().int().min(0).optional().catch(undefined),
})

/** Channel detail tabs: karaoke streams vs song uploads (`?tab=&page=`). */
export const channelVideosSearchSchema = z.object({
  tab: z.enum(["karaoke", "videos"]).optional().catch(undefined),
  page: z.coerce.number().int().min(0).optional().catch(undefined),
})

/** Home search query (`?q=&page=`). */
export const songSearchSchema = z.object({
  q: z.string().optional().catch(undefined),
  page: z.coerce.number().int().min(0).optional().catch(undefined),
})

export type PageSearch = z.infer<typeof pageSearchSchema>
export type ChannelVideosSearch = z.infer<typeof channelVideosSearchSchema>
export type SongSearch = z.infer<typeof songSearchSchema>
