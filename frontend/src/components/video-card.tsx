import { Link } from "@tanstack/react-router"
import { Info, Play } from "lucide-react"

import type { YouTubeVideo } from "@/api/types"
import { buttonVariants } from "@/components/ui/button"
import { VideoListBadges } from "@/components/video-list-badges"
import {
  formatUploadDate,
  uploadDateTimeAttr,
} from "@/lib/upload-date"
import { cn } from "@/lib/utils"
import { youtubeThumbnailUrl } from "@/lib/youtube"
import { m } from "@/paraglide/messages"

type Props = {
  video: YouTubeVideo
  index?: number
}

export function VideoCard({ video, index = 0 }: Props) {
  const formattedDate = formatUploadDate(video.upload_date)
  const dateLabel =
    formattedDate && video.upload_date_precision === "approximate"
      ? m.video_date_approximate({ date: formattedDate })
      : formattedDate

  return (
    <li
      className={cn(
        "media-card animate-rise",
        `stagger-${Math.min((index % 4) + 1, 4)}`,
      )}
    >
      <a
        href={video.url}
        target="_blank"
        rel="noreferrer"
        className="media-thumbnail group/thumbnail"
        aria-label={`${video.title} — ${m.open_youtube()}`}
      >
        <img
          src={youtubeThumbnailUrl(video.id)}
          alt=""
          className="size-full object-cover transition-transform duration-300 group-hover/thumbnail:scale-[1.025]"
          loading="lazy"
        />
        <span className="absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-transparent" />
        <span className="absolute inset-0 grid place-items-center opacity-0 transition-opacity group-hover/thumbnail:opacity-100 group-focus-visible/thumbnail:opacity-100">
          <span className="grid size-12 place-items-center rounded-full bg-primary text-primary-foreground shadow-xl">
            <Play className="size-5 fill-current" aria-hidden />
          </span>
        </span>
      </a>

      <div className="flex min-w-0 flex-1 flex-col px-1 pt-3">
        <a
          href={video.url}
          target="_blank"
          rel="noreferrer"
          className="line-clamp-2 font-display text-base leading-snug font-bold tracking-tight transition-colors hover:text-primary"
        >
          {video.title}
        </a>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <VideoListBadges
            type={video.type}
            hasSetlist={video.has_song_list_comment}
          />
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 pt-3">
          <time
            dateTime={uploadDateTimeAttr(
              video.upload_date,
              video.upload_date_precision,
            )}
            className="font-mono text-[0.68rem] leading-relaxed text-muted-foreground tabular-nums"
          >
            {dateLabel ?? m.video_date_unknown()}
          </time>
          <Link
            to="/videos/$videoId"
            params={{ videoId: video.id }}
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
