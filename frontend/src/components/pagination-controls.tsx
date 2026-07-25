import { Button } from "@/components/ui/button"
import { buildPageItems } from "@/lib/pagination"
import { m } from "@/paraglide/messages"

type Props = {
  page: number
  total: number
  pageSize: number
  onPageChange: (page: number) => void
  disabled?: boolean
}

export function PaginationControls({
  page,
  total,
  pageSize,
  onPageChange,
  disabled,
}: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) return null

  const items = buildPageItems(page, pages)
  const lastPage = pages - 1
  const atStart = page <= 0
  const atEnd = page >= lastPage

  return (
    <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">
        {m.pagination_page({ page: String(page + 1), pages: String(pages) })}
      </p>
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
    </div>
  )
}
