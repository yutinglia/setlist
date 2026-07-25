/** Page index items for numbered pagination (0-based current page). */
export type PageItem = number | "ellipsis"

/**
 * Build a compact page window with bookends and ellipses.
 * Example (current=6, total=12, 0-based): [0, 1, 2, "ellipsis", 5, 6, "ellipsis", 10, 11]
 * which renders as 1 2 3 … 6 7 … 11 12.
 */
export function buildPageItems(
  current0Based: number,
  totalPages: number,
): PageItem[] {
  if (totalPages <= 0) return []
  const current = Math.min(Math.max(0, current0Based), totalPages - 1)

  if (totalPages <= 9) {
    return Array.from({ length: totalPages }, (_, i) => i)
  }

  const pages = new Set<number>()
  pages.add(0)
  pages.add(1)
  pages.add(2)
  pages.add(totalPages - 3)
  pages.add(totalPages - 2)
  pages.add(totalPages - 1)
  for (let i = current - 1; i <= current + 1; i++) {
    if (i >= 0 && i < totalPages) pages.add(i)
  }

  const sorted = [...pages].sort((a, b) => a - b)
  const items: PageItem[] = []
  for (let i = 0; i < sorted.length; i++) {
    const page = sorted[i]!
    if (i > 0 && page - sorted[i - 1]! > 1) {
      items.push("ellipsis")
    }
    items.push(page)
  }
  return items
}

/** All 0-based page indices for a page dropdown (`0 .. totalPages-1`). */
export function buildPageOptions(totalPages: number): number[] {
  if (totalPages <= 0) return []
  return Array.from({ length: totalPages }, (_, i) => i)
}
