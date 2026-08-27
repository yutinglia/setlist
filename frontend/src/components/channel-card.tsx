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
      <article className="flex h-full min-h-48 flex-col p-5 sm:p-6">
        <div className="flex min-w-0 items-start gap-4">
          <Link
            to="/channels/$channelId"
            params={{ channelId: channel.id }}
            className="group shrink-0 rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            aria-label={channel.name}
          >
            {channel.thumbnail_url ? (
              <img
                src={channel.thumbnail_url}
                alt=""
                width={72}
                height={72}
                className="size-18 rounded-2xl object-cover ring-1 ring-border transition-[transform,ring-color] duration-200 group-hover:scale-[1.025] group-hover:ring-primary/55"
                loading="lazy"
              />
            ) : (
              <span className="grid size-18 place-items-center rounded-2xl bg-primary/10 text-2xl font-bold text-primary ring-1 ring-border">
                {channel.name.slice(0, 1)}
              </span>
            )}
          </Link>
          <div className="min-w-0 flex-1">
            <Link
              to="/channels/$channelId"
              params={{ channelId: channel.id }}
              className="-m-1 min-h-11 line-clamp-2 rounded-lg p-1 text-xl leading-snug font-bold tracking-[-0.025em] transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {channel.name}
            </Link>
            <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
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
        <div className="mt-auto grid grid-cols-2 gap-2 pt-6">
          <a
            href={channel.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl bg-secondary px-3 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            YouTube
            <ExternalLink className="size-3" aria-hidden />
          </a>
          <Link
            to="/channels/$channelId"
            params={{ channelId: channel.id }}
            className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground transition-colors hover:border-input hover:bg-secondary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {m.view_channel()}
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </article>
    </li>
  )
}
