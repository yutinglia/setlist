import { useChannelOptions } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  htmlDateToYyyymmdd,
  yyyymmddToHtmlDate,
  type SongSearch,
} from "@/lib/search-schemas"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export type SearchFilterValues = Pick<
  SongSearch,
  "channel_id" | "type" | "date_from" | "date_to"
>

type Props = {
  filters: SearchFilterValues
  onChange: (next: SearchFilterValues) => void
}

function hasActiveFilters(filters: SearchFilterValues): boolean {
  return Boolean(
    filters.channel_id || filters.type || filters.date_from || filters.date_to,
  )
}

export function SearchFilters({ filters, onChange }: Props) {
  const channels = useChannelOptions()
  const active = hasActiveFilters(filters)

  return (
    <div className="mt-5 space-y-3 text-left">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {m.search_filters_heading()}
        </p>
        {active ? (
          <button
            type="button"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() =>
              onChange({
                channel_id: undefined,
                type: undefined,
                date_from: undefined,
                date_to: undefined,
              })
            }
          >
            {m.search_filters_clear()}
          </button>
        ) : null}
      </div>

      <div
        className="inline-flex rounded-md border border-border bg-card/70 p-0.5"
        role="group"
        aria-label={m.search_type_label()}
      >
        {(
          [
            [undefined, m.search_type_all()],
            ["karaoke", m.search_type_karaoke()],
            ["song", m.search_type_song()],
          ] as const
        ).map(([value, label]) => (
          <Button
            key={label}
            type="button"
            size="sm"
            variant={filters.type === value ? "secondary" : "ghost"}
            aria-pressed={filters.type === value}
            onClick={() => onChange({ ...filters, type: value })}
          >
            {label}
          </Button>
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <label className="flex min-w-0 flex-1 flex-col gap-1.5 sm:max-w-xs">
          <span className="text-xs text-muted-foreground">
            {m.search_channel_label()}
          </span>
          <select
            className={cn(
              "h-10 w-full rounded-md border border-border/80 bg-card/80 px-3 text-sm shadow-none",
              "outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40",
            )}
            value={filters.channel_id ?? ""}
            onChange={(e) =>
              onChange({
                ...filters,
                channel_id: e.target.value || undefined,
              })
            }
            aria-label={m.search_channel_label()}
          >
            <option value="">{m.search_channel_any()}</option>
            {(channels.data?.items ?? []).map((channel) => (
              <option key={channel.id} value={channel.id}>
                {channel.name || channel.id}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground">
            {m.search_date_from()}
          </span>
          <Input
            type="date"
            className="h-10 border-border/80 bg-card/80 shadow-none"
            value={yyyymmddToHtmlDate(filters.date_from)}
            max={yyyymmddToHtmlDate(filters.date_to) || undefined}
            onChange={(e) =>
              onChange({
                ...filters,
                date_from: htmlDateToYyyymmdd(e.target.value),
              })
            }
            aria-label={m.search_date_from()}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground">
            {m.search_date_to()}
          </span>
          <Input
            type="date"
            className="h-10 border-border/80 bg-card/80 shadow-none"
            value={yyyymmddToHtmlDate(filters.date_to)}
            min={yyyymmddToHtmlDate(filters.date_from) || undefined}
            onChange={(e) =>
              onChange({
                ...filters,
                date_to: htmlDateToYyyymmdd(e.target.value),
              })
            }
            aria-label={m.search_date_to()}
          />
        </label>
      </div>
    </div>
  )
}
