import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowLeft, ExternalLink } from "lucide-react"

import { PAGE_SIZE, useVideo, useVideoSongs } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { buttonVariants } from "@/components/ui/button"
import { VideoListBadges } from "@/components/video-list-badges"
import { pageSearchSchema } from "@/lib/search-schemas"
import { formatUploadDate, uploadDateTimeAttr } from "@/lib/upload-date"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/videos/$videoId")({
  validateSearch: pageSearchSchema,
  component: VideoDetailPage,
})

function VideoDetailPage() {
  const { videoId } = Route.useParams()
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const videoQuery = useVideo(videoId)
  const isSong = (videoQuery.data?.type ?? "").toLowerCase() === "song"
  const songsQuery = useVideoSongs(videoId, page, {
    enabled: videoQuery.isSuccess && !isSong,
  })
  const uploadDateLabel = formatUploadDate(videoQuery.data?.upload_date)

  return (
    <section className="animate-fade pt-10">
      {videoQuery.data?.channel_id ? (
        <Link
          to="/channels/$channelId"
          params={{ channelId: videoQuery.data.channel_id }}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          {m.channel_videos_heading()}
        </Link>
      ) : (
        <Link
          to="/channels"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          {m.nav_channels()}
        </Link>
      )}

      <div className="mt-8">
        <QueryState
          isLoading={videoQuery.isLoading}
          isError={videoQuery.isError}
          isEmpty={videoQuery.isSuccess && !videoQuery.data}
          emptyMessage={m.videos_empty()}
          onRetry={() => void videoQuery.refetch()}
        >
          {videoQuery.data ? (
            <article className="animate-rise space-y-8 text-left">
              <header className="space-y-3">
                <h1 className="font-display text-3xl font-bold tracking-tight">
                  {videoQuery.data.title}
                </h1>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
                  <time
                    dateTime={uploadDateTimeAttr(videoQuery.data.upload_date)}
                    className="font-mono tabular-nums tracking-wide"
                  >
                    {uploadDateLabel ?? m.video_date_unknown()}
                  </time>
                  <VideoListBadges
                    type={videoQuery.data.type}
                    hasSetlist={videoQuery.data.has_song_list_comment}
                    showSetlist={!isSong}
                  />
                </div>
                <p className="font-mono text-xs text-muted-foreground">
                  {videoId}
                </p>
              </header>

              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-muted-foreground">{m.song_channel()}</dt>
                  <dd className="mt-0.5">
                    <Link
                      to="/channels/$channelId"
                      params={{ channelId: videoQuery.data.channel_id }}
                      className="font-medium underline-offset-2 hover:underline"
                    >
                      {videoQuery.data.channel_id}
                    </Link>
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">
                    {m.video_upload_date()}
                  </dt>
                  <dd className="mt-0.5">
                    <time
                      dateTime={uploadDateTimeAttr(videoQuery.data.upload_date)}
                      className="font-mono tabular-nums"
                    >
                      {uploadDateLabel ?? m.video_date_unknown()}
                    </time>
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">{m.video_type_label()}</dt>
                  <dd className="mt-0.5 capitalize">
                    {videoQuery.data.type ?? m.badge_other()}
                  </dd>
                </div>
              </dl>

              <a
                href={videoQuery.data.url}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants(), "inline-flex")}
              >
                {m.open_youtube()}
                <ExternalLink className="size-3.5" aria-hidden />
              </a>

              {isSong ? (
                <p className="border-t border-border/70 pt-6 text-sm text-muted-foreground">
                  {m.video_song_no_setlist()}
                </p>
              ) : (
                <div className="border-t border-border/70 pt-6">
                  <h2 className="font-display text-xl font-semibold tracking-tight">
                    {m.video_songs_heading()}
                  </h2>
                  <div className="mt-4">
                    <QueryState
                      isLoading={songsQuery.isLoading}
                      isError={songsQuery.isError}
                      isEmpty={
                        songsQuery.isSuccess &&
                        songsQuery.data.items.length === 0
                      }
                      emptyMessage={m.songs_empty()}
                      onRetry={() => void songsQuery.refetch()}
                    >
                      <ul className="divide-y divide-border/70">
                        {songsQuery.data?.items.map((song, i) => (
                          <li
                            key={
                              song.id ??
                              `${song.title}-${song.timestamp}-${i}`
                            }
                            className={`animate-rise flex items-baseline justify-between gap-4 py-3 stagger-${Math.min((i % 4) + 1, 4)}`}
                          >
                            {song.id != null ? (
                              <Link
                                to="/songs/$songId"
                                params={{ songId: String(song.id) }}
                                className="min-w-0 text-left font-medium transition-colors hover:text-primary"
                              >
                                {song.title}
                              </Link>
                            ) : (
                              <span className="min-w-0 text-left font-medium">
                                {song.title}
                              </span>
                            )}
                            {song.timestamp ? (
                              <span className="shrink-0 font-mono text-xs text-primary">
                                {song.timestamp}
                              </span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                      {songsQuery.data ? (
                        <PaginationControls
                          page={page}
                          total={songsQuery.data.total}
                          pageSize={PAGE_SIZE}
                          disabled={songsQuery.isFetching}
                          onPageChange={(next) =>
                            void navigate({
                              search: (prev) => ({
                                ...prev,
                                page: next || undefined,
                              }),
                            })
                          }
                        />
                      ) : null}
                    </QueryState>
                  </div>
                </div>
              )}
            </article>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
