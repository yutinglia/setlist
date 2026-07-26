import { Link, createFileRoute } from "@tanstack/react-router"
import {
  ArrowLeft,
  Clock3,
  ExternalLink,
  Play,
  Radio,
  Video,
} from "lucide-react"

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
    <section className="animate-fade mx-auto w-full max-w-5xl py-10 sm:py-14">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-4" aria-hidden />
        {m.back_to_search()}
      </Link>

      <div className="mt-7">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={invalidId}
          emptyMessage={m.song_not_found()}
          onRetry={() => void query.refetch()}
        >
          {query.data ? (
            <article className="surface animate-rise relative overflow-hidden">
              <div className="absolute -top-28 -right-24 size-80 rounded-full bg-primary/15 blur-3xl" />
              <div className="absolute -bottom-32 -left-20 size-72 rounded-full bg-accent/10 blur-3xl" />

              <div className="relative grid gap-8 p-6 sm:p-10 lg:grid-cols-[minmax(0,1fr)_18rem] lg:p-12">
                <div>
                  <p className="eyebrow">{m.song_detail_eyebrow()}</p>
                  <h1 className="mt-4 font-display text-4xl leading-tight font-bold tracking-[-0.04em] sm:text-6xl">
                    {query.data.title}
                  </h1>

                  {query.data.timestamp ? (
                    <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-2 font-mono text-sm font-semibold text-primary">
                      <Clock3 className="size-4" aria-hidden />
                      {query.data.timestamp}
                    </div>
                  ) : null}

                  <a
                    href={query.data.video_url}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(
                      buttonVariants({ size: "lg" }),
                      "mt-8 flex w-fit",
                    )}
                  >
                    <span className="grid size-6 place-items-center rounded-full bg-primary-foreground/15">
                      <Play className="size-3 fill-current" aria-hidden />
                    </span>
                    {m.open_youtube()}
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                </div>

                <aside className="rounded-2xl border border-border/60 bg-background/45 p-5 backdrop-blur-sm">
                  <dl className="space-y-5 text-sm">
                    <div className="border-b border-border/60 pb-4">
                      <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                        <Radio className="size-3.5" aria-hidden />
                        {m.song_channel()}
                      </dt>
                      <dd className="mt-2">
                        <Link
                          to="/channels/$channelId"
                          params={{ channelId: query.data.channel_id }}
                          className="font-semibold text-primary underline-offset-2 hover:underline"
                        >
                          {query.data.channel_name}
                        </Link>
                      </dd>
                    </div>
                    <div>
                      <dt className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                        <Video className="size-3.5" aria-hidden />
                        {m.song_video()}
                      </dt>
                      <dd className="mt-2 leading-relaxed">
                        <Link
                          to="/videos/$videoId"
                          params={{ videoId: query.data.video_id }}
                          className="font-medium underline-offset-2 hover:text-primary hover:underline"
                        >
                          {query.data.video_title ?? query.data.video_id}
                        </Link>
                      </dd>
                    </div>
                  </dl>
                </aside>
              </div>
            </article>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
