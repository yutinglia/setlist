import { createFileRoute } from "@tanstack/react-router"
import { ExternalLink, HeartHandshake, ListMusic, Video } from "lucide-react"
import { useCallback } from "react"

import { PAGE_SIZE, useSetlistContributors } from "@/api/hooks"
import { PageMetadata } from "@/components/page-metadata"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { useClampPage } from "@/hooks/use-clamp-page"
import { formatInteger } from "@/lib/locale-format"
import { pageSearchSchema } from "@/lib/search-schemas"
import { youtubeChannelUrl } from "@/lib/youtube"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/thanks")({
  validateSearch: pageSearchSchema,
  component: ThanksPage,
})

function ThanksPage() {
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = useSetlistContributors(page)
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
    <section className="animate-fade py-7 sm:py-10">
      <PageMetadata
        path="/thanks"
        title={`${m.thanks_heading()} | Setlist`}
        description={m.thanks_intro()}
      />

      <header className="page-header md:grid-cols-[minmax(0,1fr)_auto] md:items-end md:gap-10">
        <div className="max-w-3xl">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-2xl bg-primary/10 text-primary">
              <HeartHandshake className="size-5" aria-hidden />
            </span>
            <p className="eyebrow">{m.thanks_eyebrow()}</p>
          </div>
          <h1 className="page-title mt-4">{m.thanks_heading()}</h1>
          <p className="page-intro mt-4">{m.thanks_intro()}</p>
        </div>
        {query.data ? (
          <p className="w-fit rounded-xl border border-primary/20 bg-primary/8 px-4 py-3 text-sm font-semibold text-primary tabular-nums">
            {m.thanks_total({ count: formatInteger(query.data.total) })}
          </p>
        ) : null}
      </header>

      <div className="mt-10">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={m.thanks_empty()}
          loadingLayout="grid"
          onRetry={() => void query.refetch()}
        >
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {query.data?.items.map((contributor, index) => (
              <li
                key={contributor.author_id}
                className={`surface animate-rise overflow-hidden stagger-${Math.min((index % 4) + 1, 4)}`}
              >
                <a
                  href={youtubeChannelUrl(contributor.author_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="group block min-h-44 p-5 outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                  aria-label={m.thanks_open_channel({
                    author: contributor.author,
                  })}
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block truncate text-lg font-bold tracking-tight transition-colors group-hover:text-primary">
                        {contributor.author}
                      </span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {m.thanks_youtube_commenter()}
                      </span>
                    </span>
                    <ExternalLink
                      className="mt-1 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                      aria-hidden
                    />
                  </span>
                  <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-border/60 pt-4">
                    <div>
                      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <ListMusic className="size-3.5" aria-hidden />
                        {m.thanks_songs()}
                      </dt>
                      <dd className="mt-1 text-xl font-bold tabular-nums">
                        {formatInteger(contributor.song_count)}
                      </dd>
                    </div>
                    <div>
                      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Video className="size-3.5" aria-hidden />
                        {m.thanks_setlists()}
                      </dt>
                      <dd className="mt-1 text-xl font-bold tabular-nums">
                        {formatInteger(contributor.video_count)}
                      </dd>
                    </div>
                  </dl>
                </a>
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

      <p className="surface-subtle mx-auto mt-10 max-w-3xl px-5 py-4 text-center text-xs leading-6 text-muted-foreground">
        {m.thanks_note()}
      </p>
    </section>
  )
}
