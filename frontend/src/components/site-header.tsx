import { Link } from "@tanstack/react-router"
import { useEffect } from "react"

import { useHealth } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"
import { getLocale } from "@/paraglide/runtime"
import { useUiStore } from "@/stores/ui-store"

export function SiteHeader() {
  const locale = useUiStore((s) => s.locale)
  const setLocalePref = useUiStore((s) => s.setLocalePref)
  const health = useHealth()
  const current = locale || getLocale()

  useEffect(() => {
    document.documentElement.lang = current
  }, [current])

  const apiLabel = health.isLoading
    ? m.api_checking()
    : health.isSuccess
      ? m.api_ok()
      : m.api_down()

  return (
    <header className="animate-fade mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 pt-6 sm:flex-nowrap sm:px-6">
      <nav className="order-2 flex w-full items-center justify-center gap-1 text-sm sm:order-1 sm:w-auto sm:justify-start">
        <Link
          to="/"
          activeOptions={{ exact: true }}
          className="rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground"
        >
          {m.nav_search()}
        </Link>
        <Link
          to="/channels"
          className="rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground"
        >
          {m.nav_channels()}
        </Link>
        <Link
          to="/status"
          className="rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground"
        >
          {m.nav_status()}
        </Link>
        <Link
          to="/summary"
          className="rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground"
        >
          {m.nav_summary()}
        </Link>
      </nav>

      <div className="order-1 ml-auto flex items-center gap-2 sm:order-2">
        <span
          className={cn(
            "hidden items-center gap-1.5 text-xs sm:inline-flex",
            health.isSuccess ? "text-primary" : "text-muted-foreground",
          )}
          title={apiLabel}
        >
          <span
            className={cn(
              "size-1.5 rounded-full",
              health.isSuccess
                ? "animate-soft-pulse bg-primary"
                : health.isLoading
                  ? "bg-muted-foreground/50"
                  : "bg-destructive",
            )}
          />
          {apiLabel}
        </span>
        <div
          className="inline-flex rounded-md border border-border bg-card/70 p-0.5"
          role="group"
          aria-label={m.locale_label()}
        >
          <Button
            type="button"
            size="xs"
            variant={current === "en" ? "secondary" : "ghost"}
            onClick={() => setLocalePref("en")}
          >
            {m.locale_en()}
          </Button>
          <Button
            type="button"
            size="xs"
            variant={current === "zh-hant" ? "secondary" : "ghost"}
            onClick={() => setLocalePref("zh-hant")}
          >
            {m.locale_zh()}
          </Button>
        </div>
      </div>
    </header>
  )
}
