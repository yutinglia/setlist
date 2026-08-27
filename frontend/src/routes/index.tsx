import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowRight,
  Clock3,
  ListMusic,
  Radio,
  Search,
  Users,
} from "lucide-react"
import type { ReactNode } from "react"

import { useRecentUpdates, useSummaryReport } from "@/api/hooks"
import { ChannelCard } from "@/components/channel-card"
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

  const channels = recent.data?.channels.slice(0, 3) ?? []
  const songs = recent.data?.songs.slice(0, 4) ?? []

  return (
    <section className="flex flex-1 flex-col py-6 sm:py-10 lg:py-12">
      <PageMetadata
        path="/"
        title={m.meta_default_title()}
        description={m.home_intro()}
      />

      <div className="animate-rise relative isolate overflow-hidden rounded-[2rem] border border-border/80 bg-card px-5 py-8 shadow-[0_35px_90px_-65px_rgba(9,20,45,0.9)] sm:px-8 sm:py-10 lg:px-12 lg:py-14">
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
          <span className="absolute -top-48 -left-32 size-96 rounded-full bg-primary/12 blur-3xl" />
          <span className="absolute -right-40 -bottom-64 size-[30rem] rounded-full bg-accent-foreground/8 blur-3xl" />
          <span className="absolute top-0 right-[12%] h-full w-px bg-gradient-to-b from-transparent via-border/70 to-transparent" />
        </div>

        <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(19rem,0.8fr)] lg:gap-14">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <Equalizer />
              <p className="eyebrow">{m.home_eyebrow()}</p>
            </div>
            <h1 className="mt-5 max-w-4xl text-[clamp(3rem,7vw,6.4rem)] leading-[0.92] font-bold tracking-[-0.065em]">
              {m.home_headline()}
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
              {m.home_intro()}
            </p>

            <div className="mt-8 max-w-3xl">
              <SearchForm
                onQuerySubmit={submit}
                autoFocus
                variant="hero"
                hint={m.home_search_hint()}
                showAdvancedSearchLink
              />
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <QuickLink to="/search" icon={Search} label={m.nav_search()} />
              <QuickLink to="/channels" icon={Radio} label={m.nav_channels()} />
              <QuickLink to="/updates" icon={Clock3} label={m.nav_recent()} />
            </div>
          </div>

          <LibrarySnapshot
            songs={summary.data?.songs.total}
            setlists={summary.data?.analysis.with_setlist}
            channels={summary.data?.channels}
            loading={summary.isLoading}
          />
        </div>
      </div>

      {channels.length > 0 ? (
        <section className="mt-14 sm:mt-18" aria-labelledby="home-channels-heading">
          <SectionHeader
            eyebrow={m.recent_updates_eyebrow()}
            title={m.home_explore_title()}
            hint={m.home_explore_hint()}
            headingId="home-channels-heading"
            action={
              <Link
                to="/channels"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                {m.home_browse_all()}
                <ArrowRight aria-hidden />
              </Link>
            }
          />
          <ul className="media-grid mt-6">
            {channels.map((channel, index) => (
              <ChannelCard
                key={channel.id}
                channel={channel}
                index={index}
                showUpdatedAt
              />
            ))}
          </ul>
        </section>
      ) : null}

      {songs.length > 0 ? (
        <section className="mt-14 sm:mt-18" aria-labelledby="home-recent-heading">
          <SectionHeader
            eyebrow={m.recent_updates_eyebrow()}
            title={m.recent_songs_heading()}
            hint={m.recent_songs_hint()}
            headingId="home-recent-heading"
            action={
              <Link
                to="/updates"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                {m.nav_recent()}
                <ArrowRight aria-hidden />
              </Link>
            }
          />
          <ul className="media-grid mt-6">
            {songs.map((song, index) => (
              <SongResultCard key={song.id} song={song} index={index} showUpdatedAt />
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  )
}

function Equalizer() {
  return (
    <span
      className="flex h-6 items-end gap-1 rounded-lg bg-primary/10 px-2 py-1 text-primary"
      aria-hidden
    >
      {[45, 80, 60, 100, 52].map((height, index) => (
        <span
          key={height}
          className="equalizer-bar w-0.5 rounded-full bg-current"
          style={{ height: `${height}%`, animationDelay: `${index * -0.13}s` }}
        />
      ))}
    </span>
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
      className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-secondary px-3.5 text-sm font-semibold text-secondary-foreground outline-none transition-colors duration-200 hover:bg-muted hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Icon className="size-4 text-primary" aria-hidden />
      {label}
    </Link>
  )
}

function LibrarySnapshot({
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
    <aside className="surface-subtle relative overflow-hidden p-5 sm:p-6 lg:p-7">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary via-brand to-accent-foreground" aria-hidden />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{m.home_library_live()}</p>
          <h2 className="mt-2 text-2xl font-bold tracking-[-0.03em]">
            {m.home_library_title()}
          </h2>
        </div>
        <span className="mt-1 flex items-center gap-2 rounded-full bg-success/10 px-3 py-1 text-xs font-bold text-success">
          <span className="size-2 rounded-full bg-success" aria-hidden />
          {m.home_library_live()}
        </span>
      </div>

      <dl className="mt-7 grid gap-3">
        {metrics.map(([Icon, value, label]) => (
          <div
            key={label}
            className="flex min-h-20 items-center gap-4 rounded-xl border border-border/70 bg-card/80 px-4 py-3"
          >
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Icon className="size-4.5" aria-hidden />
            </span>
            <div className="min-w-0">
              <dd className="text-2xl font-bold tabular-nums">
                {loading || value === undefined ? "—" : formatInteger(value)}
              </dd>
              <dt className="truncate text-xs font-medium text-muted-foreground">
                {label}
              </dt>
            </div>
          </div>
        ))}
      </dl>

      <Link
        to="/summary"
        className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-semibold text-foreground outline-none transition-colors duration-200 hover:bg-secondary hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
      >
        {m.nav_summary()}
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </aside>
  )
}

function SectionHeader({
  eyebrow,
  title,
  hint,
  headingId,
  action,
}: {
  eyebrow: string
  title: string
  hint: string
  headingId: string
  action: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/75 pb-5">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={headingId} className="section-heading mt-2">
          {title}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          {hint}
        </p>
      </div>
      {action}
    </div>
  )
}
