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
    <section className="animate-fade flex flex-1 flex-col py-10 sm:py-14">
      <PageMetadata
        path="/updates"
        title={`${m.recent_updates_heading()} | Setlist`}
        description={m.recent_updates_intro()}
      />

      <header className="max-w-3xl border-b border-border/70 pb-8">
        <p className="eyebrow">{m.recent_updates_eyebrow()}</p>
        <h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">
          {m.recent_updates_heading()}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
          {m.recent_updates_intro()}
        </p>
      </header>

      <div className="mt-8">
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
              <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="eyebrow flex items-center gap-2">
                    <Radio className="size-3.5" aria-hidden />
                    {m.nav_channels()}
                  </p>
                  <h2
                    id="recent-channels-heading"
                    className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl"
                  >
                    {m.recent_channels_heading()}
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {m.recent_channels_hint()}
                  </p>
                </div>
                <p className="font-mono text-xs text-muted-foreground">
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
              className={channels.length > 0 ? "mt-14 sm:mt-16" : undefined}
            >
              <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="eyebrow flex items-center gap-2">
                    <ListMusic className="size-3.5" aria-hidden />
                    {m.nav_search()}
                  </p>
                  <h2
                    id="recent-songs-heading"
                    className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl"
                  >
                    {m.recent_songs_heading()}
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {m.recent_songs_hint()}
                  </p>
                </div>
                <p className="font-mono text-xs text-muted-foreground">
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
