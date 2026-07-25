import { Search } from "lucide-react"
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
      <div className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={m.search_placeholder()}
            maxLength={200}
            className="h-12 border-border/80 bg-card/80 pl-10 text-base shadow-none backdrop-blur-sm"
            autoFocus={autoFocus}
            aria-label={m.search_placeholder()}
          />
        </div>
        <Button type="submit" className="h-12 px-5" size="lg">
          {m.search_submit()}
        </Button>
      </div>
      <p className="mt-2 text-left text-xs text-muted-foreground">
        {m.search_hint()}
      </p>

      {recent.length > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-left">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {m.recent_searches()}
          </span>
          {recent.map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-md bg-secondary/80 px-2.5 py-1 text-xs text-secondary-foreground transition-colors hover:bg-secondary"
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
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={clearRecent}
          >
            {m.clear_recent()}
          </button>
        </div>
      ) : null}
    </form>
  )
}
