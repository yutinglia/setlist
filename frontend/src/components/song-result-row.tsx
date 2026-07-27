import { Link } from "@tanstack/react-router"
import { Clock3, Info, Play } from "lucide-react"

import type { SongSearchResult } from "@/api/types"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { youtubeThumbnailUrl } from "@/lib/youtube"
import { m } from "@/paraglide/messages"

type Props = {
  song: SongSearchResult
  index?: number
}

export function SongResultCard({ song, index = 0 }: Props) {
  const stagger = `stagger-${Math.min((index % 4) + 1, 4)}`

  return (
    <li
      className={cn(
        "media-card animate-rise",
        stagger,
      )}
    >
      <a
        href={song.video_url}
        target="_blank"
        rel="noreferrer"
        className="media-thumbnail group/thumbnail"
        aria-label={`${song.title} — ${m.open_youtube()}`}
      >
        <img
          src={youtubeThumbnailUrl(song.video_id)}
          alt=""
          className="size-full object-cover transition-transform duration-300 group-hover/thumbnail:scale-[1.025]"
          loading="lazy"
        />
        <span className="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent to-transparent" />
        <span className="absolute inset-0 grid place-items-center opacity-0 transition-opacity group-hover/thumbnail:opacity-100 group-focus-visible/thumbnail:opacity-100">
          <span className="grid size-12 place-items-center rounded-full bg-primary text-primary-foreground shadow-xl">
            <Play className="size-5 fill-current" aria-hidden />
          </span>
        </span>
        {song.timestamp ? (
          <span className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded-md bg-black/80 px-2 py-1 font-mono text-[0.68rem] font-semibold text-white">
            <Clock3 className="size-3" aria-hidden />
            {song.timestamp}
          </span>
        ) : null}
      </a>

      <div className="flex min-w-0 flex-1 flex-col px-1 pt-3">
        <a
          href={song.video_url}
          target="_blank"
          rel="noreferrer"
          className="line-clamp-2 font-display text-base leading-snug font-bold tracking-tight transition-colors hover:text-primary"
        >
          {song.title}
        </a>
        <Link
          to="/channels/$channelId"
          params={{ channelId: song.channel_id }}
          className="mt-1.5 w-fit truncate text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
        >
          {song.channel_name}
        </Link>
        {song.video_title ? (
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {song.video_title}
          </p>
        ) : null}

        <div className="mt-auto flex items-center justify-between gap-2 pt-3">
          <div className="flex items-center gap-1.5">
            {song.analyzed_by_llm ? (
              <span className="rounded-full bg-accent/20 px-2 py-1 font-mono text-[0.58rem] font-semibold tracking-wide text-accent-foreground uppercase">
                AI clean
              </span>
            ) : null}
          </div>
          <Link
            to="/songs/$songId"
            params={{ songId: String(song.id) }}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "shrink-0",
            )}
          >
            <Info aria-hidden />
            {m.view_details()}
          </Link>
        </div>
      </div>
    </li>
  )
}

/** Backward-compatible export for any downstream imports. */
export function SongResultRow(props: Props) {
  return <SongResultCard {...props} />
}
