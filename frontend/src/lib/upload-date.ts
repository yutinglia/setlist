/** Helpers for YouTube ``upload_date`` values (``YYYYMMDD`` or ISO-ish strings). */

export function compareUploadDateDesc(
  a: string | null | undefined,
  b: string | null | undefined,
): number {
  const left = (a ?? "").trim()
  const right = (b ?? "").trim()
  if (!left && !right) return 0
  if (!left) return 1 // nulls last
  if (!right) return -1
  return right.localeCompare(left)
}

/** Format ``YYYYMMDD`` as ``YYYY-MM-DD``; pass through other non-empty strings. */
export function formatUploadDate(
  uploadDate: string | null | undefined,
): string | null {
  const text = (uploadDate ?? "").trim()
  if (!text) return null
  if (/^\d{8}$/.test(text)) {
    return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`
  }
  return text
}

/** ISO date (``YYYY-MM-DD``) for ``<time dateTime>``, or undefined when unknown. */
export function uploadDateTimeAttr(
  uploadDate: string | null | undefined,
  precision?: "exact" | "approximate" | null,
): string | undefined {
  // An approximate relative date should not be machine-readable as an exact
  // calendar date in <time dateTime>.
  if (precision === "approximate") return undefined
  return formatUploadDate(uploadDate) ?? undefined
}

export function sortVideosByUploadDateDesc<
  T extends { upload_date?: string | null; id?: string },
>(videos: readonly T[]): T[] {
  return [...videos].sort((a, b) => {
    const byDate = compareUploadDateDesc(a.upload_date, b.upload_date)
    if (byDate !== 0) return byDate
    return (a.id ?? "").localeCompare(b.id ?? "")
  })
}
