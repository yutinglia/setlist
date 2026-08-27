import { Link, createFileRoute } from "@tanstack/react-router"
import { Clock3, ExternalLink, Play, Radio, Video } from "lucide-react"

import { useSong } from "@/api/hooks"
import { ContextualBackButton } from "@/components/contextual-back-button"
import { PageMetadata } from "@/components/page-metadata"
import { QueryState } from "@/components/query-state"
import { SetlistAttribution } from "@/components/setlist-attribution"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { youtubeThumbnailUrl } from "@/lib/youtube"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/songs/$songId")({
  component: SongDetailPage,
})

function SongDetailPage() {
  const { songId } = Route.useParams()
  const navigate = Route.useNavigate()
  const id = Number(songId)
  const invalidId = !Number.isSafeInteger(id) || id <= 0
  const query = useSong(id)
  const metadataTitle = query.data
    ? m.meta_song_title({
        title: query.data.title,
        channel: query.data.channel_name,
      })
    : m.meta_song_title_fallback()
  const metadataDescription = query.data
    ? m.meta_song_description({
        title: query.data.title,
        video: query.data.video_title ?? query.data.video_id,
      })
    : m.meta_song_description_fallback()

  return (
    <section className="animate-fade mx-auto w-full max-w-6xl py-7 sm:py-10">
      <PageMetadata
        path={`/songs/${songId}`}
        title={metadataTitle}
        description={metadataDescription}
        noIndex={invalidId || query.isError}
      />
      <ContextualBackButton
        label={m.back()}
        onFallback={() => {
          if (query.data) {
            return navigate({
              to: "/videos/$videoId",
              params: { videoId: query.data.video_id },
              replace: true,
            })
          }
          return navigate({ to: "/", replace: true })
        }}
      />

      <div className="mt-5">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={invalidId}
          emptyMessage={m.song_not_found()}
          onRetry={() => void query.refetch()}
        >
          {query.data ? (
            <article className="surface animate-rise overflow-hidden">
              <div className="grid lg:grid-cols-[minmax(19rem,0.9fr)_minmax(0,1.1fr)] lg:items-stretch">
                <a
                  href={query.data.video_url}
                  target="_blank"
                  rel="noreferrer"
                  className="group relative aspect-video min-h-full overflow-hidden bg-secondary outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring lg:aspect-auto"
                  aria-label={m.open_youtube()}
                >
                  <img
                    src={youtubeThumbnailUrl(query.data.video_id)}
                    alt=""
                    className="size-full min-h-64 object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                  />
                  <span className="absolute inset-0 grid place-items-center bg-black/15 transition-colors group-hover:bg-black/25">
                    <span className="grid size-14 place-items-center rounded-full bg-brand text-white shadow-xl">
                      <Play className="size-6 fill-current" aria-hidden />
                    </span>
                  </span>
                  {query.data.timestamp ? (
                    <span className="absolute right-3 bottom-3 inline-flex items-center gap-1.5 rounded-md bg-black/85 px-2.5 py-1.5 text-xs font-semibold text-white tabular-nums">
                      <Clock3 className="size-3.5" aria-hidden />
                      {query.data.timestamp}
                    </span>
                  ) : null}
                </a>

                <div className="flex flex-col justify-center p-6 sm:p-9 lg:p-12">
                  <p className="eyebrow">{m.song_detail_eyebrow()}</p>
                  <h1 className="mt-4 text-4xl leading-tight font-bold tracking-[-0.04em] sm:text-5xl">
                    {query.data.title}
                  </h1>
                  <p className="mt-4 text-sm text-muted-foreground">
                    {query.data.channel_name}
                    {query.data.video_title ? ` · ${query.data.video_title}` : ""}
                  </p>

                  <a
                    href={query.data.video_url}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(
                      buttonVariants({ size: "lg" }),
                      "mt-8 w-fit",
                    )}
                  >
                    <Play className="fill-current" aria-hidden />
                    {m.open_youtube()}
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                </div>
              </div>

              <aside className="border-t border-border bg-secondary/35 p-5 sm:p-6">
                <dl className="grid gap-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
                  <div className="min-w-0">
                    <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                      <Radio className="size-3.5" aria-hidden />
                      {m.song_channel()}
                    </dt>
                    <dd className="mt-2 truncate">
                      <Link
                        to="/channels/$channelId"
                        params={{ channelId: query.data.channel_id }}
                        className="inline-flex min-h-11 items-center font-semibold text-foreground underline-offset-2 hover:text-primary hover:underline"
                      >
                        {query.data.channel_name}
                      </Link>
                    </dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                      <Video className="size-3.5" aria-hidden />
                      {m.song_video()}
                    </dt>
                    <dd className="mt-2 leading-relaxed">
                      <Link
                        to="/videos/$videoId"
                        params={{ videoId: query.data.video_id }}
                        className="inline-flex min-h-11 items-center font-medium underline-offset-2 hover:text-primary hover:underline"
                      >
                        {query.data.video_title ?? query.data.video_id}
                      </Link>
                    </dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-xs font-medium text-muted-foreground">
                      {m.song_setlist_credit()}
                    </dt>
                    <dd className="mt-2">
                      {query.data.setlist_comment_author ? (
                        <SetlistAttribution
                          author={query.data.setlist_comment_author}
                          authorId={query.data.setlist_comment_author_id}
                          commentId={query.data.setlist_comment_id}
                          videoId={query.data.video_id}
                          className="text-sm"
                        />
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </aside>
            </article>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
