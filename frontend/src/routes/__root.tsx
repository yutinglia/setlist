import { Outlet, createRootRoute } from "@tanstack/react-router"

import { SiteHeader } from "@/components/site-header"
import { m } from "@/paraglide/messages"

export const Route = createRootRoute({
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
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-4 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>{m.footer_note()}</p>
          <p className="font-mono text-[0.65rem] tracking-[0.18em] uppercase">
            {m.brand_full()}
          </p>
        </div>
      </footer>
    </div>
  )
}
