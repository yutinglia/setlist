import { useState, type FormEvent } from "react"
import {
  Link,
  createFileRoute,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { ArrowLeft, Plus } from "lucide-react"

import { ApiError } from "@/api/client"
import { useCreateChannel } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { MANAGEMENT_UI_ENABLED } from "@/lib/app-config"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/new")({
  beforeLoad: () => {
    if (!MANAGEMENT_UI_ENABLED) {
      throw redirect({ to: "/channels" })
    }
  },
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
    <section className="animate-fade pt-10">
      <Link
        to="/channels"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        {m.nav_channels()}
      </Link>

      <h1 className="mt-6 font-display text-3xl font-bold tracking-tight">
        {m.channel_add_heading()}
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">{m.channel_add_hint()}</p>

      <form className="mt-8" onSubmit={(e) => void handleSubmit(e)}>
        <label className="block text-sm font-medium" htmlFor="channel-url">
          {m.channel_add_url_label()}
        </label>
        <div className="mt-2 flex gap-2">
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
            className="h-12 border-border/80 bg-card/80 text-base shadow-none backdrop-blur-sm"
            autoFocus
            disabled={isSubmitting}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "channel-add-error" : "channel-add-help"}
          />
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
        <p id="channel-add-help" className="mt-2 text-xs text-muted-foreground">
          {m.channel_add_help()}
        </p>
        {error ? (
          <p
            id="channel-add-error"
            className="mt-3 text-sm text-destructive"
            role="alert"
          >
            {error}
          </p>
        ) : null}
      </form>
    </section>
  )
}
