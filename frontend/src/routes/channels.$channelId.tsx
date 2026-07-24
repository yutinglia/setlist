import { useEffect, useState } from "react"
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
import { pageSearchSchema } from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/$channelId")({
  validateSearch: pageSearchSchema,
  component: ChannelVideosPage,
})

type ReloadStatus = "idle" | "loading" | "done" | "error"

function ChannelVideosPage() {
  const { channelId } = Route.useParams()
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const queryClient = useQueryClient()
  const query = useChannelVideos(channelId, page)
  const [reloadStatus, setReloadStatus] = useState<ReloadStatus>("idle")
  const [reloadDetail, setReloadDetail] = useState<string>("")

  useEffect(() => {
    if (reloadStatus !== "done" && reloadStatus !== "error") return
    const timer = window.setTimeout(() => {
      setReloadStatus("idle")
      setReloadDetail("")
    }, 4000)
    return () => window.clearTimeout(timer)
  }, [reloadStatus])

  async function handleReload() {
    setReloadStatus("loading")
    setReloadDetail("")
    try {
      // Real refresh: scrape YouTube list + reclassify types (not just GET cache).
      const refresh: ChannelVideoRefresh =
        await api.refreshChannelVideos(channelId)
      await queryClient.invalidateQueries({
        queryKey: ["channels", channelId, "videos"],
      })
      const result = await query.refetch()
      if (result.isError) {
        setReloadStatus("error")
        setReloadDetail(refresh.message)
        return
      }
      setReloadStatus("done")
      setReloadDetail(
        `${refresh.message} (${refresh.mode}: scraped ${refresh.scraped}, reclassified ${refresh.reclassified})`,
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
      </div>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError && !query.data}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={m.videos_empty()}
          onRetry={() => void handleReload()}
        >
          <div
            className={
              isReloading && query.data
                ? "opacity-55 transition-opacity duration-200"
                : "transition-opacity duration-200"
            }
            aria-busy={isReloading}
          >
            <ul className="divide-y divide-border/70">
              {query.data?.items.map((video, i) => (
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
                      {video.upload_date ? (
                        <span>{video.upload_date}</span>
                      ) : null}
                      <VideoListBadges
                        type={video.type}
                        hasSetlist={video.has_song_list_comment}
                      />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          {query.data ? (
            <PaginationControls
              page={page}
              total={query.data.total}
              pageSize={PAGE_SIZE}
              disabled={isReloading}
              onPageChange={(next) =>
                void navigate({
                  search: (prev) => ({ ...prev, page: next || undefined }),
                })
              }
            />
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
