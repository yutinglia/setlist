import { Link, createFileRoute } from "@tanstack/react-router"

import { PAGE_SIZE, useChannels } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { pageSearchSchema } from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/")({
  validateSearch: pageSearchSchema,
  component: ChannelsPage,
})

function ChannelsPage() {
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = useChannels(page)

  return (
    <section className="animate-fade pt-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-3xl font-bold tracking-tight">
          {m.channels_heading()}
        </h1>
        <Link
          to="/channels/new"
          className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {m.channel_add_cta()}
        </Link>
      </div>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={m.channels_empty()}
          onRetry={() => void query.refetch()}
        >
          <ul className="divide-y divide-border/70">
            {query.data?.items.map((channel, i) => (
              <li
                key={channel.id}
                className={`animate-rise py-4 stagger-${Math.min((i % 4) + 1, 4)}`}
              >
                <Link
                  to="/channels/$channelId"
                  params={{ channelId: channel.id }}
                  className="group flex items-center gap-4 text-left"
                >
                  {channel.thumbnail_url ? (
                    <img
                      src={channel.thumbnail_url}
                      alt=""
                      className="size-12 rounded-full object-cover ring-1 ring-border"
                      loading="lazy"
                    />
                  ) : (
                    <span className="flex size-12 items-center justify-center rounded-full bg-secondary font-display text-sm font-semibold text-secondary-foreground">
                      {channel.name.slice(0, 1)}
                    </span>
                  )}
                  <span className="min-w-0">
                    <span className="block font-display text-lg font-semibold transition-colors group-hover:text-primary">
                      {channel.name}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {channel.id}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {query.data ? (
            <PaginationControls
              page={page}
              total={query.data.total}
              pageSize={PAGE_SIZE}
              disabled={query.isFetching}
              onPageChange={(next) =>
                void navigate({
                  search: { page: next || undefined },
                })
              }
            />
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
