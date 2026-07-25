import { Link, createFileRoute } from "@tanstack/react-router"
import { ArrowLeft, ExternalLink } from "lucide-react"

import { useSong } from "@/api/hooks"
import { QueryState } from "@/components/query-state"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/songs/$songId")({
  component: SongDetailPage,
})

function SongDetailPage() {
  const { songId } = Route.useParams()
  const id = Number(songId)
  const invalidId = !Number.isSafeInteger(id) || id <= 0
  const query = useSong(id)

  return (
    <section className="animate-fade pt-10">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        {m.back_to_search()}
      </Link>

      <h1 className="mt-6 font-display text-3xl font-bold tracking-tight">
        {m.song_detail()}
      </h1>

      <div className="mt-8">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={invalidId}
          emptyMessage={m.song_not_found()}
          onRetry={() => void query.refetch()}
        >
          {query.data ? (
            <article className="animate-rise space-y-6 text-left">
              <div>
                <h2 className="font-display text-2xl font-semibold sm:text-3xl">
                  {query.data.title}
                </h2>
                {query.data.timestamp ? (
                  <p className="mt-2 font-mono text-sm text-primary">
                    {m.song_timestamp()}: {query.data.timestamp}
                  </p>
                ) : null}
              </div>

              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-muted-foreground">{m.song_channel()}</dt>
                  <dd className="mt-0.5">
                    <Link
                      to="/channels/$channelId"
                      params={{ channelId: query.data.channel_id }}
                      className="font-medium underline-offset-2 hover:underline"
                    >
                      {query.data.channel_name}
                    </Link>
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">{m.song_video()}</dt>
                  <dd className="mt-0.5">
                    <Link
                      to="/videos/$videoId"
                      params={{ videoId: query.data.video_id }}
                      className="underline-offset-2 hover:underline"
                    >
                      {query.data.video_title ?? query.data.video_id}
                    </Link>
                  </dd>
                </div>
              </dl>

              <a
                href={query.data.video_url}
                target="_blank"
                rel="noreferrer"
                className={cn(buttonVariants(), "inline-flex")}
              >
                {m.open_youtube()}
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            </article>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
