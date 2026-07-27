import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowRight,
  Disc3,
  ListMusic,
  Sparkles,
  Users,
} from "lucide-react"

import { useSummaryReport } from "@/api/hooks"
import { PageMetadata } from "@/components/page-metadata"
import { SearchForm } from "@/components/search-form"
import { formatInteger } from "@/lib/locale-format"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  const navigate = Route.useNavigate()
  const summary = useSummaryReport()

  function submit(query: string) {
    const q = query.trim()
    if (!q) return
    void navigate({
      to: "/search",
      search: { q },
    })
  }

  return (
    <section className="grid min-h-[min(820px,82svh)] flex-1 place-items-center py-14 sm:py-20">
      <PageMetadata
        path="/"
        title={m.meta_default_title()}
        description={m.home_intro()}
      />
      <div className="animate-rise w-full max-w-4xl text-center">
        <h1 className="font-display text-[clamp(2.5rem,7vw,5.6rem)] leading-[0.96] font-bold tracking-[-0.05em]">
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

        <LibrarySummary
          songs={summary.data?.songs.total}
          setlists={summary.data?.analysis.with_setlist}
          channels={summary.data?.channels}
          loading={summary.isLoading}
        />
      </div>
    </section>
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
    [Disc3, setlists, m.home_library_setlists()],
    [Users, channels, m.home_library_channels()],
  ] as const

  return (
    <aside className="surface animate-rise stagger-3 relative mx-auto mt-7 max-w-3xl overflow-hidden p-4 text-left sm:p-5">
      <div className="absolute -top-20 -right-16 size-44 rounded-full bg-primary/10 blur-3xl" />
      <div className="relative">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
              <Sparkles className="size-4" aria-hidden />
            </span>
            <div>
              <p className="eyebrow">{m.home_library_live()}</p>
              <h2 className="mt-1 font-display text-lg font-bold">
                {m.home_library_title()}
              </h2>
            </div>
          </div>
          <Link
            to="/summary"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
          >
            {m.nav_summary()}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>

        <dl className="mt-4 grid gap-2 sm:grid-cols-3">
          {metrics.map(([Icon, value, label]) => (
            <div
              key={label}
              className="rounded-xl border border-border/60 bg-secondary/45 px-4 py-3"
            >
              <dt className="flex items-center gap-2 text-xs text-muted-foreground">
                <Icon className="size-3.5 text-primary" aria-hidden />
                {label}
              </dt>
              <dd className="mt-1.5 font-display text-2xl font-bold tabular-nums">
                {loading || value === undefined ? "—" : formatInteger(value)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </aside>
  )
}
