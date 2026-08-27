import { createFileRoute } from "@tanstack/react-router"
import { ListMusic, Radio } from "lucide-react"

import { useRecentUpdates } from "@/api/hooks"
import { ChannelCard } from "@/components/channel-card"
import { PageMetadata } from "@/components/page-metadata"
import { QueryState } from "@/components/query-state"
import { SongResultCard } from "@/components/song-result-row"
import { formatInteger } from "@/lib/locale-format"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/updates")({
  component: RecentUpdatesPage,
})

function RecentUpdatesPage() {
  const query = useRecentUpdates()
  const channels = query.data?.channels ?? []
  const songs = query.data?.songs ?? []

  return (
    <section className="animate-fade flex flex-1 flex-col py-7 sm:py-10 lg:py-12">
      <PageMetadata
        path="/updates"
        title={`${m.recent_updates_heading()} | Setlist`}
        description={m.recent_updates_intro()}
      />

      <header className="page-header max-w-4xl">
        <p className="eyebrow">{m.recent_updates_eyebrow()}</p>
        <h1 className="page-title mt-2">
          {m.recent_updates_heading()}
        </h1>
        <p className="page-intro mt-3">
          {m.recent_updates_intro()}
        </p>
      </header>

      <div className="mt-10">
        <QueryState
          isLoading={query.isLoading}
          isError={query.isError}
          isEmpty={query.isSuccess && channels.length === 0 && songs.length === 0}
          emptyMessage={m.recent_updates_empty()}
          onRetry={() => void query.refetch()}
          loadingLayout="grid"
        >
          {channels.length > 0 ? (
            <section aria-labelledby="recent-channels-heading">
              <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-border/75 pb-5">
                <div>
                  <p className="eyebrow flex items-center gap-2">
                    <Radio className="size-3.5" aria-hidden />
                    {m.nav_channels()}
                  </p>
                  <h2
                    id="recent-channels-heading"
                    className="section-heading mt-2"
                  >
                    {m.recent_channels_heading()}
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {m.recent_channels_hint()}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {m.recent_channels_count({
                    count: formatInteger(channels.length),
                  })}
                </p>
              </div>
              <ul className="media-grid">
                {channels.map((channel, index) => (
                  <ChannelCard
                    key={channel.id}
                    channel={channel}
                    index={index}
                    showUpdatedAt
                  />
                ))}
              </ul>
            </section>
          ) : null}

          {songs.length > 0 ? (
            <section
              aria-labelledby="recent-songs-heading"
              className={channels.length > 0 ? "mt-14 sm:mt-18" : undefined}
            >
              <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-border/75 pb-5">
                <div>
                  <p className="eyebrow flex items-center gap-2">
                    <ListMusic className="size-3.5" aria-hidden />
                    {m.nav_search()}
                  </p>
                  <h2
                    id="recent-songs-heading"
                    className="section-heading mt-2"
                  >
                    {m.recent_songs_heading()}
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {m.recent_songs_hint()}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {m.recent_songs_count({
                    count: formatInteger(songs.length),
                  })}
                </p>
              </div>
              <ul className="media-grid">
                {songs.map((song, index) => (
                  <SongResultCard
                    key={song.id}
                    song={song}
                    index={index}
                    showUpdatedAt
                  />
                ))}
              </ul>
            </section>
          ) : null}
        </QueryState>
      </div>
    </section>
  )
}
