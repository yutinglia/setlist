import {
  CalendarDays,
  Check,
  ChevronDown,
  Search,
  SlidersHorizontal,
  Users,
  X,
} from "lucide-react"
import { Popover } from "radix-ui"
import { useEffect, useState } from "react"

import { useChannelOptions } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { htmlDateToYyyymmdd, yyyymmddToHtmlDate } from "@/lib/search-schemas"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export type SearchFilterValues = {
  channel_ids?: string[]
  type?: "karaoke" | "song"
  date_from?: string
  date_to?: string
}

type Props = {
  filters: SearchFilterValues
  onChange: (next: SearchFilterValues) => void
}

function activeFilterCount(filters: SearchFilterValues): number {
  return [
    filters.channel_ids?.length,
    filters.type,
    filters.date_from,
    filters.date_to,
  ].filter(Boolean).length
}

export function SearchFilters({ filters, onChange }: Props) {
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
                channel_ids: undefined,
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

          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(15rem,1.15fr)_minmax(10rem,0.65fr)_minmax(10rem,0.65fr)]">
            <ChannelMultiSelect
              selected={filters.channel_ids ?? []}
              onChange={(channel_ids) =>
                onChange({
                  ...filters,
                  channel_ids:
                    channel_ids.length > 0 ? channel_ids : undefined,
                })
              }
            />

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

function ChannelMultiSelect({
  selected,
  onChange,
}: {
  selected: string[]
  onChange: (selected: string[]) => void
}) {
  const channels = useChannelOptions()
  const [query, setQuery] = useState("")
  const items = channels.data?.items ?? []
  const selectedSet = new Set(selected)
  const normalizedQuery = query.trim().toLocaleLowerCase()
  const visibleItems = normalizedQuery
    ? items.filter((channel) =>
        channel.name.toLocaleLowerCase().includes(normalizedQuery),
      )
    : items
  const names = new Map(items.map((channel) => [channel.id, channel.name]))

  function toggle(channelId: string) {
    onChange(
      selectedSet.has(channelId)
        ? selected.filter((id) => id !== channelId)
        : [...selected, channelId],
    )
  }

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Users className="size-3.5" aria-hidden />
        {m.search_channel_label()}
      </span>
      <Popover.Root
        onOpenChange={(isOpen) => {
          if (!isOpen) setQuery("")
        }}
      >
        <Popover.Trigger asChild>
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full justify-between bg-card px-3 font-normal"
          >
            <span className="truncate">
              {selected.length > 0
                ? m.search_channel_selected({
                    count: String(selected.length),
                  })
                : m.search_channel_any()}
            </span>
            <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
          </Button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content
            align="start"
            sideOffset={6}
            className="z-[70] w-[var(--radix-popover-trigger-width)] min-w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-border bg-popover p-2 text-popover-foreground shadow-xl outline-none"
          >
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={m.search_channel_search()}
                className="h-10 pl-9"
                autoFocus
              />
            </div>

            <div
              className="mt-2 max-h-72 overflow-y-auto overscroll-contain"
              role="group"
              aria-label={m.search_channel_label()}
            >
              {channels.isLoading ? (
                <p className="px-3 py-5 text-center text-sm text-muted-foreground">
                  {m.search_channel_loading()}
                </p>
              ) : visibleItems.length === 0 ? (
                <p className="px-3 py-5 text-center text-sm text-muted-foreground">
                  {m.search_channel_empty()}
                </p>
              ) : (
                visibleItems.map((channel) => {
                  const checked = selectedSet.has(channel.id)
                  return (
                    <button
                      key={channel.id}
                      type="button"
                      role="checkbox"
                      aria-checked={checked}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                        checked
                          ? "bg-primary/10 text-primary"
                          : "hover:bg-secondary",
                      )}
                      onClick={() => toggle(channel.id)}
                    >
                      {channel.thumbnail_url ? (
                        <img
                          src={channel.thumbnail_url}
                          alt=""
                          className="size-8 rounded-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <span className="grid size-8 place-items-center rounded-full bg-secondary font-display text-xs font-bold">
                          {channel.name.slice(0, 1)}
                        </span>
                      )}
                      <span className="min-w-0 flex-1 truncate font-medium">
                        {channel.name}
                      </span>
                      <span
                        className={cn(
                          "grid size-5 shrink-0 place-items-center rounded-md border",
                          checked
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-input",
                        )}
                      >
                        {checked ? (
                          <Check className="size-3.5" aria-hidden />
                        ) : null}
                      </span>
                    </button>
                  )
                })
              )}
            </div>

            {selected.length > 0 ? (
              <div className="mt-2 border-t border-border/60 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => onChange([])}
                >
                  <X aria-hidden />
                  {m.search_channel_clear()}
                </Button>
              </div>
            ) : null}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>

      {selected.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {selected.map((channelId) => (
            <button
              key={channelId}
              type="button"
              className="inline-flex max-w-full items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
              onClick={() => toggle(channelId)}
              aria-label={`${m.search_channel_remove()} ${names.get(channelId) ?? ""}`}
            >
              <span className="truncate">
                {names.get(channelId) ?? m.search_channel_unknown()}
              </span>
              <X className="size-3 shrink-0" aria-hidden />
            </button>
          ))}
        </div>
      ) : null}
    </div>
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
