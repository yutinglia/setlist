import { Link } from "@tanstack/react-router"
import { ExternalLink, Info, Play } from "lucide-react"

import type { YouTubeVideo } from "@/api/types"
import { buttonVariants } from "@/components/ui/button"
import { VideoListBadges } from "@/components/video-list-badges"
import {
  formatUploadDate,
  uploadDateTimeAttr,
} from "@/lib/upload-date"
import { cn } from "@/lib/utils"
import { youtubeThumbnailUrl, youtubeVideoUrl } from "@/lib/youtube"
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
      <Link
        to="/videos/$videoId"
        params={{ videoId: video.id }}
        className="media-thumbnail group/thumbnail"
        aria-label={`${video.title} — ${m.view_details()}`}
      >
        <img
          src={youtubeThumbnailUrl(video.id)}
          alt=""
          className="size-full object-cover transition-transform duration-300 group-hover/thumbnail:scale-[1.025]"
          loading="lazy"
        />
        <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/5 to-transparent" />
        <span className="absolute bottom-3 left-3 grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground shadow-lg transition-transform duration-200 group-hover/thumbnail:scale-105 group-focus-visible/thumbnail:scale-105">
          <Info className="size-4.5" aria-hidden />
        </span>
      </Link>

      <div className="flex min-w-0 flex-1 flex-col p-4 sm:p-5">
        <Link
          to="/videos/$videoId"
          params={{ videoId: video.id }}
          className="-m-1 line-clamp-2 rounded-lg p-1 text-lg leading-snug font-bold tracking-[-0.02em] transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {video.title}
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <VideoListBadges
            type={video.type}
            hasSetlist={video.has_song_list_comment}
          />
        </div>
        <div className="mt-auto pt-3">
          <time
            dateTime={uploadDateTimeAttr(
              video.upload_date,
              video.upload_date_precision,
            )}
            className="text-xs leading-relaxed font-medium text-muted-foreground tabular-nums"
          >
            {dateLabel ?? m.video_date_unknown()}
          </time>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <a
              href={youtubeVideoUrl(video.id)}
              target="_blank"
              rel="noreferrer"
              className={cn(
                buttonVariants({ variant: "secondary", size: "sm" }),
                "min-w-0",
              )}
              aria-label={m.open_youtube()}
            >
              <Play className="fill-current" aria-hidden />
              <span className="truncate">YouTube</span>
              <ExternalLink aria-hidden />
            </a>
            <Link
              to="/videos/$videoId"
              params={{ videoId: video.id }}
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
