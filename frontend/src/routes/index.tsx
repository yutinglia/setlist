import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowRight,
  Clock3,
  ListMusic,
  Radio,
  Search,
  Users,
} from "lucide-react"

import { useRecentUpdates, useSummaryReport } from "@/api/hooks"
import { PageMetadata } from "@/components/page-metadata"
import { SearchForm } from "@/components/search-form"
import { SongResultCard } from "@/components/song-result-row"
import { buttonVariants } from "@/components/ui/button"
import { formatInteger } from "@/lib/locale-format"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  const navigate = Route.useNavigate()
  const summary = useSummaryReport()
  const recent = useRecentUpdates()

  function submit(query: string) {
    const q = query.trim()
    if (!q) return
    void navigate({
      to: "/search",
      search: { q },
    })
  }

  return (
    <section className="flex flex-1 flex-col py-8 sm:py-12 lg:py-14">
      <PageMetadata
        path="/"
        title={m.meta_default_title()}
        description={m.home_intro()}
      />
      <div className="animate-rise relative mx-auto w-full max-w-5xl overflow-hidden rounded-[2rem] border border-border bg-card px-5 py-12 text-center shadow-[0_20px_70px_-55px_rgba(0,0,0,0.65)] sm:px-10 sm:py-16 lg:px-16 lg:py-20">
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
          <span className="absolute -top-32 -left-28 size-72 rounded-full bg-primary/8 blur-3xl" />
          <span className="absolute -right-24 -bottom-40 size-80 rounded-full bg-primary/6 blur-3xl" />
          <span className="absolute top-9 left-1/2 flex h-7 -translate-x-1/2 items-end gap-1 opacity-25">
            {[3, 6, 10, 16, 9, 20, 12, 7, 14, 5, 3].map((height, index) => (
              <span
                key={`${height}-${index}`}
                className="w-1 rounded-full bg-primary"
                style={{ height: `${height}px` }}
              />
            ))}
          </span>
        </div>

        <div className="relative">
          <p className="eyebrow">{m.home_eyebrow()}</p>
          <h1 className="mx-auto mt-4 max-w-4xl text-[clamp(2.5rem,7vw,5.25rem)] leading-[0.98] font-bold tracking-[-0.05em]">
            {m.home_headline()}
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            {m.home_intro()}
          </p>

          <div className="mx-auto mt-9 max-w-3xl text-left">
            <SearchForm
              onQuerySubmit={submit}
              autoFocus
              variant="hero"
              hint={m.home_search_hint()}
              showAdvancedSearchLink
            />
          </div>

          <div className="mt-7 flex flex-wrap items-center justify-center gap-2">
            <QuickLink to="/search" icon={Search} label={m.nav_search()} />
            <QuickLink to="/channels" icon={Radio} label={m.nav_channels()} />
            <QuickLink to="/updates" icon={Clock3} label={m.nav_recent()} />
          </div>
        </div>
      </div>

      <LibrarySummary
        songs={summary.data?.songs.total}
        setlists={summary.data?.analysis.with_setlist}
        channels={summary.data?.channels}
        loading={summary.isLoading}
      />

      {recent.data?.songs.length ? (
        <section className="mt-14 sm:mt-16" aria-labelledby="home-recent-heading">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow">{m.recent_updates_eyebrow()}</p>
              <h2 id="home-recent-heading" className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
                {m.recent_songs_heading()}
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                {m.recent_songs_hint()}
              </p>
            </div>
            <Link
              to="/updates"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              {m.nav_recent()}
              <ArrowRight aria-hidden />
            </Link>
          </div>
          <ul className="media-grid">
            {recent.data.songs.slice(0, 4).map((song, index) => (
              <SongResultCard key={song.id} song={song} index={index} showUpdatedAt />
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  )
}

function QuickLink({
  to,
  icon: Icon,
  label,
}: {
  to: "/search" | "/channels" | "/updates"
  icon: typeof Search
  label: string
}) {
  return (
    <Link
      to={to}
      className="inline-flex min-h-10 items-center gap-2 rounded-full bg-secondary px-4 text-sm font-medium text-secondary-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Icon className="size-4 text-primary" aria-hidden />
      {label}
    </Link>
  )
}

function LibrarySummary({
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
    [Radio, setlists, m.home_library_setlists()],
    [Users, channels, m.home_library_channels()],
  ] as const

  return (
    <aside className="animate-rise stagger-3 mx-auto mt-6 w-full max-w-5xl border-b border-border py-6 text-left sm:mt-8 sm:border-y">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">{m.home_library_live()}</p>
          <h2 className="mt-1 text-lg font-bold">{m.home_library_title()}</h2>
        </div>
        <Link
          to="/summary"
          className="inline-flex min-h-10 items-center gap-1.5 rounded-full px-3 text-sm font-semibold text-primary hover:bg-primary/8"
        >
          {m.nav_summary()}
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
      <dl className="mt-5 grid grid-cols-3 divide-x divide-border">
        {metrics.map(([Icon, value, label]) => (
          <div key={label} className="min-w-0 px-3 first:pl-0 sm:px-6 sm:first:pl-0">
            <dt className="flex items-center gap-2 text-xs text-muted-foreground">
              <Icon className="hidden size-4 text-primary sm:block" aria-hidden />
              <span className="truncate">{label}</span>
            </dt>
            <dd className="mt-1.5 text-2xl font-bold tabular-nums sm:text-3xl">
              {loading || value === undefined ? "—" : formatInteger(value)}
            </dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}
