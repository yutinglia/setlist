import { CalendarDays, ChevronDown, SlidersHorizontal } from "lucide-react"
import { useEffect, useState } from "react"

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

function activeFilterCount(filters: SearchFilterValues): number {
  return [
    filters.channel_id,
    filters.type,
    filters.date_from,
    filters.date_to,
  ].filter(Boolean).length
}

export function SearchFilters({ filters, onChange }: Props) {
  const channels = useChannelOptions()
  const activeCount = activeFilterCount(filters)
  const [open, setOpen] = useState(activeCount > 0)

  useEffect(() => {
    if (activeCount > 0) setOpen(true)
  }, [activeCount])

  return (
    <section className="mt-4 overflow-hidden rounded-xl border border-border/70 bg-card/55">
      <div className="flex items-center justify-between gap-3 px-3 py-2.5 sm:px-4">
        <button
          type="button"
          className="flex min-w-0 items-center gap-2 text-sm font-semibold"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          <SlidersHorizontal className="size-4 text-primary" aria-hidden />
          {m.search_filters_show()}
          {activeCount > 0 ? (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[0.65rem] text-primary">
              {m.search_filters_active({ count: String(activeCount) })}
            </span>
          ) : null}
          <ChevronDown
            className={cn(
              "size-3.5 text-muted-foreground transition-transform",
              open && "rotate-180",
            )}
            aria-hidden
          />
        </button>

        {activeCount > 0 ? (
          <button
            type="button"
            className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
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

      {open ? (
        <div className="animate-fade border-t border-border/60 px-3 pt-4 pb-4 sm:px-4">
          <div
            className="inline-flex rounded-lg bg-secondary/70 p-1"
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
                variant={filters.type === value ? "default" : "ghost"}
                aria-pressed={filters.type === value}
                onClick={() => onChange({ ...filters, type: value })}
              >
                {label}
              </Button>
            ))}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(13rem,1fr)_minmax(10rem,0.65fr)_minmax(10rem,0.65fr)]">
            <label className="flex min-w-0 flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                {m.search_channel_label()}
              </span>
              <select
                className={cn(
                  "h-11 w-full rounded-lg border border-input bg-card px-3 text-sm",
                  "outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30",
                )}
                value={filters.channel_id ?? ""}
                onChange={(event) =>
                  onChange({
                    ...filters,
                    channel_id: event.target.value || undefined,
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

            <DateFilter
              label={m.search_date_from()}
              value={yyyymmddToHtmlDate(filters.date_from)}
              max={yyyymmddToHtmlDate(filters.date_to) || undefined}
              onChange={(value) =>
                onChange({
                  ...filters,
                  date_from: htmlDateToYyyymmdd(value),
                })
              }
            />

            <DateFilter
              label={m.search_date_to()}
              value={yyyymmddToHtmlDate(filters.date_to)}
              min={yyyymmddToHtmlDate(filters.date_from) || undefined}
              onChange={(value) =>
                onChange({
                  ...filters,
                  date_to: htmlDateToYyyymmdd(value),
                })
              }
            />
          </div>
        </div>
      ) : null}
    </section>
  )
}

function DateFilter({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: string
  min?: string
  max?: string
  onChange: (value: string) => void
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <CalendarDays className="size-3.5" aria-hidden />
        {label}
      </span>
      <Input
        type="date"
        className="h-11 bg-card"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
        aria-label={label}
      />
    </label>
  )
}
