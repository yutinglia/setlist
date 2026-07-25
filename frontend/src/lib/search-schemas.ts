import { z } from "zod"

const MAX_PAGE = 50_000

/** Allowed page sizes for the channel videos list. */
export const CHANNEL_PAGE_SIZES = [10, 20, 50] as const
export type ChannelPageSize = (typeof CHANNEL_PAGE_SIZES)[number]
export const DEFAULT_CHANNEL_PAGE_SIZE: ChannelPageSize = 10

/** Shared offset pagination query (`?page=0`). Invalid values fall back to unset. */
export const pageSearchSchema = z.object({
  page: z.coerce.number().int().min(0).max(MAX_PAGE).optional().catch(undefined),
})

const channelPageSizeSchema = z
  .coerce.number()
  .pipe(z.union([z.literal(10), z.literal(20), z.literal(50)]))
  .optional()
  .catch(undefined)

/** Channel detail tabs: karaoke streams vs song uploads (`?tab=&page=&has_song_list=&limit=`). */
export const channelVideosSearchSchema = z.object({
  tab: z.enum(["karaoke", "videos"]).optional().catch(undefined),
  page: z.coerce.number().int().min(0).max(MAX_PAGE).optional().catch(undefined),
  has_song_list: z.enum(["true", "false"]).optional().catch(undefined),
  limit: channelPageSizeSchema,
})

export type ChannelVideosSearch = z.infer<typeof channelVideosSearchSchema>

/** Inputs for building channel-video URL search (omit defaults for a clean URL). */
export type ChannelVideosSearchInput = {
  tab?: "karaoke" | "videos"
  page?: number
  has_song_list?: "true" | "false"
  limit?: number
}

/** Serialize channel video list search, omitting default tab/page/limit. */
export function toChannelVideosSearch(
  input: ChannelVideosSearchInput,
): ChannelVideosSearch {
  const limit =
    input.limit !== undefined &&
    input.limit !== DEFAULT_CHANNEL_PAGE_SIZE &&
    (CHANNEL_PAGE_SIZES as readonly number[]).includes(input.limit)
      ? (input.limit as ChannelPageSize)
      : undefined
  return {
    tab: input.tab === "videos" ? "videos" : undefined,
    page: input.page && input.page > 0 ? input.page : undefined,
    has_song_list: input.has_song_list,
    limit,
  }
}

/** Resolve effective page size from validated search (default 10). */
export function resolveChannelPageSize(
  limit: ChannelVideosSearch["limit"],
): ChannelPageSize {
  return limit ?? DEFAULT_CHANNEL_PAGE_SIZE
}

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
