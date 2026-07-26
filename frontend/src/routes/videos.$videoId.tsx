import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowLeft,
  CalendarDays,
  Check,
  ExternalLink,
  Hash,
  Play,
  Radio,
  RefreshCw,
} from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useState } from "react"

import { api } from "@/api/client"
import {
  PAGE_SIZE,
  useAuthSession,
  useVideo,
  useVideoSongs,
} from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { PageMetadata } from "@/components/page-metadata"
import { QueryState } from "@/components/query-state"
import { Button, buttonVariants } from "@/components/ui/button"
import { VideoListBadges } from "@/components/video-list-badges"
import { useClampPage } from "@/hooks/use-clamp-page"
import { pageSearchSchema } from "@/lib/search-schemas"
import { formatUploadDate, uploadDateTimeAttr } from "@/lib/upload-date"
import { cn } from "@/lib/utils"
import { youtubeUrlAtTimestamp } from "@/lib/youtube"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/videos/$videoId")({
  validateSearch: pageSearchSchema,
  component: VideoDetailPage,
})

function VideoDetailPage() {
  const { videoId } = Route.useParams()
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const queryClient = useQueryClient()
  const auth = useAuthSession()
  const videoQuery = useVideo(videoId)
  const isSong = (videoQuery.data?.type ?? "").toLowerCase() === "song"
  const isKaraoke = (videoQuery.data?.type ?? "").toLowerCase() === "karaoke"
  const songsQuery = useVideoSongs(videoId, page, {
    enabled: videoQuery.isSuccess && !isSong,
  })
  const [reloadStatus, setReloadStatus] = useState<
    "idle" | "loading" | "done" | "error"
  >("idle")
  const [reloadDetail, setReloadDetail] = useState("")
  const canManage =
    auth.data?.authenticated === true &&
    auth.data.role === "admin" &&
    auth.data.management_enabled
  const changePage = useCallback(
    (next: number) => {
      void navigate({
        search: (prev) => ({
          ...prev,
          page: next || undefined,
        }),
        replace: true,
      })
    },
    [navigate],
  )
  useClampPage(page, songsQuery.data?.total, PAGE_SIZE, changePage)

  useEffect(() => {
    if (reloadStatus !== "done" && reloadStatus !== "error") return
    const timer = window.setTimeout(() => {
      setReloadStatus("idle")
      setReloadDetail("")
    }, 5000)
    return () => window.clearTimeout(timer)
  }, [reloadStatus])

  async function handleSongReload() {
    setReloadStatus("loading")
    setReloadDetail("")
    try {
      const result = await api.reloadVideoSongs(videoId)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["videos", videoId] }),
        queryClient.invalidateQueries({
          queryKey: ["videos", videoId, "songs"],
        }),
        queryClient.invalidateQueries({ queryKey: ["report", "summary"] }),
      ])
      setReloadStatus("done")
      setReloadDetail(
        m.song_reload_summary({ count: String(result.song_count) }),
      )
    } catch (error) {
      setReloadStatus("error")
      setReloadDetail(
        error instanceof Error ? error.message : m.song_reload_failed(),
      )
    }
  }

  const formattedUploadDate = formatUploadDate(videoQuery.data?.upload_date)
  const uploadDateLabel =
    formattedUploadDate &&
    videoQuery.data?.upload_date_precision === "approximate"
      ? m.video_date_approximate({ date: formattedUploadDate })
      : formattedUploadDate
  const metadataTitle = videoQuery.data
    ? `${videoQuery.data.title} | Setlist`
    : "VTuber karaoke video | Setlist"
  const metadataDescription = videoQuery.data
    ? `Browse the indexed songs and timestamps for ${videoQuery.data.title}.`
    : "Browse a VTuber karaoke video and jump to songs at exact YouTube timestamps."

  return (
    <section className="animate-fade py-10 sm:py-14">
      <PageMetadata
        path={`/videos/${encodeURIComponent(videoId)}`}
        title={metadataTitle}
        description={metadataDescription}
        noIndex={videoQuery.isError}
      />
      {videoQuery.data?.channel_id ? (
        <Link
          to="/channels/$channelId"
          params={{ channelId: videoQuery.data.channel_id }}
          className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {m.channel_videos_heading()}
        </Link>
      ) : (
        <Link
          to="/channels"
          className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {m.nav_channels()}
        </Link>
      )}

      <div className="mt-7">
        <QueryState
          isLoading={videoQuery.isLoading}
          isError={videoQuery.isError}
          isEmpty={videoQuery.isSuccess && !videoQuery.data}
          emptyMessage={m.videos_empty()}
          onRetry={() => void videoQuery.refetch()}
        >
          {videoQuery.data ? (
            <article className="animate-rise">
              <header className="relative overflow-hidden rounded-2xl border border-border/70 bg-card/80 p-6 sm:p-8 lg:p-10">
                <div className="absolute -top-28 -right-20 size-72 rounded-full bg-primary/12 blur-3xl" />
                <div className="relative max-w-4xl">
                  <p className="eyebrow">{m.video_type_label()}</p>
                  <h1 className="mt-4 font-display text-3xl leading-tight font-bold tracking-tight sm:text-5xl">
                    {videoQuery.data.title}
                  </h1>
                  <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
                    <time
                      dateTime={uploadDateTimeAttr(
                        videoQuery.data.upload_date,
                        videoQuery.data.upload_date_precision,
                      )}
                      className="inline-flex items-center gap-1.5 font-mono tabular-nums"
                    >
                      <CalendarDays className="size-3.5" aria-hidden />
                      {uploadDateLabel ?? m.video_date_unknown()}
                    </time>
                    <VideoListBadges
                      type={videoQuery.data.type}
                      hasSetlist={videoQuery.data.has_song_list_comment}
                      showSetlist={!isSong}
                    />
                  </div>
                </div>
              </header>

              <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_19rem]">
                <div>
                  {isSong ? (
                    <div className="surface flex min-h-44 flex-col items-center justify-center px-6 py-10 text-center">
                      <span className="grid size-12 place-items-center rounded-2xl bg-secondary text-primary">
                        <Radio className="size-5" aria-hidden />
                      </span>
                      <p className="mt-4 max-w-md text-sm text-muted-foreground">
                        {m.video_song_no_setlist()}
                      </p>
                    </div>
                  ) : (
                    <section className="surface overflow-hidden">
                      <div className="border-b border-border/60 px-5 py-5 sm:px-6">
                        <h2 className="font-display text-xl font-bold tracking-tight sm:text-2xl">
                          {m.video_songs_heading()}
                        </h2>
                        <p className="mt-1.5 text-sm text-muted-foreground">
                          {m.video_setlist_hint()}
                        </p>
                      </div>
                      <div className="p-3 sm:p-4">
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
                          <ol className="grid gap-1">
                            {songsQuery.data?.items.map((song, index) => (
                              <li
                                key={
                                  song.id ??
                                  `${song.title}-${song.timestamp}-${index}`
                                }
                                className={`animate-rise group flex items-center gap-3 rounded-xl px-3 py-3 transition-colors hover:bg-secondary/60 stagger-${Math.min((index % 4) + 1, 4)}`}
                              >
                                <span className="w-7 shrink-0 text-right font-mono text-xs text-muted-foreground">
                                  {String(
                                    page * PAGE_SIZE + index + 1,
                                  ).padStart(2, "0")}
                                </span>
                                <span className="min-w-0 flex-1">
                                  {song.id != null ? (
                                    <Link
                                      to="/songs/$songId"
                                      params={{ songId: String(song.id) }}
                                      className="block truncate font-semibold transition-colors group-hover:text-primary"
                                    >
                                      {song.title}
                                    </Link>
                                  ) : (
                                    <span className="block truncate font-semibold">
                                      {song.title}
                                    </span>
                                  )}
                                </span>
                                {song.timestamp ? (
                                  <a
                                    href={youtubeUrlAtTimestamp(
                                      videoQuery.data.url,
                                      song.timestamp,
                                    )}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary/10 px-2.5 py-1.5 font-mono text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
                                    aria-label={m.play_from_timestamp({
                                      timestamp: song.timestamp,
                                    })}
                                  >
                                    <Play
                                      className="size-3 fill-current"
                                      aria-hidden
                                    />
                                    {song.timestamp}
                                  </a>
                                ) : null}
                              </li>
                            ))}
                          </ol>
                          {songsQuery.data ? (
                            <PaginationControls
                              page={page}
                              total={songsQuery.data.total}
                              pageSize={PAGE_SIZE}
                              disabled={songsQuery.isFetching}
                              onPageChange={changePage}
                            />
                          ) : null}
                        </QueryState>
                      </div>
                    </section>
                  )}
                </div>

                <aside className="surface h-fit p-5">
                  <dl className="space-y-5">
                    <MetaRow
                      icon={Radio}
                      label={m.song_channel()}
                      value={
                        <Link
                          to="/channels/$channelId"
                          params={{ channelId: videoQuery.data.channel_id }}
                          className="break-all font-medium text-primary hover:underline"
                        >
                          {videoQuery.data.channel_id}
                        </Link>
                      }
                    />
                    <MetaRow
                      icon={CalendarDays}
                      label={m.video_upload_date()}
                      value={
                        <time
                          dateTime={uploadDateTimeAttr(
                            videoQuery.data.upload_date,
                            videoQuery.data.upload_date_precision,
                          )}
                          className="font-mono text-xs tabular-nums"
                        >
                          {uploadDateLabel ?? m.video_date_unknown()}
                        </time>
                      }
                    />
                    <MetaRow
                      icon={Hash}
                      label="YouTube ID"
                      value={
                        <span className="break-all font-mono text-xs">
                          {videoId}
                        </span>
                      }
                    />
                  </dl>

                  <a
                    href={videoQuery.data.url}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(
                      buttonVariants({ size: "lg" }),
                      "mt-6 flex w-full",
                    )}
                  >
                    <Play className="fill-current" aria-hidden />
                    {m.open_youtube()}
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                  {canManage && isKaraoke ? (
                    <div className="mt-3 border-t border-border/60 pt-4">
                      <Button
                        type="button"
                        variant={
                          reloadStatus === "error" ? "destructive" : "outline"
                        }
                        className="w-full"
                        disabled={reloadStatus === "loading"}
                        onClick={() => void handleSongReload()}
                      >
                        {reloadStatus === "done" ? (
                          <Check aria-hidden />
                        ) : (
                          <RefreshCw
                            className={
                              reloadStatus === "loading"
                                ? "animate-spin"
                                : undefined
                            }
                            aria-hidden
                          />
                        )}
                        {reloadStatus === "loading"
                          ? m.song_reload_loading()
                          : reloadStatus === "done"
                            ? m.song_reload_done()
                            : m.song_reload_action()}
                      </Button>
                      <p
                        className="mt-2 min-h-8 text-xs leading-relaxed text-muted-foreground"
                        aria-live="polite"
                      >
                        {reloadDetail || m.song_reload_hint()}
                      </p>
                    </div>
                  ) : null}
                </aside>
              </div>
            </article>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}

function MetaRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Radio
  label: string
  value: React.ReactNode
}) {
  return (
    <div className="border-b border-border/60 pb-4 last:border-0 last:pb-0">
      <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <Icon className="size-3.5" aria-hidden />
        {label}
      </dt>
      <dd className="mt-1.5 text-sm">{value}</dd>
    </div>
  )
}
