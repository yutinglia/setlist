import { useId } from "react"

import { Button } from "@/components/ui/button"
import { buildPageItems, buildPageOptions } from "@/lib/pagination"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

type Props = {
  page: number
  total: number
  pageSize: number
  onPageChange: (page: number) => void
  disabled?: boolean
  /** When set, always show a page-size select (even if page nav is hidden). */
  pageSizeOptions?: readonly number[]
  onPageSizeChange?: (size: number) => void
}

const selectClassName = cn(
  "h-8 rounded-md border border-input bg-transparent px-2 text-sm shadow-xs outline-none",
  "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
  "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
)

export function PaginationControls({
  page,
  total,
  pageSize,
  onPageChange,
  disabled,
  pageSizeOptions,
  onPageSizeChange,
}: Props) {
  const pageSelectId = useId()
  const sizeSelectId = useId()
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const showPageNav = total > pageSize
  const showSizeSelect =
    pageSizeOptions !== undefined && pageSizeOptions.length > 0

  if (!showPageNav && !showSizeSelect) return null

  const items = buildPageItems(page, pages)
  const options = buildPageOptions(pages)
  const lastPage = pages - 1
  const atStart = page <= 0
  const atEnd = page >= lastPage

  return (
    <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-3">
        {showPageNav ? (
          <>
            <p className="text-sm text-muted-foreground">
              {m.pagination_page({
                page: String(page + 1),
                pages: String(pages),
              })}
            </p>
            <label className="sr-only" htmlFor={pageSelectId}>
              {m.pagination_select_label()}
            </label>
            <select
              id={pageSelectId}
              className={selectClassName}
              value={String(page)}
              disabled={disabled}
              aria-label={m.pagination_select_label()}
              onChange={(e) => {
                const next = Number(e.target.value)
                if (Number.isFinite(next) && next !== page) onPageChange(next)
              }}
            >
              {options.map((p) => (
                <option key={p} value={p}>
                  {p + 1}
                </option>
              ))}
            </select>
          </>
        ) : null}
        {showSizeSelect ? (
          <div className="flex items-center gap-2">
            <label
              className="text-sm text-muted-foreground"
              htmlFor={sizeSelectId}
            >
              {m.pagination_page_size_label()}
            </label>
            <select
              id={sizeSelectId}
              className={selectClassName}
              value={String(pageSize)}
              disabled={disabled}
              aria-label={m.pagination_page_size_label()}
              onChange={(e) => {
                const next = Number(e.target.value)
                if (
                  Number.isFinite(next) &&
                  next !== pageSize &&
                  onPageSizeChange
                ) {
                  onPageSizeChange(next)
                }
              }}
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>
      {showPageNav ? (
        <nav
          className="flex flex-wrap items-center gap-1"
          aria-label={m.pagination_nav_label()}
        >
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled || atStart}
            aria-label={m.pagination_first()}
            onClick={() => onPageChange(0)}
          >
            {"<<"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled || atStart}
            aria-label={m.pagination_prev()}
            onClick={() => onPageChange(page - 1)}
          >
            {"<"}
          </Button>
          {items.map((item, index) =>
            item === "ellipsis" ? (
              <span
                key={`ellipsis-${index}`}
                className="px-1.5 text-sm text-muted-foreground"
                aria-hidden
              >
                …
              </span>
            ) : (
              <Button
                key={item}
                type="button"
                variant={item === page ? "secondary" : "outline"}
                size="sm"
                disabled={disabled}
                aria-label={m.pagination_goto({ page: String(item + 1) })}
                aria-current={item === page ? "page" : undefined}
                onClick={() => onPageChange(item)}
              >
                {item + 1}
              </Button>
            ),
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled || atEnd}
            aria-label={m.pagination_next()}
            onClick={() => onPageChange(page + 1)}
          >
            {">"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled || atEnd}
            aria-label={m.pagination_last()}
            onClick={() => onPageChange(lastPage)}
          >
            {">>"}
          </Button>
        </nav>
      ) : null}
    </div>
  )
}
