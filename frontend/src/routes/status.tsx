import { Link, createFileRoute } from "@tanstack/react-router"
import type { ReactNode } from "react"

import { useUpdaterStatus } from "@/api/hooks"
import type { UpdaterPhase } from "@/api/types"
import { QueryState } from "@/components/query-state"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/status")({
  component: StatusPage,
})

const ACTIVE_PHASES = new Set<string>([
  "starting",
  "fetching_channels",
  "refreshing_channel",
  "scraping_videos",
  "backfilling_videos",
  "reclassifying",
  "scraping_comments",
  "analyzing",
  "llm_cleaning",
  "jitter",
  "committing",
])

function phaseLabel(phase: string): string {
  switch (phase as UpdaterPhase) {
    case "idle":
      return m.status_phase_idle()
    case "waiting":
      return m.status_phase_waiting()
    case "cooldown":
      return m.status_phase_cooldown()
    case "starting":
      return m.status_phase_starting()
    case "fetching_channels":
      return m.status_phase_fetching_channels()
    case "refreshing_channel":
      return m.status_phase_refreshing_channel()
    case "scraping_videos":
      return m.status_phase_scraping_videos()
    case "backfilling_videos":
      return m.status_phase_backfilling_videos()
    case "reclassifying":
      return m.status_phase_reclassifying()
    case "scraping_comments":
      return m.status_phase_scraping_comments()
    case "analyzing":
      return m.status_phase_analyzing()
    case "llm_cleaning":
      return m.status_phase_llm_cleaning()
    case "jitter":
      return m.status_phase_jitter()
    case "committing":
      return m.status_phase_committing()
    case "error":
      return m.status_phase_error()
    default:
      return phase
  }
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

function formatSeconds(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  if (m < 60) return rem ? `${m}m ${rem}s` : `${m}m`
  const h = Math.floor(m / 60)
  const mins = m % 60
  return mins ? `${h}h ${mins}m` : `${h}h`
}

function StatusPage() {
  const query = useUpdaterStatus()
  const data = query.data
  const phase = data?.phase ?? "idle"
  const isBusy = Boolean(data?.is_cycle_active) || ACTIVE_PHASES.has(phase)
  const isCooldown = phase === "cooldown" || (data?.youtube_cooldown_remaining_seconds ?? 0) > 0
  const isError = phase === "error"

  return (
    <section className="animate-fade pt-10">
      <h1 className="font-display text-3xl font-bold tracking-tight">
        {m.status_heading()}
      </h1>
      <p className="mt-2 max-w-prose text-sm text-muted-foreground">
        {m.status_hint()}
      </p>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={false}
          emptyMessage=""
          onRetry={() => void query.refetch()}
        >
          {data ? (
            <div className="space-y-8">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "size-2.5 shrink-0 rounded-full",
                      isError
                        ? "bg-destructive"
                        : isCooldown
                          ? "bg-amber-500"
                          : isBusy
                            ? "animate-soft-pulse bg-primary"
                            : "bg-muted-foreground/40",
                    )}
                    aria-hidden
                  />
                  <div>
                    <p className="font-display text-xl font-semibold tracking-tight">
                      {phaseLabel(phase)}
                    </p>
                    {data.detail ? (
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {data.detail}
                      </p>
                    ) : null}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  {m.status_updated_at({ when: formatWhen(data.updated_at) })}
                </p>
              </div>

              <dl className="grid gap-4 sm:grid-cols-2">
                <StatusField
                  label={m.status_channel()}
                  value={
                    data.channel_name || data.channel_id
                      ? data.channel_id
                        ? (
                            <Link
                              to="/channels/$channelId"
                              params={{ channelId: data.channel_id }}
                              className="text-primary underline-offset-2 hover:underline"
                            >
                              {data.channel_name || data.channel_id}
                            </Link>
                          )
                        : data.channel_name
                      : "—"
                  }
                />
                <StatusField
                  label={m.status_video()}
                  value={
                    data.video_id
                      ? (
                          <Link
                            to="/videos/$videoId"
                            params={{ videoId: data.video_id }}
                            className="text-primary underline-offset-2 hover:underline"
                          >
                            {data.video_title || data.video_id}
                          </Link>
                        )
                      : "—"
                  }
                />
                <StatusField
                  label={m.status_comment_scrapes()}
                  value={`${data.comment_scrapes_this_cycle} / ${data.comment_scrape_cap}`}
                />
                <StatusField
                  label={m.status_cycle_interval()}
                  value={formatSeconds(data.update_interval_seconds)}
                />
                <StatusField
                  label={m.status_cooldown()}
                  value={
                    data.youtube_cooldown_remaining_seconds > 0
                      ? formatSeconds(data.youtube_cooldown_remaining_seconds)
                      : m.status_cooldown_clear()
                  }
                />
                <StatusField
                  label={m.status_cycle_active()}
                  value={
                    data.is_cycle_active
                      ? m.status_cycle_yes()
                      : m.status_cycle_no()
                  }
                />
                <StatusField
                  label={m.status_cycle_started()}
                  value={formatWhen(data.cycle_started_at)}
                />
                <StatusField
                  label={m.status_cycle_finished()}
                  value={formatWhen(data.last_cycle_finished_at)}
                />
              </dl>

              {data.last_error ? (
                <div
                  role="alert"
                  className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
                >
                  <p className="font-medium">{m.status_last_error()}</p>
                  <p className="mt-1 break-words opacity-90">{data.last_error}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}

function StatusField({
  label,
  value,
}: {
  label: string
  value: ReactNode
}) {
  return (
    <div className="border-b border-border/60 pb-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 truncate text-sm text-foreground">{value}</dd>
    </div>
  )
}
