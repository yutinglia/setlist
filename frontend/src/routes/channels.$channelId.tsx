import { useCallback, useEffect, useState } from "react"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  CalendarDays,
  Check,
  ChevronRight,
  RefreshCw,
} from "lucide-react"

import { api } from "@/api/client"
import { useAuthSession, useChannelVideos } from "@/api/hooks"
import type { ChannelVideoRefresh } from "@/api/types"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { Button } from "@/components/ui/button"
import { VideoListBadges } from "@/components/video-list-badges"
import { useClampPage } from "@/hooks/use-clamp-page"
import { CHANNEL_PAGE_SIZES } from "@/lib/pagination"
import {
  channelVideosSearchSchema,
  resolveChannelPageSize,
  toChannelVideosSearch,
} from "@/lib/search-schemas"
import {
  formatUploadDate,
  sortVideosByUploadDateDesc,
  uploadDateTimeAttr,
} from "@/lib/upload-date"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/$channelId")({
  validateSearch: channelVideosSearchSchema,
  component: ChannelVideosPage,
})

type ChannelTab = "karaoke" | "videos"
type SetlistFilter = "all" | "yes" | "no"
type ReloadStatus = "idle" | "loading" | "done" | "error"

const TAB_TO_TYPE = {
  karaoke: "karaoke",
  videos: "song",
} as const satisfies Record<ChannelTab, "karaoke" | "song">

function setlistParamToFilter(
  value: "true" | "false" | undefined,
): SetlistFilter {
  if (value === "true") return "yes"
  if (value === "false") return "no"
  return "all"
}

function setlistFilterToQuery(
  filter: SetlistFilter,
): boolean | undefined {
  if (filter === "yes") return true
  if (filter === "no") return false
  return undefined
}

function ChannelVideosPage() {
  const { channelId } = Route.useParams()
  const {
    page = 0,
    tab: tabParam,
    has_song_list: hasSongListParam,
    limit: limitParam,
  } = Route.useSearch()
  const tab: ChannelTab = tabParam ?? "karaoke"
  const pageSize = resolveChannelPageSize(limitParam)
  const setlistFilter =
    tab === "karaoke" ? setlistParamToFilter(hasSongListParam) : "all"
  const hasSongList = setlistFilterToQuery(setlistFilter)
  const videoType = TAB_TO_TYPE[tab]
  const navigate = Route.useNavigate()
  const queryClient = useQueryClient()
  const auth = useAuthSession()
  const canManage =
    auth.data?.authenticated === true &&
    auth.data.role === "admin" &&
    auth.data.management_enabled
  const query = useChannelVideos(
    channelId,
    page,
    videoType,
    hasSongList,
    pageSize,
  )
  const [reloadStatus, setReloadStatus] = useState<ReloadStatus>("idle")
  const [reloadDetail, setReloadDetail] = useState<string>("")

  const changePage = useCallback(
    (next: number) => {
      void navigate({
        search: toChannelVideosSearch({
          tab,
          page: next,
          has_song_list:
            tab === "karaoke" ? hasSongListParam : undefined,
          limit: pageSize,
        }),
        replace: true,
      })
    },
    [navigate, tab, hasSongListParam, pageSize],
  )
  useClampPage(page, query.data?.total, pageSize, changePage)

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
      search: toChannelVideosSearch({
        tab: next,
        limit: pageSize,
      }),
    })
  }

  function setSetlistFilter(next: SetlistFilter) {
    void navigate({
      search: toChannelVideosSearch({
        tab: "karaoke",
        has_song_list:
          next === "yes" ? "true" : next === "no" ? "false" : undefined,
        limit: pageSize,
      }),
    })
  }

  function setLimit(next: number) {
    void navigate({
      search: toChannelVideosSearch({
        tab,
        has_song_list:
          tab === "karaoke" ? hasSongListParam : undefined,
        limit: next,
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
    tab === "videos"
      ? m.song_videos_empty()
      : setlistFilter === "yes"
        ? m.karaoke_empty_with_setlist()
        : setlistFilter === "no"
          ? m.karaoke_empty_without_setlist()
          : m.karaoke_empty()
  const videos = sortVideosByUploadDateDesc(query.data?.items ?? [])

  return (
    <section className="animate-fade py-10 sm:py-14">
      <Link
        to="/channels"
        className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-4" aria-hidden />
        {m.nav_channels()}
      </Link>

      <header className="mt-7 flex flex-col gap-5 border-b border-border/70 pb-8 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="eyebrow">{m.channel_library_eyebrow()}</p>
          <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
            {m.channel_videos_heading()}
          </h1>
          <p className="mt-3 break-all font-mono text-xs text-muted-foreground">
            {channelId}
          </p>
        </div>
        {canManage ? (
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
      </header>

      <div className="surface mt-7 flex flex-col gap-4 p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4">
        <div
          className="inline-flex self-start rounded-lg bg-secondary/70 p-1"
          role="tablist"
          aria-label={m.channel_tabs_label()}
        >
          <Button
            type="button"
            role="tab"
            size="sm"
            variant={tab === "karaoke" ? "default" : "ghost"}
            aria-selected={tab === "karaoke"}
            onClick={() => setTab("karaoke")}
          >
            {m.channel_tab_karaoke()}
          </Button>
          <Button
            type="button"
            role="tab"
            size="sm"
            variant={tab === "videos" ? "default" : "ghost"}
            aria-selected={tab === "videos"}
            onClick={() => setTab("videos")}
          >
            {m.channel_tab_videos()}
          </Button>
        </div>

        {tab === "karaoke" ? (
          <div
            className="flex flex-wrap items-center gap-1"
            role="group"
            aria-label={m.setlist_filter_label()}
          >
            <span className="mr-1 text-xs font-medium text-muted-foreground">
              {m.setlist_filter_label()}
            </span>
            {(
              [
                ["all", m.setlist_filter_all()],
                ["yes", m.setlist_filter_yes()],
                ["no", m.setlist_filter_no()],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={setlistFilter === value ? "secondary" : "ghost"}
                aria-pressed={setlistFilter === value}
                onClick={() => setSetlistFilter(value)}
              >
                {label}
              </Button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="mt-7" role="tabpanel">
        {query.data ? (
          <p className="mb-4 font-mono text-xs text-muted-foreground">
            {m.videos_count({ total: String(query.data.total) })}
          </p>
        ) : null}
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
            <ul className="grid gap-3">
              {videos.map((video, i) => {
                const formattedDate = formatUploadDate(video.upload_date)
                const dateLabel =
                  formattedDate &&
                  video.upload_date_precision === "approximate"
                    ? m.video_date_approximate({ date: formattedDate })
                    : formattedDate
                return (
                  <li
                    key={video.id}
                    className={`animate-rise stagger-${Math.min((i % 4) + 1, 4)}`}
                  >
                    <Link
                      to="/videos/$videoId"
                      params={{ videoId: video.id }}
                      className="surface group flex items-center gap-4 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/30 sm:p-5"
                    >
                      <span className="hidden size-11 shrink-0 place-items-center rounded-xl bg-secondary text-primary sm:grid">
                        <CalendarDays className="size-4" aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block font-display text-base font-bold leading-snug transition-colors group-hover:text-primary sm:text-lg">
                          {video.title}
                        </span>
                        <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
                          <time
                            dateTime={uploadDateTimeAttr(
                              video.upload_date,
                              video.upload_date_precision,
                            )}
                            className="font-mono tabular-nums tracking-wide"
                          >
                            {dateLabel ?? m.video_date_unknown()}
                          </time>
                          <VideoListBadges
                            type={video.type}
                            hasSetlist={video.has_song_list_comment}
                          />
                        </span>
                      </span>
                      <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" aria-hidden />
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
              pageSize={pageSize}
              disabled={isReloading}
              onPageChange={changePage}
              pageSizeOptions={CHANNEL_PAGE_SIZES}
              onPageSizeChange={setLimit}
            />
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
