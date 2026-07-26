import type { QueryClient } from "@tanstack/react-query"
import {
  Link,
  Outlet,
  createRootRouteWithContext,
} from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"

import { SiteHeader } from "@/components/site-header"
import { buttonVariants } from "@/components/ui/button"
import { SOURCE_URL } from "@/lib/public-config"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
}>()({
  component: RootLayout,
})

function RootLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main-content"
        className="fixed top-3 left-3 z-[100] -translate-y-20 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lg transition-transform focus:translate-y-0"
      >
        {m.skip_to_content()}
      </a>
      <SiteHeader />
      <main
        id="main-content"
        className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-4 pb-20 sm:px-6 lg:px-8"
      >
        <Outlet />
      </main>
      <footer className="border-t border-border/60 bg-card/30">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-8 text-xs text-muted-foreground sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div>
            <p>{m.footer_note()}</p>
            <p className="mt-1 font-mono text-[0.65rem] tracking-[0.18em] uppercase">
              {m.brand_full()}
            </p>
          </div>
          <nav
            className="flex flex-wrap items-center gap-x-5 gap-y-2"
            aria-label={m.footer_info_nav()}
          >
            <Link to="/how-to-use" className="hover:text-primary">
              {m.nav_how_to_use()}
            </Link>
            <Link to="/about" className="hover:text-primary">
              {m.nav_about()}
            </Link>
            <Link to="/terms" className="hover:text-primary">
              {m.nav_terms()}
            </Link>
            <Link to="/privacy" className="hover:text-primary">
              {m.nav_privacy()}
            </Link>
            <Link to="/copyright" className="hover:text-primary">
              {m.nav_copyright()}
            </Link>
            <span
              className="font-mono text-[0.65rem] tracking-[0.12em]"
              aria-label={m.footer_version({ version: __APP_VERSION__ })}
              title={m.footer_version({ version: __APP_VERSION__ })}
            >
              v{__APP_VERSION__}
            </span>
            <a
              href={SOURCE_URL}
              target="_blank"
              rel="noreferrer"
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "h-7 rounded-md px-2.5 text-xs"
              )}
            >
              <ExternalLink aria-hidden />
              {m.footer_github()}
            </a>
          </nav>
        </div>
      </footer>
    </div>
  )
}
