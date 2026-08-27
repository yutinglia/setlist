import { Link } from "@tanstack/react-router"
import { Clock3, ExternalLink, Info, Play } from "lucide-react"

import type { SongSearchResult } from "@/api/types"
import { SetlistAttribution } from "@/components/setlist-attribution"
import { buttonVariants } from "@/components/ui/button"
import { formatApiDateTime } from "@/lib/locale-format"
import { cn } from "@/lib/utils"
import { youtubeThumbnailUrl } from "@/lib/youtube"
import { m } from "@/paraglide/messages"

type Props = {
  song: SongSearchResult
  index?: number
  showUpdatedAt?: boolean
}

export function SongResultCard({
  song,
  index = 0,
  showUpdatedAt = false,
}: Props) {
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
        <span className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/5 to-transparent" />
        <span className="absolute bottom-3 left-3 grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground shadow-lg transition-transform duration-200 group-hover/thumbnail:scale-105 group-focus-visible/thumbnail:scale-105">
          <Play className="size-4.5 fill-current" aria-hidden />
        </span>
        {song.timestamp ? (
          <span className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded-md bg-black/80 px-2 py-1 font-mono text-[0.68rem] font-semibold text-white">
            <Clock3 className="size-3" aria-hidden />
            {song.timestamp}
          </span>
        ) : null}
      </a>

      <div className="flex min-w-0 flex-1 flex-col p-4 sm:p-5">
        <a
          href={song.video_url}
          target="_blank"
          rel="noreferrer"
          className="-m-1 min-h-11 line-clamp-2 rounded-lg p-1 text-lg leading-snug font-bold tracking-[-0.02em] transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {song.title}
        </a>
        <Link
          to="/channels/$channelId"
          params={{ channelId: song.channel_id }}
          className="mt-1 inline-flex min-h-11 w-fit max-w-full items-center truncate rounded-lg pr-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {song.channel_name}
        </Link>
        {song.video_title ? (
          <p className="line-clamp-2 text-sm leading-6 text-muted-foreground">
            {song.video_title}
          </p>
        ) : null}
        {showUpdatedAt && song.updated_at ? (
          <time
            dateTime={song.updated_at}
            className="mt-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground"
          >
            <Clock3 className="size-3.5 text-primary" aria-hidden />
            {m.recent_updated_at({
              when: formatApiDateTime(song.updated_at),
            })}
          </time>
        ) : null}
        <SetlistAttribution
          author={song.setlist_comment_author}
          authorId={song.setlist_comment_author_id}
          commentId={song.setlist_comment_id}
          videoId={song.video_id}
          className="mt-1"
        />

        <div className="mt-auto pt-3">
          <div className="mb-3 flex min-h-6 items-center gap-1.5">
            {song.analyzed_by_llm ? (
              <span className="rounded-full bg-accent px-2.5 py-1 text-[0.68rem] font-semibold text-accent-foreground">
                AI clean
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <a
              href={song.video_url}
              target="_blank"
              rel="noreferrer"
              className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "min-w-0")}
            >
              <Play className="fill-current" aria-hidden />
              <span className="truncate">YouTube</span>
              <ExternalLink className="size-3.5" aria-hidden />
            </a>
            <Link
              to="/songs/$songId"
              params={{ songId: String(song.id) }}
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "min-w-0",
              )}
            >
              <Info aria-hidden />
              <span className="truncate">{m.view_details()}</span>
            </Link>
          </div>
        </div>
      </div>
    </li>
  )
}

/** Backward-compatible export for any downstream imports. */
export function SongResultRow(props: Props) {
  return <SongResultCard {...props} />
}
