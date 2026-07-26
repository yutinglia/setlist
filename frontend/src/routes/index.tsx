import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowRight,
  Disc3,
  ListMusic,
  Sparkles,
  Users,
} from "lucide-react"
import { useCallback, useEffect } from "react"

import {
  PAGE_SIZE,
  useChannelOptions,
  useSongSearch,
  useSummaryReport,
} from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import {
  SearchFilters,
  type SearchFilterValues,
} from "@/components/search-filters"
import { SearchForm } from "@/components/search-form"
import { SongResultRow } from "@/components/song-result-row"
import { useClampPage } from "@/hooks/use-clamp-page"
import { songSearchSchema } from "@/lib/search-schemas"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"
import { useUiStore } from "@/stores/ui-store"

export const Route = createFileRoute("/")({
  validateSearch: songSearchSchema,
  component: SearchPage,
})

const integer = new Intl.NumberFormat()

function SearchPage() {
  const {
    q = "",
    page = 0,
    channel_id,
    type,
    date_from,
    date_to,
  } = Route.useSearch()
  const navigate = Route.useNavigate()
  const addRecent = useUiStore((state) => state.addRecentSearch)
  const query = useSongSearch(q, page, {
    channelId: channel_id,
    type,
    uploadDateFrom: date_from,
    uploadDateTo: date_to,
  })
  const summary = useSummaryReport()
  const channels = useChannelOptions()

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
          channel_id: next.channel_id,
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

  useEffect(() => {
    if (q && query.isSuccess) addRecent(q)
  }, [q, query.isSuccess, addRecent])

  const channelPreview = channels.data?.items.slice(0, 4) ?? []

  return (
    <section className="flex flex-1 flex-col">
      <div
        className={cn(
          "relative grid items-center gap-10 py-12 lg:grid-cols-[minmax(0,1.25fr)_minmax(19rem,0.75fr)] lg:gap-16",
          q ? "lg:py-14" : "min-h-[min(720px,78svh)] lg:py-20",
        )}
      >
        <div className="relative z-10 max-w-3xl">
          <p className="eyebrow animate-rise">{m.home_eyebrow()}</p>
          <h1 className="animate-rise stagger-1 mt-4 max-w-3xl font-display text-[clamp(2.8rem,7vw,6.6rem)] leading-[0.92] font-bold tracking-[-0.055em]">
            {m.home_headline()}
          </h1>
          <p className="animate-rise stagger-2 mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            {m.home_intro()}
          </p>

          <div className="animate-rise stagger-3 mt-8 max-w-3xl">
            <SearchForm
              initialQuery={q}
              onQueryChange={setQuery}
              autoFocus
            />
            <SearchFilters
              filters={{ channel_id, type, date_from, date_to }}
              onChange={setFilters}
            />
          </div>
        </div>

        <LibraryPanel
          songs={summary.data?.songs.total}
          setlists={summary.data?.analysis.with_setlist}
          channels={summary.data?.channels}
          loading={summary.isLoading}
        />
      </div>

      <div className="border-t border-border/70 py-10 sm:py-14">
        {!q ? (
          <div className="animate-fade">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="eyebrow">{m.home_explore_title()}</p>
                <h2 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
                  {m.empty_prompt()}
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  {m.home_explore_hint()}
                </p>
              </div>
              <Link
                to="/channels"
                className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
              >
                {m.home_browse_all()}
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </div>

            {channelPreview.length > 0 ? (
              <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {channelPreview.map((channel, index) => (
                  <Link
                    key={channel.id}
                    to="/channels/$channelId"
                    params={{ channelId: channel.id }}
                    className={cn(
                      "surface group flex min-w-0 items-center gap-3 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/30",
                      `animate-rise stagger-${Math.min(index + 1, 4)}`,
                    )}
                  >
                    {channel.thumbnail_url ? (
                      <img
                        src={channel.thumbnail_url}
                        alt=""
                        className="size-11 rounded-xl object-cover ring-1 ring-border"
                        loading="lazy"
                      />
                    ) : (
                      <span className="grid size-11 place-items-center rounded-xl bg-primary/10 font-display font-bold text-primary">
                        {channel.name.slice(0, 1)}
                      </span>
                    )}
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">
                        {channel.name}
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[0.65rem] text-muted-foreground">
                        {channel.id}
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <>
            <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="eyebrow">{m.results_heading()}</p>
                <h2 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">
                  {m.results_for({ query: q })}
                </h2>
              </div>
              {query.data ? (
                <p className="font-mono text-xs text-muted-foreground">
                  {m.results_count({ total: integer.format(query.data.total) })}
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
              <ul className="grid gap-3">
                {query.data?.items.map((song, index) => (
                  <SongResultRow key={song.id} song={song} index={index} />
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
        )}
      </div>
    </section>
  )
}

function LibraryPanel({
  songs,
  setlists,
  channels,
  loading,
}: {
  songs?: number
  setlists?: number
  channels?: number
  loading: boolean
}) {
  const metrics = [
    [ListMusic, songs, m.home_library_songs()],
    [Disc3, setlists, m.home_library_setlists()],
    [Users, channels, m.home_library_channels()],
  ] as const

  return (
    <aside className="surface animate-rise stagger-4 relative hidden overflow-hidden p-6 lg:block">
      <div className="absolute -top-20 -right-20 size-52 rounded-full bg-primary/15 blur-3xl" />
      <div className="absolute -bottom-24 -left-16 size-48 rounded-full bg-accent/15 blur-3xl" />
      <div className="relative">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="eyebrow">{m.home_library_live()}</p>
            <h2 className="mt-2 font-display text-xl font-bold">
              {m.home_library_title()}
            </h2>
          </div>
          <div className="flex h-8 items-end gap-1" aria-hidden>
            {[18, 28, 22, 31, 15].map((height, index) => (
              <span
                key={height}
                className="equalizer-bar w-1 rounded-full bg-accent"
                style={{
                  height,
                  animationDelay: `${index * -0.14}s`,
                }}
              />
            ))}
          </div>
        </div>

        <dl className="mt-8 divide-y divide-border/60">
          {metrics.map(([Icon, value, label]) => (
            <div
              key={label}
              className="flex items-center justify-between gap-4 py-4 first:pt-0"
            >
              <dt className="flex items-center gap-2.5 text-sm text-muted-foreground">
                <span className="grid size-8 place-items-center rounded-lg bg-secondary text-primary">
                  <Icon className="size-4" aria-hidden />
                </span>
                {label}
              </dt>
              <dd className="font-display text-2xl font-bold tabular-nums">
                {loading || value === undefined ? "—" : integer.format(value)}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-primary/15 bg-primary/5 p-3 text-xs leading-relaxed text-muted-foreground">
          <Sparkles className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
          <p>{m.home_library_fallback()}</p>
        </div>

        <Link
          to="/summary"
          className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
        >
          {m.nav_summary()}
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
    </aside>
  )
}
