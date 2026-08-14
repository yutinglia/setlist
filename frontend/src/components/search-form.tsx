import { useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  ArrowRight,
  LoaderCircle,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import {
  type SongSearchFilters,
  useSongSuggestions,
} from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"
import { useUiStore } from "@/stores/ui-store"

const SUGGESTION_DEBOUNCE_MS = 500
const MIN_SUGGESTION_LENGTH = 2

type Props = {
  initialQuery?: string
  onQuerySubmit: (q: string) => void
  suggestionFilters?: SongSearchFilters
  autoFocus?: boolean
  variant?: "default" | "hero" | "compact"
  hint?: string
  showAdvancedSearchLink?: boolean
  shortcutEnabled?: boolean
  inputAriaLabel?: string
}

export function SearchForm({
  initialQuery = "",
  onQuerySubmit,
  suggestionFilters,
  autoFocus,
  variant = "default",
  hint,
  showAdvancedSearchLink = false,
  shortcutEnabled = true,
  inputAriaLabel,
}: Props) {
  const isHero = variant === "hero"
  const isCompact = variant === "compact"
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
      if (
        shortcutEnabled &&
        event.key === "/" &&
        !isEditing &&
        inputRef.current?.offsetParent !== null
      ) {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener("keydown", focusSearch)
    return () => window.removeEventListener("keydown", focusSearch)
  }, [shortcutEnabled])

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
      role={isCompact ? "search" : undefined}
      aria-label={isCompact ? m.nav_search() : undefined}
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
      <div className={cn("flex gap-2.5", isCompact && "gap-0")}>
        <div className="relative min-w-0 flex-1">
          <Search
            className={cn(
              "pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground",
              isCompact && "size-4",
            )}
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
            className={cn(
              "h-14 rounded-full border-input bg-card pr-20 pl-12 text-base shadow-sm focus-visible:bg-card",
              isHero &&
                "h-14 border-border pl-12 shadow-[0_10px_35px_-22px_rgba(0,0,0,0.45)] sm:h-16 sm:pl-14 sm:text-lg",
              isCompact &&
                "h-10 rounded-r-none rounded-l-full border-r-0 bg-background pr-11 pl-11 shadow-none focus-visible:z-10 focus-visible:bg-card",
            )}
            autoFocus={autoFocus}
            aria-label={inputAriaLabel ?? m.search_placeholder()}
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
              className={cn(
                "absolute top-1/2 right-3 grid size-9 -translate-y-1/2 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isCompact && "right-1.5 size-8",
              )}
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
            !isCompact && (
              <kbd className="pointer-events-none absolute top-1/2 right-4 hidden -translate-y-1/2 rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[0.65rem] text-muted-foreground sm:block">
                /
              </kbd>
            )
          )}
          {showSuggestions ? (
            <div
              id={listboxId}
              role="listbox"
              aria-label={m.search_suggestions_label()}
              className="absolute top-[calc(100%+0.5rem)] left-0 z-30 w-full overflow-hidden rounded-2xl border border-border bg-popover p-1.5 text-popover-foreground shadow-xl"
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
                        ? "bg-secondary text-foreground"
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
        <Button
          type="submit"
          className={cn(
            "h-14 px-5 sm:px-6",
            isHero && "h-14 px-5 sm:h-16 sm:px-8",
            isCompact &&
              "h-10 w-14 rounded-r-full rounded-l-none border border-input bg-secondary px-0 text-secondary-foreground shadow-none hover:bg-muted focus-visible:z-10",
          )}
          size={isCompact ? "sm" : "lg"}
          variant={isCompact ? "secondary" : "default"}
          aria-label={m.search_submit()}
        >
          {isCompact ? (
            <Search className="size-5" aria-hidden />
          ) : (
            <>
              <span className="hidden sm:inline">{m.search_submit()}</span>
              <ArrowRight aria-hidden />
            </>
          )}
        </Button>
      </div>
      {!isCompact ? (
        <>
          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-left text-xs text-muted-foreground">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <p>{hint ?? m.search_hint()}</p>
              {showAdvancedSearchLink ? (
                <Link
                  to="/search"
                  search={{ q: currentQuery || undefined }}
                  className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-full px-2 font-semibold text-primary hover:bg-primary/8"
                >
                  <SlidersHorizontal className="size-3.5" aria-hidden />
                  {m.search_advanced_link()}
                  <ArrowRight className="size-3.5" aria-hidden />
                </Link>
              ) : null}
            </div>
            <p className="hidden shrink-0 font-mono lg:block">
              {m.search_shortcut()}
            </p>
          </div>

          {recent.length > 0 ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-left">
              <span className="text-[0.68rem] font-semibold tracking-[0.12em] text-muted-foreground uppercase">
                {m.recent_searches()}
              </span>
              {recent.map((item) => (
                <button
                  key={item}
                  type="button"
                  className="min-h-8 rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground transition-colors hover:bg-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => {
                    submitQuery(item)
                  }}
                >
                  {item}
                </button>
              ))}
              <button
                type="button"
                className="ml-1 min-h-8 rounded-full px-2 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
                onClick={clearRecent}
              >
                {m.clear_recent()}
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </form>
  )
}
