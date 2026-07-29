import { Link, createFileRoute } from "@tanstack/react-router"
import { MessageSquarePlus, Plus } from "lucide-react"
import { useCallback } from "react"

import { PAGE_SIZE, useAuthSession, useChannels } from "@/api/hooks"
import { ChannelCard } from "@/components/channel-card"
import { ChannelRequestNotice } from "@/components/channel-request-notice"
import { PaginationControls } from "@/components/pagination-controls"
import { PageMetadata } from "@/components/page-metadata"
import { QueryState } from "@/components/query-state"
import { buttonVariants } from "@/components/ui/button"
import { useClampPage } from "@/hooks/use-clamp-page"
import { formatInteger } from "@/lib/locale-format"
import { CHANNEL_REQUEST_URL } from "@/lib/public-config"
import { pageSearchSchema } from "@/lib/search-schemas"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/")({
  validateSearch: pageSearchSchema,
  component: ChannelsPage,
})

function ChannelsPage() {
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = useChannels(page)
  const auth = useAuthSession()
  const isAdmin =
    auth.data?.authenticated === true && auth.data.role === "admin"
  const canManage = isAdmin && auth.data?.management_enabled === true
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
      <PageMetadata
        path="/channels"
        title={`${m.channels_heading()} | Setlist`}
        description={m.channels_hint()}
        noIndex={page > 0}
      />
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
              {m.channels_count({ total: formatInteger(query.data.total) })}
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
          ) : !auth.isLoading && !isAdmin ? (
            <a
              href={CHANNEL_REQUEST_URL}
              target="_blank"
              rel="noreferrer"
              className={cn(
                buttonVariants({ variant: "outline" }),
                "inline-flex",
              )}
            >
              <MessageSquarePlus aria-hidden />
              {m.channel_request_contact_cta()}
            </a>
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
          loadingLayout="grid"
        >
          <ul className="media-grid">
            {query.data?.items.map((channel, index) => (
              <ChannelCard
                key={channel.id}
                channel={channel}
                index={index}
              />
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

      {!auth.isLoading && !isAdmin ? (
        <ChannelRequestNotice className="mt-12" />
      ) : null}
    </section>
  )
}
