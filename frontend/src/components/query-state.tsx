import type { ReactNode } from "react"
import { AlertCircle, Inbox } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { m } from "@/paraglide/messages"

type Props = {
  isLoading?: boolean
  isError?: boolean
  isEmpty?: boolean
  emptyMessage: string
  onRetry?: () => void
  loadingLayout?: "rows" | "grid"
  children: ReactNode
}

export function QueryState({
  isLoading,
  isError,
  isEmpty,
  emptyMessage,
  onRetry,
  loadingLayout = "rows",
  children,
}: Props) {
  if (isLoading) {
    if (loadingLayout === "grid") {
      return (
        <div className="media-grid" aria-busy aria-label={m.loading()}>
          {Array.from({ length: 8 }, (_, index) => (
            <div key={index}>
              <Skeleton className="aspect-video w-full rounded-xl bg-muted" />
              <Skeleton className="mt-3 h-4 w-5/6 rounded-md bg-muted" />
              <Skeleton className="mt-2 h-3 w-1/2 rounded-md bg-muted" />
            </div>
          ))}
        </div>
      )
    }
    return (
      <div className="grid gap-3" aria-busy aria-label={m.loading()}>
        <Skeleton className="h-24 w-full rounded-2xl bg-muted" />
        <Skeleton className="h-24 w-full rounded-2xl bg-muted" />
        <Skeleton className="h-24 w-full rounded-2xl bg-muted" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="surface px-5 py-8 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-xl bg-destructive/10 text-destructive">
          <AlertCircle className="size-5" aria-hidden />
        </span>
        <p className="mt-4 text-sm text-destructive">{m.error_generic()}</p>
        {onRetry ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={onRetry}
          >
            {m.error_retry()}
          </Button>
        ) : null}
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div className="surface px-5 py-12 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary text-muted-foreground">
          <Inbox className="size-5" aria-hidden />
        </span>
        <p className="mx-auto mt-4 max-w-md text-sm text-muted-foreground">
          {emptyMessage}
        </p>
      </div>
    )
  }

  return <>{children}</>
}
