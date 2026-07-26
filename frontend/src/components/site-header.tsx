import { Link, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"
import {
  Activity,
  BarChart3,
  BookOpen,
  Disc3,
  Languages,
  LogIn,
  LogOut,
  Moon,
  Radio,
  Search,
  ShieldCheck,
  Sun,
} from "lucide-react"

import { useAuthSession, useHealth, useLogout } from "@/api/hooks"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"
import { getLocale } from "@/paraglide/runtime"
import { useUiStore } from "@/stores/ui-store"

export function SiteHeader() {
  const locale = useUiStore((s) => s.locale)
  const theme = useUiStore((s) => s.theme)
  const setLocalePref = useUiStore((s) => s.setLocalePref)
  const toggleTheme = useUiStore((s) => s.toggleTheme)
  const health = useHealth()
  const auth = useAuthSession()
  const logout = useLogout()
  const navigate = useNavigate()
  const current = locale || getLocale()
  const isAdmin =
    auth.data?.authenticated === true && auth.data.role === "admin"

  useEffect(() => {
    document.documentElement.lang = current
  }, [current])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
  }, [theme])

  const apiLabel = health.isLoading
    ? m.api_checking()
    : health.isSuccess
      ? m.api_ok()
      : m.api_down()

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex min-h-16 w-full max-w-7xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2 sm:px-6 lg:flex-nowrap lg:px-8">
        <Link
          to="/"
          className="group flex shrink-0 items-center gap-2.5"
          aria-label={m.brand_name()}
        >
          <span className="brand-mark">
            <Disc3 className="size-4" aria-hidden />
          </span>
          <span className="hidden sm:block">
            <span className="block font-display text-sm leading-none font-bold tracking-tight">
              {m.brand_name()}
            </span>
            <span className="mt-1 block font-mono text-[0.55rem] leading-none tracking-[0.16em] text-muted-foreground uppercase">
              karaoke index
            </span>
          </span>
        </Link>

        <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto text-sm lg:order-2 lg:w-auto">
          <NavLink to="/" label={m.nav_search()} icon={Search} exact />
          <NavLink to="/channels" label={m.nav_channels()} icon={Radio} />
          <NavLink to="/summary" label={m.nav_summary()} icon={BarChart3} />
          <NavLink
            to="/how-to-use"
            label={m.nav_how_to_use()}
            icon={BookOpen}
          />
          {isAdmin ? (
            <NavLink to="/status" label={m.nav_status()} icon={Activity} />
          ) : null}
        </nav>

        <div className="order-2 ml-auto flex items-center gap-1.5 lg:order-3">
          {isAdmin ? (
            <>
              <span className="hidden items-center gap-1.5 rounded-full border border-primary/20 bg-primary/8 px-2.5 py-1 text-[0.68rem] font-semibold text-primary sm:inline-flex">
                <ShieldCheck className="size-3.5" aria-hidden />
                {auth.data?.username ?? m.auth_admin()}
              </span>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={() =>
                  logout.mutate(undefined, {
                    onSuccess: () => {
                      void navigate({ to: "/" })
                    },
                  })
                }
                disabled={logout.isPending}
                aria-label={m.auth_sign_out()}
                title={m.auth_sign_out()}
              >
                <LogOut aria-hidden />
              </Button>
            </>
          ) : (
            <Button asChild size="sm" variant="ghost">
              <Link to="/admin/login">
                <LogIn aria-hidden />
                <span className="hidden sm:inline">{m.auth_sign_in()}</span>
              </Link>
            </Button>
          )}

          <span
            className={cn(
              "mr-1 hidden items-center gap-2 rounded-full border border-border/70 bg-card/70 px-2.5 py-1.5 text-[0.7rem] xl:inline-flex",
              health.isSuccess ? "text-foreground" : "text-muted-foreground",
            )}
            title={apiLabel}
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                health.isSuccess
                  ? "animate-soft-pulse bg-emerald-500"
                  : health.isLoading
                    ? "bg-muted-foreground/50"
                    : "bg-destructive",
              )}
            />
            {apiLabel}
          </span>

          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={toggleTheme}
            aria-label={
              theme === "dark" ? m.theme_switch_light() : m.theme_switch_dark()
            }
            title={
              theme === "dark" ? m.theme_switch_light() : m.theme_switch_dark()
            }
          >
            {theme === "dark" ? <Sun aria-hidden /> : <Moon aria-hidden />}
          </Button>

          <div
            className="flex items-center rounded-lg border border-border/70 bg-card/70 p-0.5"
            role="group"
            aria-label={m.locale_label()}
          >
            <Languages
              className="mx-1 hidden size-3.5 text-muted-foreground sm:block"
              aria-hidden
            />
            <Button
              type="button"
              size="xs"
              variant={current === "en" ? "secondary" : "ghost"}
              onClick={() => setLocalePref("en")}
              aria-pressed={current === "en"}
            >
              {m.locale_en()}
            </Button>
            <Button
              type="button"
              size="xs"
              variant={current === "zh-hant" ? "secondary" : "ghost"}
              onClick={() => setLocalePref("zh-hant")}
              aria-pressed={current === "zh-hant"}
            >
              {m.locale_zh()}
            </Button>
            <Button
              type="button"
              size="xs"
              variant={current === "ja" ? "secondary" : "ghost"}
              onClick={() => setLocalePref("ja")}
              aria-pressed={current === "ja"}
            >
              {m.locale_ja()}
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}

function NavLink({
  to,
  label,
  icon: Icon,
  exact = false,
}: {
  to: "/" | "/channels" | "/summary" | "/how-to-use" | "/status"
  label: string
  icon: typeof Search
  exact?: boolean
}) {
  return (
    <Link
      to={to}
      activeOptions={{ exact }}
      className="inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-muted-foreground transition-colors hover:bg-secondary/70 hover:text-foreground data-[status=active]:bg-primary/10 data-[status=active]:font-medium data-[status=active]:text-primary"
    >
      <Icon className="size-3.5" aria-hidden />
      {label}
    </Link>
  )
}
