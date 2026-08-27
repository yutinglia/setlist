import type { QueryClient } from "@tanstack/react-query"
import {
  Link,
  Outlet,
  createRootRouteWithContext,
} from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"

import { BrandLogo } from "@/components/brand-logo"
import { MobileBottomNavigation } from "@/components/site-navigation"
import { SiteHeader } from "@/components/site-header"
import type { ApiClient } from "@/api/client"
import { buttonVariants } from "@/components/ui/button"
import { SOURCE_URL } from "@/lib/public-config"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
  api: ApiClient
}>()({
  component: RootLayout,
  notFoundComponent: NotFoundPage,
})

function RootLayout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main-content"
        className="fixed top-3 left-3 z-[90] inline-flex min-h-11 -translate-y-20 items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lg transition-transform focus:translate-y-0"
      >
        {m.skip_to_content()}
      </a>
      <SiteHeader />
      <main
        id="main-content"
        className="mx-auto flex min-h-[calc(100dvh-4rem)] w-full max-w-[90rem] flex-1 flex-col px-4 pb-28 sm:px-6 lg:min-h-[calc(100dvh-4.5rem)] lg:px-8 lg:pb-18"
      >
        <Outlet />
      </main>
      <SiteFooter />
      <MobileBottomNavigation />
    </div>
  )
}

function SiteFooter() {
  return (
    <footer className="border-t border-border/80 bg-card/70 pb-22 backdrop-blur-sm lg:pb-0">
      <div className="mx-auto grid w-full max-w-[90rem] gap-8 px-4 py-10 text-sm text-muted-foreground sm:px-6 md:grid-cols-[minmax(13rem,1fr)_auto] lg:px-8 lg:py-12">
        <div className="max-w-md">
          <BrandLogo />
          <p className="mt-4 text-sm leading-6">{m.footer_note()}</p>
          <p
            className="mt-2 text-[0.68rem] font-medium tracking-wide"
            aria-label={m.footer_version({ version: __APP_VERSION__ })}
          >
            v{__APP_VERSION__}
          </p>
        </div>
        <div className="flex flex-col gap-5 md:items-end">
          <nav
            className="flex max-w-xl flex-wrap gap-x-2 gap-y-1 text-sm"
            aria-label={m.footer_info_nav()}
          >
            <Link to="/how-to-use" className="inline-flex min-h-11 items-center rounded-lg px-2 hover:bg-secondary hover:text-foreground">
              {m.nav_how_to_use()}
            </Link>
            <Link to="/about" className="inline-flex min-h-11 items-center rounded-lg px-2 hover:bg-secondary hover:text-foreground">
              {m.nav_about()}
            </Link>
            <Link to="/thanks" className="inline-flex min-h-11 items-center rounded-lg px-2 hover:bg-secondary hover:text-foreground">
              {m.nav_thanks()}
            </Link>
            <Link to="/terms" className="inline-flex min-h-11 items-center rounded-lg px-2 hover:bg-secondary hover:text-foreground">
              {m.nav_terms()}
            </Link>
            <Link to="/privacy" className="inline-flex min-h-11 items-center rounded-lg px-2 hover:bg-secondary hover:text-foreground">
              {m.nav_privacy()}
            </Link>
            <Link to="/copyright" className="inline-flex min-h-11 items-center rounded-lg px-2 hover:bg-secondary hover:text-foreground">
              {m.nav_copyright()}
            </Link>
          </nav>
          <a
            href={SOURCE_URL}
            target="_blank"
            rel="noreferrer"
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "w-fit",
            )}
          >
            <ExternalLink aria-hidden />
            {m.footer_github()}
          </a>
        </div>
      </div>
    </footer>
  )
}

function NotFoundPage() {
  return (
    <section className="mx-auto grid min-h-[70dvh] max-w-xl place-content-center py-20 text-center">
      <p className="text-sm font-semibold tracking-[0.16em] text-primary uppercase">
        {m.not_found_eyebrow()}
      </p>
      <h1 className="mt-3 text-4xl font-bold tracking-[-0.04em] sm:text-6xl">
        {m.not_found_heading()}
      </h1>
      <p className="mt-4 leading-relaxed text-muted-foreground">
        {m.not_found_body()}
      </p>
      <div className="mt-8">
        <Link to="/" className={buttonVariants()}>
          {m.not_found_home()}
        </Link>
      </div>
    </section>
  )
}
