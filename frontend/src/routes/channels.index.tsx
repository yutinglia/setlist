import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowRight, Plus, Radio } from "lucide-react"
import { useCallback } from "react"

import { PAGE_SIZE, useAuthSession, useChannels } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { buttonVariants } from "@/components/ui/button"
import { useClampPage } from "@/hooks/use-clamp-page"
import { pageSearchSchema } from "@/lib/search-schemas"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/")({
  validateSearch: pageSearchSchema,
  component: ChannelsPage,
})

const integer = new Intl.NumberFormat()

function ChannelsPage() {
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = useChannels(page)
  const auth = useAuthSession()
  const canManage =
    auth.data?.authenticated === true &&
    auth.data.role === "admin" &&
    auth.data.management_enabled
  const changePage = useCallback(
    (next: number) => {
      void navigate({
        search: { page: next || undefined },
        replace: true,
      })
    },
    [navigate],
  )
  useClampPage(page, query.data?.total, PAGE_SIZE, changePage)

  return (
    <section className="animate-fade py-10 sm:py-14">
      <header className="flex flex-col gap-5 border-b border-border/70 pb-8 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">{m.home_explore_title()}</p>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
            {m.channels_heading()}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            {m.channels_hint()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {query.data ? (
            <span className="font-mono text-xs text-muted-foreground">
              {m.channels_count({ total: integer.format(query.data.total) })}
            </span>
          ) : null}
          {canManage ? (
            <Link
              to="/channels/new"
              className={cn(buttonVariants(), "inline-flex")}
            >
              <Plus aria-hidden />
              {m.channel_add_cta()}
            </Link>
          ) : null}
        </div>
      </header>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={m.channels_empty()}
          onRetry={() => void query.refetch()}
        >
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {query.data?.items.map((channel, index) => (
              <li
                key={channel.id}
                className={`animate-rise stagger-${Math.min((index % 4) + 1, 4)}`}
              >
                <Link
                  to="/channels/$channelId"
                  params={{ channelId: channel.id }}
                  className="surface group flex h-full min-h-32 items-center gap-4 p-5 transition-all hover:-translate-y-0.5 hover:border-primary/30"
                >
                  <span className="relative shrink-0">
                    {channel.thumbnail_url ? (
                      <img
                        src={channel.thumbnail_url}
                        alt=""
                        className="size-16 rounded-2xl object-cover ring-1 ring-border"
                        loading="lazy"
                      />
                    ) : (
                      <span className="grid size-16 place-items-center rounded-2xl bg-primary/10 font-display text-xl font-bold text-primary">
                        {channel.name.slice(0, 1)}
                      </span>
                    )}
                    <span className="absolute -right-1 -bottom-1 grid size-6 place-items-center rounded-lg border-2 border-card bg-accent text-accent-foreground">
                      <Radio className="size-3" aria-hidden />
                    </span>
                  </span>

                  <span className="min-w-0 flex-1 text-left">
                    <span className="block truncate font-display text-lg font-bold transition-colors group-hover:text-primary">
                      {channel.name}
                    </span>
                    <span className="mt-1 block truncate font-mono text-[0.65rem] text-muted-foreground">
                      {channel.id}
                    </span>
                  </span>
                  <ArrowRight
                    className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary"
                    aria-hidden
                  />
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
              onPageChange={changePage}
            />
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
