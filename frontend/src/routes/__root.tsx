import type { QueryClient } from "@tanstack/react-query"
import {
  Link,
  Outlet,
  createRootRouteWithContext,
} from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"

import { BrandLogo } from "@/components/brand-logo"
import {
  DesktopSidebar,
  MobileBottomNavigation,
} from "@/components/site-navigation"
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
    <div className="flex min-h-svh flex-col">
      <a
        href="#main-content"
        className="fixed top-3 left-3 z-[90] -translate-y-20 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-lg transition-transform focus:translate-y-0"
      >
        {m.skip_to_content()}
      </a>
      <SiteHeader />
      <div className="flex min-w-0 flex-1 items-start">
        <DesktopSidebar />
        <div className="flex min-h-[calc(100svh-4rem)] min-w-0 flex-1 flex-col">
          <main
            id="main-content"
            className="mx-auto flex w-full max-w-[96rem] flex-1 flex-col px-4 pb-24 sm:px-6 lg:px-8 lg:pb-16"
          >
            <Outlet />
          </main>
          <SiteFooter />
        </div>
      </div>
      <MobileBottomNavigation />
    </div>
  )
}

function SiteFooter() {
  return (
    <footer className="border-t border-border bg-card pb-20 lg:pb-0">
      <div className="mx-auto grid w-full max-w-[96rem] gap-8 px-4 py-8 text-sm text-muted-foreground sm:px-6 md:grid-cols-[minmax(13rem,1fr)_auto] lg:px-8">
        <div className="max-w-md">
          <BrandLogo />
          <p className="mt-4 text-xs leading-5">{m.footer_note()}</p>
          <p
            className="mt-2 text-[0.68rem] font-medium tracking-wide"
            aria-label={m.footer_version({ version: __APP_VERSION__ })}
          >
            v{__APP_VERSION__}
          </p>
        </div>
        <div className="flex flex-col gap-5 md:items-end">
          <nav
            className="flex max-w-xl flex-wrap gap-x-5 gap-y-3 text-xs"
            aria-label={m.footer_info_nav()}
          >
            <Link to="/how-to-use" className="hover:text-foreground">
              {m.nav_how_to_use()}
            </Link>
            <Link to="/about" className="hover:text-foreground">
              {m.nav_about()}
            </Link>
            <Link to="/thanks" className="hover:text-foreground">
              {m.nav_thanks()}
            </Link>
            <Link to="/terms" className="hover:text-foreground">
              {m.nav_terms()}
            </Link>
            <Link to="/privacy" className="hover:text-foreground">
              {m.nav_privacy()}
            </Link>
            <Link to="/copyright" className="hover:text-foreground">
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
    <section className="mx-auto grid min-h-[70svh] max-w-xl place-content-center py-20 text-center">
      <p className="text-sm font-semibold tracking-[0.16em] text-primary uppercase">
        {m.not_found_eyebrow()}
      </p>
      <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
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
