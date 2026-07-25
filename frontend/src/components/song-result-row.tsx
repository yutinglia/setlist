import { Link } from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"

import type { SongSearchResult } from "@/api/types"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

type Props = {
  song: SongSearchResult
  index?: number
}

export function SongResultRow({ song, index = 0 }: Props) {
  const stagger = `stagger-${Math.min((index % 4) + 1, 4)}`

  return (
    <li
      className={cn(
        "animate-rise group border-b border-border/70 py-4 first:pt-0 last:border-0 last:pb-0",
        stagger,
      )}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
        <div className="min-w-0 text-left">
          <Link
            to="/songs/$songId"
            params={{ songId: String(song.id) }}
            className="font-display text-lg font-semibold tracking-tight text-foreground transition-colors hover:text-primary"
          >
            {song.title}
          </Link>
          <p className="mt-1 text-sm text-muted-foreground">
            <Link
              to="/channels/$channelId"
              params={{ channelId: song.channel_id }}
              className="font-medium text-foreground/80 transition-colors hover:text-primary"
            >
              {song.channel_name}
            </Link>
            {song.video_title ? (
              <>
                <span className="mx-1.5 text-border">·</span>
                <span>{song.video_title}</span>
              </>
            ) : null}
          </p>
          {song.timestamp ? (
            <p className="mt-1 font-mono text-xs tracking-wide text-primary/90">
              {song.timestamp}
            </p>
          ) : null}
        </div>
        <a
          href={song.video_url}
          target="_blank"
          rel="noreferrer"
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "shrink-0 self-start sm:self-center",
          )}
        >
          {m.open_youtube()}
          <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </div>
    </li>
  )
}
