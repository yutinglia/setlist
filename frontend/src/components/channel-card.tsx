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
      <article className="surface flex h-full min-h-40 flex-col p-4 transition-colors hover:border-input hover:bg-card sm:p-5">
        <div className="flex min-w-0 items-center gap-4">
          <Link
            to="/channels/$channelId"
            params={{ channelId: channel.id }}
            className="group shrink-0 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-label={channel.name}
          >
            {channel.thumbnail_url ? (
              <img
                src={channel.thumbnail_url}
                alt=""
                className="size-16 rounded-full object-cover ring-2 ring-border transition-[transform,ring-color] duration-200 group-hover:scale-[1.03] group-hover:ring-primary/40"
                loading="lazy"
              />
            ) : (
              <span className="grid size-16 place-items-center rounded-full bg-primary/10 text-xl font-bold text-primary ring-2 ring-border">
                {channel.name.slice(0, 1)}
              </span>
            )}
          </Link>
          <div className="min-w-0 flex-1">
            <Link
              to="/channels/$channelId"
              params={{ channelId: channel.id }}
              className="line-clamp-2 text-lg leading-snug font-semibold tracking-tight transition-colors hover:text-primary"
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
          </div>
        </div>
        <div className="mt-auto flex items-center justify-between gap-3 pt-5">
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
            className="inline-flex min-h-9 items-center gap-1 rounded-full px-2 text-sm font-semibold text-primary hover:bg-primary/8"
          >
            {m.view_channel()}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </article>
    </li>
  )
}
