import { Link } from "@tanstack/react-router"
import { Clock3, Info, Play } from "lucide-react"

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
        <span className="absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-transparent" />
        <span className="absolute inset-0 grid place-items-center opacity-0 transition-opacity group-hover/thumbnail:opacity-100 group-focus-visible/thumbnail:opacity-100">
          <span className="grid size-12 place-items-center rounded-full bg-brand text-white shadow-xl">
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

      <div className="flex min-w-0 flex-1 flex-col pt-3">
        <a
          href={song.video_url}
          target="_blank"
          rel="noreferrer"
          className="line-clamp-2 text-base leading-snug font-semibold tracking-[-0.01em] transition-colors hover:text-primary"
        >
          {song.title}
        </a>
        <Link
          to="/channels/$channelId"
          params={{ channelId: song.channel_id }}
          className="mt-1.5 w-fit max-w-full truncate text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          {song.channel_name}
        </Link>
        {song.video_title ? (
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {song.video_title}
          </p>
        ) : null}
        {showUpdatedAt && song.updated_at ? (
          <time
            dateTime={song.updated_at}
            className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground"
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
          className="mt-2"
        />

        <div className="mt-auto flex items-center justify-between gap-2 pt-3">
          <div className="flex items-center gap-1.5">
            {song.analyzed_by_llm ? (
              <span className="rounded-md bg-accent px-2 py-1 text-[0.68rem] font-medium text-accent-foreground">
                AI clean
              </span>
            ) : null}
          </div>
          <Link
            to="/songs/$songId"
            params={{ songId: String(song.id) }}
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
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
