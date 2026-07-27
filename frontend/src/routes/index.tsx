import { createFileRoute } from "@tanstack/react-router"
import { ArrowRight, Search } from "lucide-react"
import { useState } from "react"

import { PageMetadata } from "@/components/page-metadata"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/")({
  component: HomePage,
})

function HomePage() {
  const navigate = Route.useNavigate()
  const [query, setQuery] = useState("")

  function submit() {
    const q = query.trim()
    if (!q) return
    void navigate({
      to: "/search",
      search: { q },
    })
  }

  return (
    <section className="grid min-h-[min(760px,78svh)] flex-1 place-items-center py-14 sm:py-20">
      <PageMetadata
        path="/"
        title={m.meta_default_title()}
        description={m.home_intro()}
      />
      <div className="animate-rise w-full max-w-4xl text-center">
        <h1 className="font-display text-[clamp(2.5rem,7vw,5.6rem)] leading-[0.96] font-bold tracking-[-0.05em]">
          {m.home_headline()}
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          {m.home_intro()}
        </p>

        <form
          className="mx-auto mt-9 flex max-w-3xl gap-2.5 text-left"
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
        >
          <div className="relative min-w-0 flex-1">
            <Search
              className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-primary sm:left-5 sm:size-6"
              aria-hidden
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={m.search_placeholder()}
              aria-label={m.search_placeholder()}
              maxLength={200}
              autoFocus
              className="h-16 rounded-2xl border-border bg-card pr-4 pl-12 text-base shadow-[0_28px_80px_-38px_rgba(55,40,150,0.7)] sm:h-18 sm:pl-15 sm:text-lg"
            />
          </div>
          <Button
            type="submit"
            size="lg"
            className="h-16 rounded-2xl px-5 sm:h-18 sm:px-8"
            disabled={!query.trim()}
            aria-label={m.search_submit()}
          >
            <span className="hidden sm:inline">{m.search_submit()}</span>
            <ArrowRight aria-hidden />
          </Button>
        </form>
      </div>
    </section>
  )
}
