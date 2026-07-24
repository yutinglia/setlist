import { Outlet, createRootRoute } from "@tanstack/react-router"

import { SiteHeader } from "@/components/site-header"
import { m } from "@/paraglide/messages"

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pb-16 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-3xl px-4 pb-8 text-center text-xs text-muted-foreground sm:px-6">
        {m.footer_note()}
      </footer>
    </div>
  )
}
