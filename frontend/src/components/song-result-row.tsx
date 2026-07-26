import { Link } from "@tanstack/react-router"
import { Clock3, ExternalLink, Play } from "lucide-react"

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
        "surface animate-rise group relative overflow-hidden transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_24px_70px_-42px_rgba(79,70,190,0.5)]",
        stagger,
      )}
    >
      <div className="flex items-stretch">
        <span className="hidden w-14 shrink-0 place-items-center border-r border-border/60 bg-secondary/35 font-mono text-xs text-muted-foreground sm:grid">
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="min-w-0 text-left">
            <div className="flex flex-wrap items-center gap-2">
              {song.timestamp ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 font-mono text-[0.68rem] font-semibold text-primary">
                  <Clock3 className="size-3" aria-hidden />
                  {song.timestamp}
                </span>
              ) : null}
              {song.analyzed_by_llm ? (
                <span className="rounded-full bg-accent/20 px-2 py-1 font-mono text-[0.6rem] font-semibold tracking-wide text-accent-foreground uppercase">
                  AI clean
                </span>
              ) : null}
            </div>
            <Link
              to="/songs/$songId"
              params={{ songId: String(song.id) }}
              className="mt-2.5 block font-display text-xl font-bold tracking-tight text-foreground transition-colors group-hover:text-primary sm:text-2xl"
            >
              {song.title}
            </Link>
            <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
              <Link
                to="/channels/$channelId"
                params={{ channelId: song.channel_id }}
                className="font-semibold text-foreground/85 transition-colors hover:text-primary"
              >
                {song.channel_name}
              </Link>
              {song.video_title ? (
                <>
                  <span className="mx-2 text-border">/</span>
                  <span>{song.video_title}</span>
                </>
              ) : null}
            </p>
          </div>

          <a
            href={song.video_url}
            target="_blank"
            rel="noreferrer"
            className={cn(
              buttonVariants({ variant: "outline", size: "lg" }),
              "group/play shrink-0 self-start sm:self-center",
            )}
          >
            <span className="grid size-6 place-items-center rounded-full bg-primary text-primary-foreground">
              <Play className="size-3 fill-current" aria-hidden />
            </span>
            {m.open_youtube()}
            <ExternalLink
              className="size-3.5 text-muted-foreground transition-transform group-hover/play:translate-x-0.5"
              aria-hidden
            />
          </a>
        </div>
      </div>
    </li>
  )
}
