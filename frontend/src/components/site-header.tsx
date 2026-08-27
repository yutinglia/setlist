import { Link, useNavigate, useRouterState } from "@tanstack/react-router"
import {
  Check,
  ChevronDown,
  Languages,
  LogIn,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react"
import { Dialog, DropdownMenu } from "radix-ui"
import { useEffect, useState } from "react"

import { useAuthSession, useHealth, useLogout } from "@/api/hooks"
import { BrandLogo } from "@/components/brand-logo"
import { GlobalSearch } from "@/components/global-search"
import {
  DesktopNavigation,
  MobileNavigationContent,
} from "@/components/site-navigation"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"
import { getLocale } from "@/paraglide/runtime"
import { useUiStore } from "@/stores/ui-store"

export function SiteHeader() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const isHome = pathname === "/"
  const showHeaderSearch = !isHome && pathname !== "/search"
  const theme = useUiStore((state) => state.theme)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
  }, [theme])

  return (
    <header className="sticky top-0 z-40 h-16 border-b border-border/85 bg-background/92 backdrop-blur-xl lg:h-[4.5rem]">
      <div className="mx-auto flex h-full w-full max-w-[90rem] items-center gap-2 px-3 sm:px-6 lg:gap-3 lg:px-8">
        <Dialog.Root open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <Dialog.Trigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              className="size-11 rounded-xl lg:hidden"
              aria-label={m.nav_open_menu()}
            >
              <Menu aria-hidden />
            </Button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[2px] data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out data-[state=open]:fade-in" />
            <Dialog.Content className="fixed inset-y-0 left-0 z-[60] flex w-[min(22rem,90vw)] flex-col border-r border-border bg-background shadow-2xl outline-none data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-border px-4">
                <Dialog.Title className="sr-only">{m.nav_menu()}</Dialog.Title>
                <BrandLogo onNavigate={() => setMobileMenuOpen(false)} />
                <Dialog.Close asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-lg"
                    className="size-11 rounded-xl"
                    aria-label={m.nav_close_menu()}
                  >
                    <X aria-hidden />
                  </Button>
                </Dialog.Close>
              </div>
              <div className="scrollbar-none flex-1 overflow-y-auto px-3 py-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
                <MobileNavigationContent
                  onNavigate={() => setMobileMenuOpen(false)}
                />
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        <BrandLogo className="mr-1 shrink-0" />
        <DesktopNavigation />

        {showHeaderSearch ? (
          <div className="mx-auto hidden min-w-52 max-w-md flex-1 justify-center xl:flex">
            <GlobalSearch />
          </div>
        ) : (
          <div className="hidden flex-1 xl:block" aria-hidden />
        )}

        <div className="ml-auto flex shrink-0 items-center gap-1 lg:ml-0">
          {showHeaderSearch ? (
            <Button
              asChild
              variant="ghost"
              size="icon-lg"
              className="hidden size-11 rounded-xl sm:inline-flex lg:hidden"
            >
              <Link
                to="/search"
                aria-label={m.nav_search()}
                title={m.nav_search()}
              >
                <Search aria-hidden />
              </Link>
            </Button>
          ) : null}
          <PreferencesMenu />
        </div>
      </div>
    </header>
  )
}

function PreferencesMenu() {
  const locale = useUiStore((state) => state.locale)
  const theme = useUiStore((state) => state.theme)
  const setLocalePref = useUiStore((state) => state.setLocalePref)
  const toggleTheme = useUiStore((state) => state.toggleTheme)
  const auth = useAuthSession()
  const health = useHealth()
  const logout = useLogout()
  const navigate = useNavigate()
  const current = locale || getLocale()
  const isAdmin =
    auth.data?.authenticated === true && auth.data.role === "admin"
  const apiLabel = health.isLoading
    ? m.api_checking()
    : health.isSuccess
      ? m.api_ok()
      : m.api_down()

  useEffect(() => {
    document.documentElement.lang = current
  }, [current])

  function setLanguage(next: string) {
    if (next === "en" || next === "zh-hant" || next === "ja") {
      setLocalePref(next)
    }
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          type="button"
          variant="ghost"
          className={cn(
            "size-11 rounded-full p-0 sm:h-11 sm:w-auto sm:rounded-xl sm:px-3",
            isAdmin &&
              "bg-primary text-primary-foreground hover:bg-primary/90 sm:bg-secondary sm:text-secondary-foreground sm:hover:bg-muted",
          )}
          aria-label={m.nav_more()}
          title={m.nav_more()}
        >
          {isAdmin ? (
            <span className="grid place-items-center text-sm leading-none font-bold sm:size-7 sm:rounded-full sm:bg-primary sm:text-xs sm:text-primary-foreground">
              {(auth.data?.username ?? "A").slice(0, 1).toUpperCase()}
            </span>
          ) : (
            <Settings2 className="size-5" aria-hidden />
          )}
          <ChevronDown className="hidden size-3.5 text-muted-foreground sm:block" aria-hidden />
        </Button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-[70] min-w-68 rounded-2xl border border-border bg-popover p-2 text-popover-foreground shadow-xl outline-none data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out data-[state=open]:fade-in data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
        >
          <div className="px-2 py-2">
            {isAdmin ? (
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                  {(auth.data?.username ?? "A").slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">
                    {auth.data?.username ?? m.auth_admin()}
                  </p>
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <ShieldCheck className="size-3.5" aria-hidden />
                    {m.auth_admin()}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {m.nav_preferences()}
              </p>
            )}
          </div>

          <DropdownMenu.Separator className="my-1 h-px bg-border" />

          <DropdownMenu.Item
            className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-3 text-sm outline-none select-none data-[highlighted]:bg-secondary"
            onSelect={toggleTheme}
          >
            {theme === "dark" ? (
              <Sun className="size-4.5" aria-hidden />
            ) : (
              <Moon className="size-4.5" aria-hidden />
            )}
            {theme === "dark" ? m.theme_switch_light() : m.theme_switch_dark()}
          </DropdownMenu.Item>

          <DropdownMenu.Sub>
            <DropdownMenu.SubTrigger className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-3 text-sm outline-none select-none data-[highlighted]:bg-secondary data-[state=open]:bg-secondary">
              <Languages className="size-4.5" aria-hidden />
              <span className="flex-1">{m.locale_label()}</span>
              <ChevronDown className="size-3.5 -rotate-90 text-muted-foreground" aria-hidden />
            </DropdownMenu.SubTrigger>
            <DropdownMenu.Portal>
              <DropdownMenu.SubContent
                sideOffset={8}
                alignOffset={-4}
                className="z-[80] min-w-40 rounded-xl border border-border bg-popover p-1.5 text-popover-foreground shadow-xl outline-none data-[state=closed]:animate-out data-[state=open]:animate-in data-[state=closed]:fade-out data-[state=open]:fade-in"
              >
                <DropdownMenu.RadioGroup value={current} onValueChange={setLanguage}>
                  {(
                    [
                      ["en", m.locale_en()],
                      ["zh-hant", m.locale_zh()],
                      ["ja", m.locale_ja()],
                    ] as const
                  ).map(([value, label]) => (
                    <DropdownMenu.RadioItem
                      key={value}
                      value={value}
                      className="flex min-h-11 cursor-pointer items-center gap-2 rounded-xl px-3 text-sm outline-none select-none data-[highlighted]:bg-secondary"
                    >
                      <span className="grid size-4 place-items-center">
                        {current === value ? (
                          <Check className="size-3.5 text-primary" aria-hidden />
                        ) : null}
                      </span>
                      {label}
                    </DropdownMenu.RadioItem>
                  ))}
                </DropdownMenu.RadioGroup>
              </DropdownMenu.SubContent>
            </DropdownMenu.Portal>
          </DropdownMenu.Sub>

          <DropdownMenu.Separator className="my-1 h-px bg-border" />

          {isAdmin ? (
            <DropdownMenu.Item
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-3 text-sm text-destructive outline-none select-none data-[highlighted]:bg-destructive/10"
              disabled={logout.isPending}
              aria-label={m.auth_sign_out()}
              onSelect={() =>
                logout.mutate(undefined, {
                  onSuccess: () => void navigate({ to: "/" }),
                })
              }
            >
              <LogOut className="size-4.5" aria-hidden />
              {m.auth_sign_out()}
            </DropdownMenu.Item>
          ) : (
            <DropdownMenu.Item asChild>
              <Link
                to="/admin/login"
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-3 text-sm outline-none select-none data-[highlighted]:bg-secondary"
              >
                <LogIn className="size-4.5" aria-hidden />
                {m.auth_sign_in()}
              </Link>
            </DropdownMenu.Item>
          )}

          <div className="mt-1 flex min-h-11 items-center gap-2.5 rounded-xl bg-secondary/70 px-3 py-2 text-xs font-medium text-muted-foreground">
            <span
              className={cn(
                "size-2 rounded-full",
                health.isSuccess
                  ? "bg-success"
                  : health.isLoading
                    ? "bg-muted-foreground"
                    : "bg-destructive",
              )}
              aria-hidden
            />
            {apiLabel}
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
