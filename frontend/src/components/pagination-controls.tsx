import { Button } from "@/components/ui/button"
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

  return (
    <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground">
        {m.pagination_page({ page: String(page + 1), pages: String(pages) })}
      </p>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || page <= 0}
          onClick={() => onPageChange(page - 1)}
        >
          {m.pagination_prev()}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || page + 1 >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          {m.pagination_next()}
        </Button>
      </div>
    </div>
  )
}
