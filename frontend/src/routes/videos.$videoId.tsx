import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"

import { PAGE_SIZE, useVideoSongs } from "@/api/hooks"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { pageSearchSchema } from "@/lib/search-schemas"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/videos/$videoId")({
  validateSearch: pageSearchSchema,
  component: VideoSongsPage,
})

function VideoSongsPage() {
  const { videoId } = Route.useParams()
  const { page = 0 } = Route.useSearch()
  const navigate = Route.useNavigate()
  const query = useVideoSongs(videoId, page)

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
        {m.video_songs_heading()}
      </h1>
      <p className="mt-1 font-mono text-xs text-muted-foreground">{videoId}</p>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={query.isSuccess && query.data.items.length === 0}
          emptyMessage={m.songs_empty()}
          onRetry={() => void query.refetch()}
        >
          <ul className="divide-y divide-border/70">
            {query.data?.items.map((song, i) => (
              <li
                key={song.id ?? `${song.title}-${song.timestamp}-${i}`}
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
