import { ArrowRight, Search, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { m } from "@/paraglide/messages"
import { useUiStore } from "@/stores/ui-store"

type Props = {
  initialQuery?: string
  onQueryChange: (q: string) => void
  autoFocus?: boolean
}

export function SearchForm({
  initialQuery = "",
  onQueryChange,
  autoFocus,
}: Props) {
  const [value, setValue] = useState(initialQuery)
  const debounced = useDebouncedValue(value, 350)
  const inputRef = useRef<HTMLInputElement>(null)
  const recent = useUiStore((s) => s.recentSearches)
  const addRecent = useUiStore((s) => s.addRecentSearch)
  const clearRecent = useUiStore((s) => s.clearRecentSearches)
  const onQueryChangeRef = useRef(onQueryChange)
  const initialQueryRef = useRef(initialQuery)

  onQueryChangeRef.current = onQueryChange
  initialQueryRef.current = initialQuery

  useEffect(() => {
    setValue(initialQuery)
  }, [initialQuery])

  useEffect(() => {
    const next = debounced.trim()
    // Depending on the callback identity here creates a back/forward race:
    // the old debounced value can overwrite a newly restored URL query.
    if (next !== initialQueryRef.current.trim()) {
      onQueryChangeRef.current(next)
    }
  }, [debounced])

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

  return (
    <form
      className="w-full"
      onSubmit={(e) => {
        e.preventDefault()
        const q = value.trim()
        onQueryChange(q)
        if (q) addRecent(q)
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
            onChange={(e) => setValue(e.target.value)}
            placeholder={m.search_placeholder()}
            maxLength={200}
            className="h-14 rounded-xl border-border/80 bg-card pr-20 pl-12 text-base shadow-[0_18px_50px_-34px_rgba(40,30,100,0.6)]"
            autoFocus={autoFocus}
            aria-label={m.search_placeholder()}
          />
          {value ? (
            <button
              type="button"
              className="absolute top-1/2 right-3 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              aria-label={m.search_clear()}
              onClick={() => {
                setValue("")
                onQueryChange("")
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
                setValue(item)
                onQueryChange(item)
                addRecent(item)
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
