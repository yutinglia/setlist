import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"

import { PAGE_SIZE, useChannelVideos } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { pageSearchSchema } from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/channels/$channelId")({
  validateSearch: pageSearchSchema,
  component: ChannelVideosPage,
})

function ChannelVideosPage() {
  const { channelId } = Route.useParams()
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = useChannelVideos(channelId, page)

  return (
    <section className="animate-fade pt-10">
      <Link
        to="/channels"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        {m.nav_channels()}
      </Link>

      <h1 className="mt-6 font-display text-3xl font-bold tracking-tight">
        {m.channel_videos_heading()}
      </h1>
      <p className="mt-1 font-mono text-xs text-muted-foreground">{channelId}</p>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={m.videos_empty()}
          onRetry={() => void query.refetch()}
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
                  <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    {video.upload_date ? <span>{video.upload_date}</span> : null}
                    <span>
                      {video.has_song_list_comment
                        ? m.has_setlist()
                        : m.no_setlist()}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {query.data ? (
            <PaginationControls
              page={page}
              total={query.data.total}
              pageSize={PAGE_SIZE}
              disabled={query.isFetching}
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
