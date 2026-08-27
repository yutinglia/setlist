import { useMemo, useState, type FormEvent } from "react"
import { Link, createFileRoute } from "@tanstack/react-router"
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ListPlus,
  Radio,
  ShieldCheck,
} from "lucide-react"

import { ApiError } from "@/api/client"
import { useCreateChannelsBulk } from "@/api/hooks"
import type {
  ChannelBulkAddItem,
  ChannelBulkAddResponse,
  ChannelBulkAddStatus,
} from "@/api/types"
import { ChannelIngestQueuePanel } from "@/components/channel-ingest-queue"
import { ContextualBackButton } from "@/components/contextual-back-button"
import { PageMetadata } from "@/components/page-metadata"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { requireManagementRoute } from "@/lib/auth-guard"
import { m } from "@/paraglide/messages"

const MAX_BULK_CHANNELS = 10

export const Route = createFileRoute("/channels/new")({
  beforeLoad: requireManagementRoute,
  component: AddChannelPage,
})

function AddChannelPage() {
  const navigate = Route.useNavigate()
  const createChannels = useCreateChannelsBulk()
  const [value, setValue] = useState("")
  const [error, setError] = useState("")
  const [result, setResult] = useState<ChannelBulkAddResponse | null>(null)
  const urls = useMemo(
    () =>
      value
        .split(/\r?\n/)
        .map((url) => url.trim())
        .filter(Boolean),
    [value],
  )

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (urls.length === 0) {
      setError(m.channel_add_url_required())
      return
    }
    if (urls.length > MAX_BULK_CHANNELS) {
      setError(
        m.channel_add_too_many({
          count: urls.length,
          max: MAX_BULK_CHANNELS,
        }),
      )
      return
    }

    setError("")
    setResult(null)
    try {
      setResult(await createChannels.mutateAsync(urls))
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError(m.channel_add_failed())
      }
    }
  }

  const isSubmitting = createChannels.isPending
  const isTooMany = urls.length > MAX_BULK_CHANNELS

  return (
    <section className="animate-fade mx-auto w-full max-w-5xl py-7 sm:py-10 lg:py-12">
      <PageMetadata
        path="/channels/new"
        title={`${m.channel_add_heading()} | Setlist`}
        description={m.channel_add_hint()}
        noIndex
      />
      <ContextualBackButton
        label={m.back()}
        onFallback={() =>
          navigate({ to: "/channels", replace: true })
        }
      />

      <header className="page-header mt-7 max-w-4xl">
        <p className="eyebrow">{m.channel_library_eyebrow()}</p>
        <h1 className="page-title mt-1">{m.channel_add_heading()}</h1>
        <p className="page-intro">{m.channel_add_hint()}</p>
      </header>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <TipCard
          icon={ShieldCheck}
          title={m.channel_add_pacing_title()}
          body={m.channel_add_pacing_body()}
        />
        <TipCard
          icon={Clock3}
          title={m.channel_add_backfill_title()}
          body={m.channel_add_backfill_body()}
        />
      </div>

      <div className="surface mt-6 overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border/60 bg-secondary/35 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-full bg-primary/10 text-primary">
              <Radio className="size-4" aria-hidden />
            </span>
            <p className="text-sm font-semibold">{m.channel_add_url_label()}</p>
          </div>
          <span
            className={
              isTooMany
                ? "font-mono text-xs font-semibold text-destructive"
                : "font-mono text-xs text-muted-foreground"
            }
          >
            {m.channel_add_count({
              count: urls.length,
              max: MAX_BULK_CHANNELS,
            })}
          </span>
        </div>

        <form className="p-5 sm:p-7" onSubmit={(e) => void handleSubmit(e)}>
          <label className="sr-only" htmlFor="channel-urls">
            {m.channel_add_url_label()}
          </label>
          <textarea
            id="channel-urls"
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              if (error) setError("")
            }}
            placeholder={m.channel_add_url_placeholder()}
            maxLength={5_010}
            rows={8}
            className="min-h-48 w-full resize-y rounded-xl border border-input bg-card px-4 py-3 font-mono text-base leading-7 shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/35 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
            autoFocus
            disabled={isSubmitting}
            aria-invalid={error || isTooMany ? true : undefined}
            aria-describedby={
              error ? "channel-add-error" : "channel-add-help"
            }
          />
          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p
              id="channel-add-help"
              className="text-xs leading-relaxed text-muted-foreground"
            >
              {m.channel_add_help()}
            </p>
            <Button
              type="submit"
              className="shrink-0 px-5"
              size="lg"
              disabled={
                isSubmitting || urls.length === 0 || urls.length > MAX_BULK_CHANNELS
              }
              aria-busy={isSubmitting}
            >
              <ListPlus aria-hidden />
              {isSubmitting
                ? m.channel_add_loading()
                : m.channel_add_submit()}
            </Button>
          </div>
          {error ? (
            <p
              id="channel-add-error"
              className="mt-4 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </form>
      </div>

      {result ? <BulkResult result={result} /> : null}
      <ChannelIngestQueuePanel />
    </section>
  )
}

function TipCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof ShieldCheck
  title: string
  body: string
}) {
  return (
    <div className="surface-subtle p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
          <Icon className="size-4" aria-hidden />
        </span>
        <div>
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {body}
          </p>
        </div>
      </div>
    </div>
  )
}

function BulkResult({ result }: { result: ChannelBulkAddResponse }) {
  return (
    <div className="surface mt-6 overflow-hidden" aria-live="polite">
      <div className="flex items-start gap-3 border-b border-border/60 bg-secondary/35 px-5 py-4">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
          {result.failed || result.skipped ? (
            <AlertTriangle className="size-4" aria-hidden />
          ) : result.queued ? (
            <Clock3 className="size-4" aria-hidden />
          ) : (
            <CheckCircle2 className="size-4" aria-hidden />
          )}
        </span>
        <div>
          <p className="text-sm font-semibold">
            {m.channel_add_result_title()}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {m.channel_add_result_summary({
              created: result.created,
              existing: result.already_exists,
              queued: result.queued,
              failed: result.failed,
              skipped: result.skipped,
            })}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {result.queued
              ? m.channel_add_result_queued({ queued: result.queued })
              : m.channel_add_result_pacing({
                  seconds: result.cooldown_seconds,
                })}
          </p>
        </div>
      </div>

      <ul className="divide-y divide-border/60">
        {result.items.map((item, index) => (
          <li
            key={`${item.url}-${index}`}
            className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              {item.channel_id ? (
                <Link
                  to="/channels/$channelId"
                  params={{ channelId: item.channel_id }}
                  className="inline-flex min-h-11 max-w-full items-center truncate text-sm font-semibold text-primary underline-offset-2 hover:underline"
                >
                  {item.channel_name || item.channel_id}
                </Link>
              ) : (
                <p className="truncate text-sm font-semibold">
                  {item.channel_name ||
                    (item.status === "queued"
                      ? m.channel_add_queued_channel()
                      : m.channel_add_unknown_channel())}
                </p>
              )}
              <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
                {item.url}
              </p>
            </div>
            <Badge
              variant={badgeVariant(item.status)}
              className="w-fit shrink-0"
            >
              {statusLabel(item)}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}

function badgeVariant(status: ChannelBulkAddStatus) {
  if (status === "created") return "success" as const
  if (status === "already_exists") return "muted" as const
  return "default" as const
}

function statusLabel(item: ChannelBulkAddItem): string {
  switch (item.status) {
    case "created":
      return m.channel_add_status_created()
    case "already_exists":
      return m.channel_add_status_existing()
    case "queued":
      return m.channel_add_status_queued()
    case "invalid":
      return m.channel_add_status_invalid()
    case "skipped":
      return m.channel_add_status_skipped()
    default:
      return m.channel_add_status_failed()
  }
}
