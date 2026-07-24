import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { m } from "@/paraglide/messages"

type Props = {
  isLoading?: boolean
  isError?: boolean
  isEmpty?: boolean
  emptyMessage: string
  onRetry?: () => void
  children: ReactNode
}

export function QueryState({
  isLoading,
  isError,
  isEmpty,
  emptyMessage,
  onRetry,
  children,
}: Props) {
  if (isLoading) {
    return (
      <div className="space-y-3" aria-busy aria-label={m.loading()}>
        <Skeleton className="h-16 w-full bg-muted" />
        <Skeleton className="h-16 w-full bg-muted" />
        <Skeleton className="h-16 w-[85%] bg-muted" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-6 text-left">
        <p className="text-sm text-destructive">{m.error_generic()}</p>
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
      <p className="py-8 text-left text-sm text-muted-foreground">{emptyMessage}</p>
    )
  }

  return <>{children}</>
}
