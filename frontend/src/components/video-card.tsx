import { Link } from "@tanstack/react-router"
import { ExternalLink, Info } from "lucide-react"

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
        <span className="absolute inset-0 bg-gradient-to-t from-black/25 via-transparent to-transparent" />
        <span className="absolute inset-0 grid place-items-center opacity-0 transition-opacity group-hover/thumbnail:opacity-100 group-focus-visible/thumbnail:opacity-100">
          <span className="grid size-12 place-items-center rounded-full bg-brand text-white shadow-xl">
            <Info className="size-5" aria-hidden />
          </span>
        </span>
      </Link>

      <div className="flex min-w-0 flex-1 flex-col pt-3">
        <Link
          to="/videos/$videoId"
          params={{ videoId: video.id }}
          className="line-clamp-2 text-base leading-snug font-semibold tracking-[-0.01em] transition-colors hover:text-primary"
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
            className="text-xs leading-relaxed text-muted-foreground tabular-nums"
          >
            {dateLabel ?? m.video_date_unknown()}
          </time>
          <div className="mt-2 flex flex-wrap justify-end gap-2">
            <a
              href={youtubeVideoUrl(video.id)}
              target="_blank"
              rel="noreferrer"
              className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
                "shrink-0",
              )}
              aria-label={m.open_youtube()}
            >
              YouTube
              <ExternalLink aria-hidden />
            </a>
            <Link
              to="/videos/$videoId"
              params={{ videoId: video.id }}
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
      </div>
    </li>
  )
}
