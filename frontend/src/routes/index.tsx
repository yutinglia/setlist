import { createFileRoute } from "@tanstack/react-router"
import { useCallback, useEffect } from "react"

import { PAGE_SIZE, useSongSearch } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { SearchForm } from "@/components/search-form"
import { SongResultRow } from "@/components/song-result-row"
import { songSearchSchema } from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"
import { useUiStore } from "@/stores/ui-store"

export const Route = createFileRoute("/")({
  validateSearch: songSearchSchema,
  component: SearchPage,
})

function SearchPage() {
  const { q = "", page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const addRecent = useUiStore((s) => s.addRecentSearch)
  const query = useSongSearch(q, page)

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

  useEffect(() => {
    if (q && query.isSuccess) addRecent(q)
  }, [q, query.isSuccess, addRecent])

  return (
    <section className="flex flex-1 flex-col">
      {/* One composition: brand + tagline + search — hero signal, not a dashboard */}
      <div className="flex min-h-[min(72svh,40rem)] flex-col justify-center pt-8 pb-10">
        <p className="animate-rise font-display text-sm font-medium tracking-[0.2em] text-primary uppercase">
          {m.brand_full()}
        </p>
        <h1 className="animate-rise stagger-1 mt-3 font-display text-5xl leading-[0.95] font-bold tracking-tight text-foreground sm:text-6xl md:text-7xl">
          {m.brand_name()}
        </h1>
        <p className="animate-rise stagger-2 mt-4 max-w-xl text-base text-muted-foreground sm:text-lg">
          {m.tagline()}
        </p>
        <div className="animate-rise stagger-3 mt-8">
          <SearchForm
            initialQuery={q}
            onQueryChange={setQuery}
            autoFocus
          />
        </div>
      </div>

      <div className="animate-fade border-t border-border/60 pt-8">
        {!q ? (
          <p className="text-left text-sm text-muted-foreground">
            {m.empty_prompt()}
          </p>
        ) : (
          <>
            <div className="mb-4 flex items-baseline justify-between gap-3">
              <h2 className="font-display text-xl font-semibold">
                {m.results_heading()}
              </h2>
              {query.data ? (
                <p className="text-sm text-muted-foreground">
                  {m.results_count({ total: String(query.data.total) })}
                </p>
              ) : null}
            </div>

            <QueryState
              isLoading={query.isLoading}
              isError={query.isError}
              isEmpty={query.isSuccess && query.data.items.length === 0}
              emptyMessage={m.empty_results({ query: q })}
              onRetry={() => void query.refetch()}
            >
              <ul className="divide-y-0">
                {query.data?.items.map((song, i) => (
                  <SongResultRow key={song.id} song={song} index={i} />
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
                      search: (prev) => ({ ...prev, page: next || undefined }),
                    })
                  }
                />
              ) : null}
            </QueryState>
          </>
        )}
      </div>
    </section>
  )
}
