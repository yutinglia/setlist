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
    <section className="animate-fade flex flex-1 flex-col py-10 sm:py-14">
      <PageMetadata
        path="/search"
        title={`${m.search_page_heading()} | Setlist`}
        description={m.search_page_intro()}
        noIndex={hasSearchState}
      />

      <header className="max-w-3xl">
        <p className="eyebrow">{m.search_page_eyebrow()}</p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
          {m.search_page_heading()}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
          {m.search_page_intro()}
        </p>
      </header>

      <div className="mt-7 max-w-5xl">
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

      <div className="mt-10 border-t border-border/70 pt-8 sm:mt-12 sm:pt-10">
        {q ? (
          <>
            <div className="mb-7 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="eyebrow">{m.results_heading()}</p>
                <h2 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
                  {m.results_for({ query: q })}
                </h2>
              </div>
              {query.data ? (
                <p className="font-mono text-xs text-muted-foreground">
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
          <div className="surface grid min-h-64 place-items-center px-6 py-12 text-center">
            <div className="max-w-md">
              <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-primary/10 text-primary">
                <Search className="size-5" aria-hidden />
              </span>
              <h2 className="mt-4 font-display text-xl font-bold">
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
