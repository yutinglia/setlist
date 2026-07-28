/** Add a YouTube `t` query parameter for `mm:ss` / `hh:mm:ss` timestamps. */
export function youtubeUrlAtTimestamp(
  baseUrl: string,
  timestamp: string | null | undefined,
): string {
  const seconds = timestampToSeconds(timestamp)
  if (seconds === null) return baseUrl

  try {
    const url = new URL(baseUrl)
    url.searchParams.set("t", `${seconds}s`)
    return url.toString()
  } catch {
    const separator = baseUrl.includes("?") ? "&" : "?"
    return `${baseUrl}${separator}t=${seconds}s`
  }
}

/** Public YouTube thumbnail for a known video id. */
export function youtubeThumbnailUrl(videoId: string): string {
  return `https://i.ytimg.com/vi/${encodeURIComponent(videoId)}/hqdefault.jpg`
}

/** Canonical YouTube watch URL without a playback timestamp. */
export function youtubeVideoUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`
}

/** Stable channel URL for a yt-dlp comment `author_id`. */
export function youtubeChannelUrl(authorId: string): string {
  return `https://www.youtube.com/channel/${encodeURIComponent(authorId)}`
}

/** Direct link to a public YouTube comment on its source video. */
export function youtubeCommentUrl(
  videoId: string,
  commentId: string,
): string {
  const url = new URL(youtubeVideoUrl(videoId))
  url.searchParams.set("lc", commentId)
  return url.toString()
}

function timestampToSeconds(
  timestamp: string | null | undefined,
): number | null {
  const parts = (timestamp ?? "").trim().split(":").map(Number)
  if (
    (parts.length !== 2 && parts.length !== 3) ||
    parts.some((part) => !Number.isInteger(part) || part < 0)
  ) {
    return null
  }

  if (parts.length === 2) {
    const [minutes, seconds] = parts
    if (seconds! >= 60) return null
    return minutes! * 60 + seconds!
  }

  const [hours, minutes, seconds] = parts
  if (minutes! >= 60 || seconds! >= 60) return null
  return hours! * 3600 + minutes! * 60 + seconds!
}
