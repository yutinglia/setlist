import { useNavigate, useRouterState } from "@tanstack/react-router"

import { SearchForm } from "@/components/search-form"
import { m } from "@/paraglide/messages"

export function GlobalSearch() {
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const searchStr = useRouterState({
    select: (state) => state.location.searchStr,
  })
  const query =
    pathname === "/search"
      ? (new URLSearchParams(searchStr).get("q") ?? "")
      : ""

  function submit(q: string) {
    if (!q) return
    void navigate({ to: "/search", search: { q } })
  }

  return (
    <div className="w-full max-w-2xl">
      <SearchForm
        initialQuery={query}
        onQuerySubmit={submit}
        variant="compact"
        shortcutEnabled={pathname !== "/search"}
        inputAriaLabel={m.nav_search()}
      />
    </div>
  )
}
