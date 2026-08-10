import { Link } from "@tanstack/react-router"
import { ArrowRight, Clock3, ExternalLink, Radio } from "lucide-react"

import type { YouTubeChannel } from "@/api/types"
import { formatApiDateTime } from "@/lib/locale-format"
import { m } from "@/paraglide/messages"

type Props = {
  channel: YouTubeChannel
  index?: number
  showUpdatedAt?: boolean
}

export function ChannelCard({
  channel,
  index = 0,
  showUpdatedAt = false,
}: Props) {
  return (
    <li
      className={`media-card animate-rise stagger-${Math.min((index % 4) + 1, 4)}`}
    >
      <article className="surface flex h-full flex-col overflow-hidden">
        <Link
          to="/channels/$channelId"
          params={{ channelId: channel.id }}
          className="group relative flex aspect-video items-center justify-center overflow-hidden bg-gradient-to-br from-primary/15 via-secondary to-accent/15"
          aria-label={channel.name}
        >
          {channel.thumbnail_url ? (
            <img
              src={channel.thumbnail_url}
              alt=""
              className="size-24 rounded-full object-cover ring-4 ring-card shadow-xl transition-transform duration-300 group-hover:scale-105"
              loading="lazy"
            />
          ) : (
            <span className="grid size-24 place-items-center rounded-full bg-primary font-display text-3xl font-bold text-primary-foreground ring-4 ring-card shadow-xl">
              {channel.name.slice(0, 1)}
            </span>
          )}
        </Link>

        <div className="flex min-w-0 flex-1 flex-col p-4">
          <Link
            to="/channels/$channelId"
            params={{ channelId: channel.id }}
            className="line-clamp-2 font-display text-lg leading-snug font-bold tracking-tight transition-colors hover:text-primary"
          >
            {channel.name}
          </Link>
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Radio className="size-3.5 text-primary" aria-hidden />
            {m.channel_content_label()}
          </p>
          {showUpdatedAt && channel.updated_at ? (
            <time
              dateTime={channel.updated_at}
              className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <Clock3 className="size-3.5 text-primary" aria-hidden />
              {m.recent_updated_at({
                when: formatApiDateTime(channel.updated_at),
              })}
            </time>
          ) : null}
          <div className="mt-auto flex items-center justify-between gap-3 pt-4">
            <a
              href={channel.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              YouTube
              <ExternalLink className="size-3" aria-hidden />
            </a>
            <Link
              to="/channels/$channelId"
              params={{ channelId: channel.id }}
              className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
            >
              {m.view_channel()}
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </div>
      </article>
    </li>
  )
}
