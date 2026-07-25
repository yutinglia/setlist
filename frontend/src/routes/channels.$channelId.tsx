import { useCallback, useEffect, useState } from "react"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Check, RefreshCw } from "lucide-react"

import { api } from "@/api/client"
import { PAGE_SIZE, useChannelVideos } from "@/api/hooks"
import type { ChannelVideoRefresh } from "@/api/types"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { Button } from "@/components/ui/button"
import { VideoListBadges } from "@/components/video-list-badges"
import { useClampPage } from "@/hooks/use-clamp-page"
import { channelVideosSearchSchema } from "@/lib/search-schemas"
import {
  formatUploadDate,
  sortVideosByUploadDateDesc,
  uploadDateTimeAttr,
} from "@/lib/upload-date"
import { MANAGEMENT_UI_ENABLED } from "@/lib/app-config"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/$channelId")({
  validateSearch: channelVideosSearchSchema,
  component: ChannelVideosPage,
})

type ChannelTab = "karaoke" | "videos"
type ReloadStatus = "idle" | "loading" | "done" | "error"

const TAB_TO_TYPE = {
  karaoke: "karaoke",
  videos: "song",
} as const satisfies Record<ChannelTab, "karaoke" | "song">

function ChannelVideosPage() {
  const { channelId } = Route.useParams()
  const { page = 0, tab: tabParam } = Route.useSearch()
  const tab: ChannelTab = tabParam ?? "karaoke"
  const videoType = TAB_TO_TYPE[tab]
  const navigate = Route.useNavigate()
  const queryClient = useQueryClient()
  const query = useChannelVideos(channelId, page, videoType)
  const [reloadStatus, setReloadStatus] = useState<ReloadStatus>("idle")
  const [reloadDetail, setReloadDetail] = useState<string>("")
  const changePage = useCallback(
    (next: number) => {
      void navigate({
        search: (prev) => ({
          ...prev,
          tab: tab === "karaoke" ? undefined : tab,
          page: next || undefined,
        }),
        replace: true,
      })
    },
    [navigate, tab],
  )
  useClampPage(page, query.data?.total, PAGE_SIZE, changePage)

  useEffect(() => {
    if (reloadStatus !== "done" && reloadStatus !== "error") return
    const timer = window.setTimeout(() => {
      setReloadStatus("idle")
      setReloadDetail("")
    }, 4000)
    return () => window.clearTimeout(timer)
  }, [reloadStatus])

  function setTab(next: ChannelTab) {
    void navigate({
      search: () => ({
        tab: next === "karaoke" ? undefined : next,
        page: undefined,
      }),
    })
  }

  async function handleReload() {
    setReloadStatus("loading")
    setReloadDetail("")
    try {
      const refresh: ChannelVideoRefresh =
        await api.refreshChannelVideos(channelId)
      await queryClient.invalidateQueries({
        queryKey: ["channels", channelId, "videos"],
      })
      setReloadStatus("done")
      setReloadDetail(
        m.reload_summary({
          scraped: String(refresh.scraped),
        }),
      )
    } catch (err) {
      setReloadStatus("error")
      setReloadDetail(err instanceof Error ? err.message : m.reload_failed())
    }
  }

  const isReloading = reloadStatus === "loading"
  const reloadLabel =
    reloadStatus === "loading"
      ? m.reload_loading()
      : reloadStatus === "done"
        ? m.reload_done()
        : reloadStatus === "error"
          ? m.reload_failed()
          : m.reload_list()
  const emptyMessage =
    tab === "karaoke" ? m.karaoke_empty() : m.song_videos_empty()
  const videos = sortVideosByUploadDateDesc(query.data?.items ?? [])

  return (
    <section className="animate-fade pt-10">
      <Link
        to="/channels"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        {m.nav_channels()}
      </Link>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            {m.channel_videos_heading()}
          </h1>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {channelId}
          </p>
        </div>
        {MANAGEMENT_UI_ENABLED ? (
          <div className="flex max-w-sm flex-col items-end gap-1">
            <Button
              type="button"
              variant={reloadStatus === "error" ? "destructive" : "outline"}
              size="sm"
              disabled={isReloading}
              aria-busy={isReloading}
              title={m.reload_hint()}
              onClick={() => void handleReload()}
            >
              {reloadStatus === "done" ? (
                <Check aria-hidden />
              ) : (
                <RefreshCw
                  className={isReloading ? "animate-spin" : undefined}
                  aria-hidden
                />
              )}
              {reloadLabel}
            </Button>
            <p
              className="min-h-4 text-right text-xs text-muted-foreground"
              aria-live="polite"
              role="status"
            >
              {isReloading
                ? m.reload_loading()
                : reloadDetail
                  ? reloadDetail
                  : m.reload_hint()}
            </p>
          </div>
        ) : null}
      </div>

      <div
        className="mt-8 inline-flex rounded-md border border-border bg-card/70 p-0.5"
        role="tablist"
        aria-label={m.channel_tabs_label()}
      >
        <Button
          type="button"
          role="tab"
          size="sm"
          variant={tab === "karaoke" ? "secondary" : "ghost"}
          aria-selected={tab === "karaoke"}
          onClick={() => setTab("karaoke")}
        >
          {m.channel_tab_karaoke()}
        </Button>
        <Button
          type="button"
          role="tab"
          size="sm"
          variant={tab === "videos" ? "secondary" : "ghost"}
          aria-selected={tab === "videos"}
          onClick={() => setTab("videos")}
        >
          {m.channel_tab_videos()}
        </Button>
      </div>

      <div className="mt-6" role="tabpanel">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError && !query.data}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={emptyMessage}
          onRetry={() => void query.refetch()}
        >
          <div
            className={cn(
              "transition-opacity duration-200",
              isReloading && query.data && "opacity-55",
            )}
            aria-busy={isReloading}
          >
            <ul className="divide-y divide-border/70">
              {videos.map((video, i) => {
                const dateLabel = formatUploadDate(video.upload_date)
                return (
                  <li
                    key={video.id}
                    className={`animate-rise py-4 stagger-${Math.min((i % 4) + 1, 4)}`}
                  >
                    <Link
                      to="/videos/$videoId"
                      params={{ videoId: video.id }}
                      className="block text-left transition-colors hover:text-primary"
                    >
                      <span className="font-display text-base font-semibold">
                        {video.title}
                      </span>
                      <span className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
                        <time
                          dateTime={uploadDateTimeAttr(video.upload_date)}
                          className="font-mono tabular-nums tracking-wide"
                        >
                          {dateLabel ?? m.video_date_unknown()}
                        </time>
                        <VideoListBadges
                          type={video.type}
                          hasSetlist={video.has_song_list_comment}
                        />
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
          {query.data ? (
            <PaginationControls
              page={page}
              total={query.data.total}
              pageSize={PAGE_SIZE}
              disabled={isReloading}
              onPageChange={changePage}
            />
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
