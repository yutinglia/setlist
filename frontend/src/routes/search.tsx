import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useCallback, useMemo } from "react"

import { PAGE_SIZE, useSongSearch } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { PageMetadata } from "@/components/page-metadata"
import { QueryState } from "@/components/query-state"
import {
  SearchFilters,
  type SearchFilterValues,
} from "@/components/search-filters"
import { SearchForm } from "@/components/search-form"
import { SongResultCard } from "@/components/song-result-row"
import { useClampPage } from "@/hooks/use-clamp-page"
import { formatInteger } from "@/lib/locale-format"
import {
  parseChannelIds,
  serializeChannelIds,
  songSearchSchema,
} from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/search")({
  validateSearch: songSearchSchema,
  component: SearchPage,
})

function SearchPage() {
  const {
    q = "",
    page = 0,
    channel_ids,
    type,
    date_from,
    date_to,
  } = Route.useSearch()
  const navigate = Route.useNavigate()
  const selectedChannelIds = useMemo(
    () => parseChannelIds(channel_ids),
    [channel_ids],
  )
  const query = useSongSearch(q, page, {
    channelIds: selectedChannelIds,
    type,
    uploadDateFrom: date_from,
    uploadDateTo: date_to,
  })

  const changePage = useCallback(
    (next: number) => {
      void navigate({
        search: (prev) => ({ ...prev, page: next || undefined }),
        replace: true,
      })
    },
    [navigate],
  )
  useClampPage(page, query.data?.total, PAGE_SIZE, changePage)

  const setQuery = useCallback(
    (next: string) => {
      void navigate({
        search: (prev) => ({
          ...prev,
          q: next || undefined,
          page: next === q ? prev.page : undefined,
        }),
        replace: true,
      })
    },
    [navigate, q],
  )

  const setFilters = useCallback(
    (next: SearchFilterValues) => {
      void navigate({
        search: (prev) => ({
          ...prev,
          channel_ids: serializeChannelIds(next.channel_ids),
          type: next.type,
          date_from: next.date_from,
          date_to: next.date_to,
          page: undefined,
        }),
        replace: true,
      })
    },
    [navigate],
  )

  const hasSearchState = Boolean(
    q || page || channel_ids || type || date_from || date_to,
  )

  return (
    <section className="animate-fade flex flex-1 flex-col py-7 sm:py-10">
      <PageMetadata
        path="/search"
        title={`${m.search_page_heading()} | Setlist`}
        description={m.search_page_intro()}
        noIndex={hasSearchState}
      />

      <header className="max-w-3xl">
        <p className="eyebrow">{m.search_page_eyebrow()}</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
          {m.search_page_heading()}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
          {m.search_page_intro()}
        </p>
      </header>

      <div className="mt-6 max-w-5xl">
        <SearchForm
          initialQuery={q}
          onQuerySubmit={setQuery}
          suggestionFilters={{
            channelIds: selectedChannelIds,
            type,
            uploadDateFrom: date_from,
            uploadDateTo: date_to,
          }}
          autoFocus
        />
        <SearchFilters
          filters={{
            channel_ids: selectedChannelIds,
            type,
            date_from,
            date_to,
          }}
          onChange={setFilters}
        />
      </div>

      <div className="mt-9 border-t border-border pt-7 sm:mt-10 sm:pt-8">
        {q ? (
          <>
            <div className="mb-7 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="eyebrow">{m.results_heading()}</p>
                <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
                  {m.results_for({ query: q })}
                </h2>
              </div>
              {query.data ? (
                <p className="text-xs text-muted-foreground tabular-nums">
                  {m.results_count({ total: formatInteger(query.data.total) })}
                </p>
              ) : null}
            </div>

            <QueryState
              isLoading={query.isLoading}
              isError={query.isError}
              isEmpty={query.isSuccess && query.data.items.length === 0}
              emptyMessage={m.empty_results({ query: q })}
              onRetry={() => void query.refetch()}
              loadingLayout="grid"
            >
              <ul className="media-grid">
                {query.data?.items.map((song, index) => (
                  <SongResultCard key={song.id} song={song} index={index} />
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
          </>
        ) : (
          <div className="grid min-h-60 place-items-center rounded-2xl border border-dashed border-border bg-card/50 px-6 py-12 text-center">
            <div className="max-w-md">
              <span className="mx-auto grid size-12 place-items-center rounded-full bg-primary/10 text-primary">
                <Search className="size-5" aria-hidden />
              </span>
              <h2 className="mt-4 text-xl font-bold">
                {m.search_empty_heading()}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {m.search_empty_body()}
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
