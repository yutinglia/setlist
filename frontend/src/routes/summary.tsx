import { createFileRoute } from "@tanstack/react-router"
import type { ReactNode } from "react"
import {
  Archive,
  BarChart3,
  Clock3,
  HeartHandshake,
  ListMusic,
  MessageSquareText,
  Radio,
  Sparkles,
  Tv,
  Users,
  Video,
  type LucideIcon,
} from "lucide-react"

import { useSummaryReport } from "@/api/hooks"
import { PageMetadata } from "@/components/page-metadata"
import { QueryState } from "@/components/query-state"
import { formatDateTime, formatInteger } from "@/lib/locale-format"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/summary")({
  component: SummaryPage,
})

function formatWhen(iso: string | null): string {
  if (!iso) return m.summary_never()
  const date = new Date(
    iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`,
  )
  return Number.isNaN(date.getTime()) ? iso : formatDateTime(date)
}

function percentage(value: number, total: number): number {
  if (total <= 0) return 0
  return Math.min(100, Math.round((value / total) * 100))
}

function SummaryPage() {
  const query = useSummaryReport()
  const data = query.data

  return (
    <section className="animate-fade py-10 sm:py-14">
      <PageMetadata
        path="/summary"
        title={`${m.summary_heading()} | Setlist`}
        description={m.summary_hint()}
      />
      <header className="flex flex-wrap items-end justify-between gap-5 border-b border-border/70 pb-8">
        <div>
          <p className="eyebrow">{m.home_library_live()}</p>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
            {m.summary_heading()}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            {m.summary_hint()}
          </p>
        </div>
        {data ? (
          <p className="text-xs text-muted-foreground">
            {m.summary_updated_at({ when: formatWhen(data.generated_at) })}
          </p>
        ) : null}
      </header>

      <div className="mt-7">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={false}
          emptyMessage=""
          onRetry={() => void query.refetch()}
        >
          {data ? (
            <div className="space-y-8">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                <MetricCard
                  icon={BarChart3}
                  label={m.summary_scraped_records()}
                  value={data.videos.total}
                  accent
                />
                <MetricCard
                  icon={Radio}
                  label={m.summary_karaoke()}
                  value={data.videos.karaoke}
                />
                <MetricCard
                  icon={Video}
                  label={m.summary_song_videos()}
                  value={data.videos.song}
                />
                <MetricCard
                  icon={Archive}
                  label={m.summary_other_videos()}
                  value={data.videos.other}
                />
                <MetricCard
                  icon={Users}
                  label={m.summary_channels()}
                  value={data.channels}
                />
                <MetricCard
                  icon={Tv}
                  label={m.summary_analysis_attempted()}
                  value={data.analysis.attempted}
                />
                <MetricCard
                  icon={MessageSquareText}
                  label={m.summary_comments()}
                  value={data.analysis.comments}
                />
                <MetricCard
                  icon={ListMusic}
                  label={m.summary_setlists()}
                  value={data.analysis.with_setlist}
                />
                <MetricCard
                  icon={Sparkles}
                  label={m.summary_songs()}
                  value={data.songs.total}
                  accent
                />
                <MetricCard
                  icon={HeartHandshake}
                  label={m.summary_contributors()}
                  value={data.songs.contributors}
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <ReportSection
                  title={m.summary_pipeline()}
                  hint={m.summary_pipeline_hint()}
                >
                  <div className="space-y-5">
                    <ProgressRow
                      label={m.summary_analysis_coverage()}
                      value={data.analysis.attempted}
                      total={data.videos.karaoke}
                    />
                    <ProgressRow
                      label={m.summary_setlist_coverage()}
                      value={data.analysis.with_setlist}
                      total={data.videos.karaoke}
                    />
                    <div className="border-t border-border/60 pt-4">
                      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        {m.summary_analysis_status()}
                      </p>
                      <CountRows
                        rows={[
                          [
                            m.summary_status_pending(),
                            data.analysis.status.pending,
                          ],
                          [m.summary_status_retry(), data.analysis.status.retry],
                          [
                            m.summary_status_no_setlist(),
                            data.analysis.status.no_setlist,
                          ],
                          [m.summary_status_done(), data.analysis.status.done],
                          [
                            m.summary_status_exhausted(),
                            data.analysis.status.exhausted,
                          ],
                          [
                            m.summary_status_skipped(),
                            data.analysis.status.skipped,
                          ],
                        ]}
                      />
                    </div>
                  </div>
                </ReportSection>

                <ReportSection
                  title={m.summary_backfill()}
                  hint={m.summary_backfill_hint()}
                >
                  <CountRows
                    rows={[
                      [m.summary_backfill_pending(), data.backfill.pending],
                      [m.summary_backfill_running(), data.backfill.running],
                      [m.summary_backfill_done(), data.backfill.done],
                      [m.summary_backfill_failed(), data.backfill.failed],
                    ]}
                    warnLast={data.backfill.failed > 0}
                  />
                  <dl className="mt-5 space-y-3 border-t border-border/60 pt-4">
                    <DetailRow
                      label={m.summary_comment_snapshots()}
                      value={formatInteger(data.analysis.videos_with_comments)}
                    />
                    <DetailRow
                      label={m.summary_list_snapshots()}
                      value={formatInteger(data.videos.with_list_snapshot)}
                    />
                    <DetailRow
                      label={m.summary_metadata_snapshots()}
                      value={formatInteger(data.videos.with_metadata_snapshot)}
                    />
                    <DetailRow
                      label={m.summary_date_exact()}
                      value={formatInteger(data.videos.date_exact)}
                    />
                    <DetailRow
                      label={m.summary_date_approximate()}
                      value={formatInteger(data.videos.date_approximate)}
                    />
                    <DetailRow
                      label={m.summary_date_unknown()}
                      value={formatInteger(data.videos.date_unknown)}
                      warning={data.videos.date_unknown > 0}
                    />
                    <DetailRow
                      label={m.summary_llm_songs()}
                      value={formatInteger(data.songs.analyzed_by_llm)}
                    />
                  </dl>
                </ReportSection>
              </div>

              <ReportSection title={m.summary_freshness()} icon={Clock3}>
                <dl className="grid gap-4 sm:grid-cols-2">
                  <DetailRow
                    label={m.summary_latest_discovered()}
                    value={formatWhen(data.videos.latest_discovered_at)}
                  />
                  <DetailRow
                    label={m.summary_latest_analyzed()}
                    value={formatWhen(data.analysis.latest_analyzed_at)}
                  />
                </dl>
              </ReportSection>
            </div>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  accent = false,
}: {
  icon: LucideIcon
  label: string
  value: number
  accent?: boolean
}) {
  return (
    <div
      className={cn(
        "surface p-4 transition-transform hover:-translate-y-0.5 sm:p-5",
        accent
          ? "border-primary/25 bg-primary/7"
          : "border-border/70 bg-card/80",
      )}
    >
      <Icon
        className={cn(
          "size-4",
          accent ? "text-primary" : "text-muted-foreground",
        )}
        aria-hidden
      />
      <p className="mt-5 font-display text-3xl font-bold tabular-nums">
        {formatInteger(value)}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

function ReportSection({
  title,
  hint,
  icon: Icon,
  children,
}: {
  title: string
  hint?: string
  icon?: LucideIcon
  children: ReactNode
}) {
  return (
    <section className="surface p-5 sm:p-6">
      <div className="flex items-center gap-2">
        {Icon ? <Icon className="size-4 text-primary" aria-hidden /> : null}
        <h2 className="font-display text-xl font-bold">{title}</h2>
      </div>
      {hint ? (
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      ) : null}
      <div className="mt-5">{children}</div>
    </section>
  )
}

function ProgressRow({
  label,
  value,
  total,
}: {
  label: string
  value: number
  total: number
}) {
  const percent = percentage(value, total)
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span>{label}</span>
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {formatInteger(value)} / {formatInteger(total)} · {percent}%
        </span>
      </div>
      <div
        className="mt-2 h-2 overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={Math.max(total, 1)}
        aria-valuenow={Math.min(value, total)}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}

function CountRows({
  rows,
  warnLast = false,
}: {
  rows: Array<[string, number]>
  warnLast?: boolean
}) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
      {rows.map(([label, value], index) => (
        <DetailRow
          key={label}
          label={label}
          value={formatInteger(value)}
          warning={warnLast && index === rows.length - 1}
        />
      ))}
    </dl>
  )
}

function DetailRow({
  label,
  value,
  warning = false,
}: {
  label: string
  value: string
  warning?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/50 pb-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "font-mono text-sm font-medium tabular-nums",
          warning && "text-destructive",
        )}
      >
        {value}
      </dd>
    </div>
  )
}
