import { useState, type FormEvent } from "react"
import {
  Link,
  createFileRoute,
  useNavigate,
} from "@tanstack/react-router"
import { ArrowLeft, Link2, Plus, Radio } from "lucide-react"

import { ApiError } from "@/api/client"
import { useCreateChannel } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageMetadata } from "@/components/page-metadata"
import { requireManagementRoute } from "@/lib/auth-guard"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/new")({
  beforeLoad: requireManagementRoute,
  component: AddChannelPage,
})

function AddChannelPage() {
  const navigate = useNavigate()
  const createChannel = useCreateChannel()
  const [url, setUrl] = useState("")
  const [error, setError] = useState("")

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) {
      setError(m.channel_add_url_required())
      return
    }
    setError("")
    try {
      const channel = await createChannel.mutateAsync(trimmed)
      void navigate({
        to: "/channels/$channelId",
        params: { channelId: channel.id },
      })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError(m.channel_add_failed())
      }
    }
  }

  const isSubmitting = createChannel.isPending

  return (
    <section className="animate-fade mx-auto w-full max-w-3xl py-10 sm:py-14">
      <PageMetadata
        path="/channels/new"
        title={`${m.channel_add_heading()} | Setlist`}
        description={m.channel_add_hint()}
        noIndex
      />
      <Link
        to="/channels"
        className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        {m.nav_channels()}
      </Link>

      <p className="eyebrow mt-8">{m.channel_library_eyebrow()}</p>
      <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
        {m.channel_add_heading()}
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
        {m.channel_add_hint()}
      </p>

      <div className="surface mt-8 overflow-hidden">
        <div className="flex items-center gap-3 border-b border-border/60 bg-secondary/35 px-5 py-4">
          <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary">
            <Radio className="size-4" aria-hidden />
          </span>
          <p className="text-sm font-semibold">{m.channel_add_url_label()}</p>
        </div>

        <form className="p-5 sm:p-7" onSubmit={(e) => void handleSubmit(e)}>
          <label className="sr-only" htmlFor="channel-url">
            {m.channel_add_url_label()}
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative min-w-0 flex-1">
              <Link2
                className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                id="channel-url"
                type="url"
                inputMode="url"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value)
                  if (error) setError("")
                }}
                placeholder={m.channel_add_url_placeholder()}
                maxLength={500}
                className="h-12 bg-card pl-11 text-base"
                autoFocus
                disabled={isSubmitting}
                aria-invalid={error ? true : undefined}
                aria-describedby={
                  error ? "channel-add-error" : "channel-add-help"
                }
              />
            </div>
            <Button
              type="submit"
              className="h-12 shrink-0 px-5"
              size="lg"
              disabled={isSubmitting || !url.trim()}
              aria-busy={isSubmitting}
            >
              <Plus aria-hidden />
              {isSubmitting ? m.channel_add_loading() : m.channel_add_submit()}
            </Button>
          </div>
          <p
            id="channel-add-help"
            className="mt-3 text-xs text-muted-foreground"
          >
            {m.channel_add_help()}
          </p>
          {error ? (
            <p
              id="channel-add-error"
              className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </form>
      </div>
    </section>
  )
}
