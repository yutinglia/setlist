import { useNavigate, useRouterState } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { type FormEvent, useEffect, useRef, useState } from "react"

import { m } from "@/paraglide/messages"

export function GlobalSearch() {
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const searchStr = useRouterState({
    select: (state) => state.location.searchStr,
  })
  const [value, setValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (pathname !== "/search") return
    setValue(new URLSearchParams(searchStr).get("q") ?? "")
  }, [pathname, searchStr])

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const isEditing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable
      if (
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
  }, [])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const q = value.trim()
    if (!q) {
      inputRef.current?.focus()
      return
    }
    setValue(q)
    void navigate({ to: "/search", search: { q } })
  }

  return (
    <form
      role="search"
      aria-label={m.nav_search()}
      className="hidden w-full max-w-2xl items-stretch md:flex"
      onSubmit={submit}
    >
      <label htmlFor="global-search" className="sr-only">
        {m.search_placeholder()}
      </label>
      <input
        ref={inputRef}
        id="global-search"
        type="search"
        value={value}
        maxLength={200}
        placeholder={m.search_placeholder()}
        className="h-10 min-w-0 flex-1 rounded-l-full border border-r-0 border-input bg-background px-4 text-base outline-none transition-[border-color,box-shadow,background-color] placeholder:text-muted-foreground focus:border-ring focus:bg-card focus:ring-2 focus:ring-ring/20 lg:pl-5"
        onChange={(event) => setValue(event.target.value)}
      />
      <button
        type="submit"
        className="grid h-10 w-14 shrink-0 place-items-center rounded-r-full border border-input bg-secondary text-secondary-foreground transition-colors hover:bg-muted focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={m.search_submit()}
      >
        <Search className="size-5" aria-hidden />
      </button>
    </form>
  )
}
