import { Clock3, RefreshCw } from "lucide-react"

import { useChannelIngestQueue } from "@/api/hooks"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatApiDateTime } from "@/lib/locale-format"
import { m } from "@/paraglide/messages"

export function ChannelIngestQueuePanel() {
  const queue = useChannelIngestQueue()
  const items = queue.data?.items ?? []
  const total = queue.data?.total ?? 0

  return (
    <section
      className="surface mt-6 overflow-hidden"
      aria-labelledby="channel-ingest-queue-title"
    >
      <div className="flex flex-col gap-4 border-b border-border/60 bg-secondary/35 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
            <Clock3 className="size-4" aria-hidden />
          </span>
          <div>
            <h2
              id="channel-ingest-queue-title"
              className="text-sm font-semibold"
            >
              {m.channel_add_queue_title()}
            </h2>
            <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted-foreground">
              {m.channel_add_queue_description()}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant="muted">
            {m.channel_add_queue_count({ count: total })}
          </Badge>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void queue.refetch()}
            disabled={queue.isFetching}
          >
            <RefreshCw
              className={queue.isFetching ? "animate-spin" : undefined}
              aria-hidden
            />
            {m.channel_add_queue_refresh()}
          </Button>
        </div>
      </div>

      <div aria-live="polite">
        {queue.isLoading ? (
          <p className="px-5 py-6 text-sm text-muted-foreground">
            {m.channel_add_queue_loading()}
          </p>
        ) : queue.isError ? (
          <p className="px-5 py-6 text-sm text-destructive" role="alert">
            {m.channel_add_queue_error()}
          </p>
        ) : items.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted-foreground">
            {m.channel_add_queue_empty()}
          </p>
        ) : (
          <ol className="divide-y divide-border/60">
            {items.map((item, index) => (
              <li key={item.id} className="flex gap-3 px-5 py-4">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 font-mono text-xs font-semibold text-primary">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <a
                    href={item.channel_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-11 items-center break-all font-mono text-sm font-semibold text-primary underline-offset-2 hover:underline"
                  >
                    {item.channel_url}
                  </a>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>
                      {m.channel_add_queue_position({ position: index + 1 })}
                    </span>
                    <span>
                      {m.channel_add_queue_attempts({
                        attempts: item.attempts,
                      })}
                    </span>
                    <span>
                      {m.channel_add_queue_queued_at({
                        time: formatApiDateTime(item.created_at),
                      })}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}
