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

const yyyymmdd = z
  .string()
  .regex(/^\d{8}$/)
  .optional()
  .catch(undefined)

/** Home search query (`?q=&page=&channel_id=&type=&date_from=&date_to=`). */
export const songSearchSchema = z.object({
  q: z.string().trim().max(200).optional().catch(undefined),
  page: z.coerce.number().int().min(0).max(MAX_PAGE).optional().catch(undefined),
  channel_id: z.string().trim().min(1).max(255).optional().catch(undefined),
  type: z.enum(["karaoke", "song"]).optional().catch(undefined),
  date_from: yyyymmdd,
  date_to: yyyymmdd,
})

export type PageSearch = z.infer<typeof pageSearchSchema>
export type ChannelVideosSearch = z.infer<typeof channelVideosSearchSchema>
export type SongSearch = z.infer<typeof songSearchSchema>

/** Convert HTML date input value (`YYYY-MM-DD`) to API/URL `YYYYMMDD`. */
export function htmlDateToYyyymmdd(value: string): string | undefined {
  const trimmed = value.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return undefined
  return trimmed.replaceAll("-", "")
}

/** Convert API/URL `YYYYMMDD` to HTML date input value (`YYYY-MM-DD`). */
export function yyyymmddToHtmlDate(value: string | undefined): string {
  if (!value || !/^\d{8}$/.test(value)) return ""
  return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
}
