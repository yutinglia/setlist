import { ArrowRight, LoaderCircle, Search, X } from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useId, useRef, useState } from "react"

import {
  type SongSearchFilters,
  useSongSuggestions,
} from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { m } from "@/paraglide/messages"
import { useUiStore } from "@/stores/ui-store"

const SUGGESTION_DEBOUNCE_MS = 500
const MIN_SUGGESTION_LENGTH = 2

type Props = {
  initialQuery?: string
  onQuerySubmit: (q: string) => void
  suggestionFilters?: SongSearchFilters
  autoFocus?: boolean
}

export function SearchForm({
  initialQuery = "",
  onQuerySubmit,
  suggestionFilters,
  autoFocus,
}: Props) {
  const [value, setValue] = useState(initialQuery)
  const [isOpen, setIsOpen] = useState(false)
  const [hasEdited, setHasEdited] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const currentQuery = value.trim()
  const debouncedQuery = useDebouncedValue(
    currentQuery,
    SUGGESTION_DEBOUNCE_MS,
  )
  const isDebouncing = currentQuery !== debouncedQuery
  const inputRef = useRef<HTMLInputElement>(null)
  const listboxId = useId()
  const queryClient = useQueryClient()
  const recent = useUiStore((s) => s.recentSearches)
  const addRecent = useUiStore((s) => s.addRecentSearch)
  const clearRecent = useUiStore((s) => s.clearRecentSearches)
  const suggestionQuery = useSongSuggestions(
    debouncedQuery,
    suggestionFilters,
    {
      enabled:
        isOpen &&
        hasEdited &&
        !isDebouncing &&
        currentQuery.length >= MIN_SUGGESTION_LENGTH,
    },
  )
  const suggestions = suggestionQuery.data ?? []
  const showSuggestions =
    isOpen &&
    hasEdited &&
    currentQuery.length >= MIN_SUGGESTION_LENGTH

  useEffect(() => {
    setValue(initialQuery)
    setIsOpen(false)
    setHasEdited(false)
    setActiveIndex(-1)
  }, [initialQuery])

  useEffect(() => {
    if (isDebouncing) {
      void queryClient.cancelQueries({
        queryKey: ["songs", "suggestions"],
        exact: false,
      })
    }
  }, [isDebouncing, queryClient, currentQuery])

  useEffect(() => {
    setActiveIndex(-1)
  }, [debouncedQuery])

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const isEditing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable
      if (event.key === "/" && !isEditing) {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener("keydown", focusSearch)
    return () => window.removeEventListener("keydown", focusSearch)
  }, [])

  function submitQuery(query: string) {
    const q = query.trim()
    setValue(q)
    setIsOpen(false)
    setHasEdited(false)
    setActiveIndex(-1)
    onQuerySubmit(q)
    if (q) addRecent(q)
  }

  return (
    <form
      className="w-full"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setIsOpen(false)
          setActiveIndex(-1)
        }
      }}
      onSubmit={(e) => {
        e.preventDefault()
        submitQuery(value)
      }}
    >
      <div className="flex gap-2.5">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-primary"
            aria-hidden
          />
          <Input
            ref={inputRef}
            value={value}
            onChange={(event) => {
              const next = event.target.value
              setValue(next)
              setHasEdited(true)
              setIsOpen(next.trim().length >= MIN_SUGGESTION_LENGTH)
              setActiveIndex(-1)
            }}
            onFocus={() => {
              if (
                hasEdited &&
                currentQuery.length >= MIN_SUGGESTION_LENGTH
              ) {
                setIsOpen(true)
              }
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault()
                setIsOpen(false)
                setActiveIndex(-1)
                return
              }
              if (event.key === "Enter") {
                event.preventDefault()
                const selected =
                  showSuggestions && activeIndex >= 0
                    ? suggestions[activeIndex]
                    : undefined
                submitQuery(selected?.title ?? value)
                return
              }
              if (!showSuggestions || suggestions.length === 0) {
                return
              }
              if (event.key === "ArrowDown") {
                event.preventDefault()
                setActiveIndex((current) =>
                  Math.min(current + 1, suggestions.length - 1),
                )
              } else if (event.key === "ArrowUp") {
                event.preventDefault()
                setActiveIndex((current) =>
                  current <= 0 ? suggestions.length - 1 : current - 1,
                )
              }
            }}
            placeholder={m.search_placeholder()}
            maxLength={200}
            className="h-14 rounded-xl border-border/80 bg-card pr-20 pl-12 text-base shadow-[0_18px_50px_-34px_rgba(40,30,100,0.6)]"
            autoFocus={autoFocus}
            aria-label={m.search_placeholder()}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={showSuggestions}
            aria-controls={listboxId}
            aria-activedescendant={
              activeIndex >= 0
                ? `${listboxId}-option-${activeIndex}`
                : undefined
            }
          />
          {value ? (
            <button
              type="button"
              className="absolute top-1/2 right-3 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              aria-label={m.search_clear()}
              onClick={() => {
                setValue("")
                setIsOpen(false)
                setHasEdited(false)
                setActiveIndex(-1)
                onQuerySubmit("")
                inputRef.current?.focus()
              }}
            >
              <X className="size-4" aria-hidden />
            </button>
          ) : (
            <kbd className="pointer-events-none absolute top-1/2 right-4 hidden -translate-y-1/2 rounded border border-border bg-secondary/70 px-1.5 py-0.5 font-mono text-[0.65rem] text-muted-foreground sm:block">
              /
            </kbd>
          )}
          {showSuggestions ? (
            <div
              id={listboxId}
              role="listbox"
              aria-label={m.search_suggestions_label()}
              className="absolute top-[calc(100%+0.5rem)] left-0 z-30 w-full overflow-hidden rounded-xl border border-border/80 bg-popover p-1.5 text-popover-foreground shadow-xl"
            >
              {isDebouncing || suggestionQuery.isFetching ? (
                <div
                  className="flex items-center gap-2 px-3 py-2.5 text-sm text-muted-foreground"
                  role="status"
                >
                  <LoaderCircle
                    className="size-4 animate-spin"
                    aria-hidden
                  />
                  {m.search_suggestions_loading()}
                </div>
              ) : suggestionQuery.isError ? (
                <div
                  className="px-3 py-2.5 text-sm text-muted-foreground"
                  role="status"
                >
                  {m.search_suggestions_error()}
                </div>
              ) : suggestions.length === 0 ? (
                <div
                  className="px-3 py-2.5 text-sm text-muted-foreground"
                  role="status"
                >
                  {m.search_suggestions_empty()}
                </div>
              ) : (
                suggestions.map((suggestion, index) => (
                  <button
                    key={suggestion.title.toLocaleLowerCase()}
                    id={`${listboxId}-option-${index}`}
                    type="button"
                    role="option"
                    aria-selected={activeIndex === index}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                      activeIndex === index
                        ? "bg-primary/10 text-primary"
                        : "hover:bg-secondary"
                    }`}
                    onMouseDown={(event) => event.preventDefault()}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => submitQuery(suggestion.title)}
                  >
                    <Search
                      className="size-4 shrink-0 text-muted-foreground"
                      aria-hidden
                    />
                    <span className="truncate">{suggestion.title}</span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
        <Button type="submit" className="h-14 px-4 sm:px-6" size="lg">
          <span className="hidden sm:inline">{m.search_submit()}</span>
          <ArrowRight aria-hidden />
        </Button>
      </div>
      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-left text-xs text-muted-foreground">
        <p>{m.search_hint()}</p>
        <p className="hidden shrink-0 font-mono lg:block">
          {m.search_shortcut()}
        </p>
      </div>

      {recent.length > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-left">
          <span className="font-mono text-[0.65rem] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
            {m.recent_searches()}
          </span>
          {recent.map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-full border border-border/70 bg-card/70 px-3 py-1 text-xs text-secondary-foreground transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-primary"
              onClick={() => {
                submitQuery(item)
              }}
            >
              {item}
            </button>
          ))}
          <button
            type="button"
            className="ml-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            onClick={clearRecent}
          >
            {m.clear_recent()}
          </button>
        </div>
      ) : null}
    </form>
  )
}
