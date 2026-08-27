import { Link, useRouterState } from "@tanstack/react-router"
import {
  Activity,
  BarChart3,
  BookOpen,
  CirclePlus,
  Clock3,
  HeartHandshake,
  Home,
  Info,
  Radio,
  Search,
  type LucideIcon,
} from "lucide-react"

import { useAuthSession, useHealth } from "@/api/hooks"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

type NavigationPath =
  | "/"
  | "/search"
  | "/channels"
  | "/channels/new"
  | "/updates"
  | "/summary"
  | "/thanks"
  | "/how-to-use"
  | "/about"
  | "/status"

type NavigationItem = {
  to: NavigationPath
  label: string
  icon: LucideIcon
  exact?: boolean
  private?: boolean
}

function primaryItems(): NavigationItem[] {
  return [
    { to: "/", label: m.nav_home(), icon: Home, exact: true },
    { to: "/search", label: m.nav_search(), icon: Search },
    { to: "/channels", label: m.nav_channels(), icon: Radio },
    { to: "/updates", label: m.nav_recent(), icon: Clock3 },
  ]
}

function libraryItems(): NavigationItem[] {
  return [{ to: "/summary", label: m.nav_summary(), icon: BarChart3 }]
}

function informationItems(): NavigationItem[] {
  return [
    { to: "/how-to-use", label: m.nav_how_to_use(), icon: BookOpen },
    { to: "/thanks", label: m.nav_thanks(), icon: HeartHandshake },
    { to: "/about", label: m.nav_about(), icon: Info },
  ]
}

function useAdminNavigation() {
  const auth = useAuthSession()
  const isAdmin =
    auth.data?.authenticated === true && auth.data.role === "admin"
  const canManage = isAdmin && auth.data?.management_enabled === true
  const items: NavigationItem[] = []

  if (isAdmin) {
    items.push({
      to: "/status",
      label: m.nav_status(),
      icon: Activity,
      private: true,
    })
  }
  if (canManage) {
    items.push({
      to: "/channels/new",
      label: m.channel_add_cta(),
      icon: CirclePlus,
      exact: true,
      private: true,
    })
  }

  return { items, isAdmin }
}

function pathIsActive(pathname: string, item: NavigationItem): boolean {
  if (item.exact || item.to === "/") return pathname === item.to
  if (item.to === "/channels") {
    return (
      pathname === "/channels" ||
      (pathname.startsWith("/channels/") && pathname !== "/channels/new")
    )
  }
  return pathname === item.to || pathname.startsWith(`${item.to}/`)
}

function usePathname() {
  return useRouterState({
    select: (state) => state.location.pathname,
  })
}

export function DesktopNavigation() {
  const pathname = usePathname()
  const { items: adminItems } = useAdminNavigation()
  const items = [...primaryItems(), ...libraryItems(), ...adminItems]
  const hasAdminItems = adminItems.length > 0

  return (
    <nav
      className="hidden min-w-0 shrink-0 items-center gap-1 lg:ml-auto lg:flex xl:ml-0"
      aria-label={m.nav_menu()}
    >
      {items.map((item) => {
        const active = pathIsActive(pathname, item)
        const Icon = item.icon
        return (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "relative inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold text-muted-foreground outline-none transition-colors duration-200 hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
              active && "bg-secondary text-foreground",
              item.private && "text-accent-foreground dark:text-accent-foreground",
            )}
            aria-current={active ? "page" : undefined}
            aria-label={item.label}
            title={item.label}
          >
            <Icon
              className={cn("size-4.5 shrink-0", active && "text-primary")}
              strokeWidth={active ? 2.35 : 1.9}
              aria-hidden
            />
            <span
              className={cn(
                "hidden",
                hasAdminItems && !item.private ? "2xl:inline" : "xl:inline",
              )}
            >
              {item.label}
            </span>
            {active ? (
              <span
                className="absolute right-3 bottom-0 left-3 h-0.5 rounded-full bg-primary"
                aria-hidden
              />
            ) : null}
          </Link>
        )
      })}
    </nav>
  )
}

function MobileNavigationLink({
  item,
  onNavigate,
}: {
  item: NavigationItem
  onNavigate: () => void
}) {
  const pathname = usePathname()
  const active = pathIsActive(pathname, item)
  const Icon = item.icon

  return (
    <Link
      to={item.to}
      className={cn(
        "relative flex min-h-12 items-center gap-3 rounded-xl px-3 text-sm font-semibold text-muted-foreground outline-none transition-colors duration-200 hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
        active && "bg-secondary text-foreground",
      )}
      aria-current={active ? "page" : undefined}
      onClick={onNavigate}
    >
      <span
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-lg bg-muted",
          active && "bg-primary text-primary-foreground",
        )}
      >
        <Icon className="size-4" strokeWidth={active ? 2.35 : 1.9} aria-hidden />
      </span>
      <span className="truncate">{item.label}</span>
    </Link>
  )
}

function NavigationSection({
  label,
  items,
  onNavigate,
}: {
  label: string
  items: NavigationItem[]
  onNavigate: () => void
}) {
  if (items.length === 0) return null

  return (
    <div>
      <p className="mb-2 px-3 text-[0.68rem] font-bold tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </p>
      <div className="grid gap-1">
        {items.map((item) => (
          <MobileNavigationLink
            key={item.to}
            item={item}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </div>
  )
}

function ApiHealth() {
  const health = useHealth()
  const label = health.isLoading
    ? m.api_checking()
    : health.isSuccess
      ? m.api_ok()
      : m.api_down()

  return (
    <div
      className="flex min-h-11 items-center gap-2.5 rounded-xl border border-border/80 bg-card px-3 text-xs font-medium text-muted-foreground"
      title={label}
      role="status"
    >
      <span
        className={cn(
          "size-2.5 shrink-0 rounded-full",
          health.isSuccess
            ? "bg-success"
            : health.isLoading
              ? "bg-muted-foreground"
              : "bg-destructive",
        )}
        aria-hidden
      />
      <span className="truncate">{label}</span>
    </div>
  )
}

export function MobileNavigationContent({
  onNavigate,
}: {
  onNavigate: () => void
}) {
  const { items: adminItems } = useAdminNavigation()

  return (
    <nav className="space-y-6" aria-label={m.nav_menu()}>
      <NavigationSection
        label={m.nav_menu()}
        items={primaryItems()}
        onNavigate={onNavigate}
      />
      <NavigationSection
        label={m.nav_library()}
        items={libraryItems()}
        onNavigate={onNavigate}
      />
      {adminItems.length > 0 ? (
        <NavigationSection
          label={m.auth_admin()}
          items={adminItems}
          onNavigate={onNavigate}
        />
      ) : null}
      <NavigationSection
        label={m.nav_information()}
        items={informationItems()}
        onNavigate={onNavigate}
      />
      <ApiHealth />
    </nav>
  )
}

export function MobileBottomNavigation() {
  const pathname = usePathname()

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 grid h-[calc(4.5rem+env(safe-area-inset-bottom))] grid-cols-4 border-t border-border/85 bg-background/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-16px_40px_-30px_rgba(5,10,25,0.75)] backdrop-blur-xl lg:hidden"
      aria-label={m.nav_menu()}
    >
      {primaryItems().map((item) => {
        const active = pathIsActive(pathname, item)
        const Icon = item.icon
        return (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "relative flex min-w-0 flex-col items-center justify-center gap-1 px-1 text-[0.7rem] font-semibold text-muted-foreground outline-none transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              active && "text-foreground",
            )}
            aria-current={active ? "page" : undefined}
          >
            <span
              className={cn(
                "grid h-7 min-w-11 place-items-center rounded-full transition-colors duration-200",
                active && "bg-primary text-primary-foreground",
              )}
            >
              <Icon className="size-4.5" strokeWidth={active ? 2.4 : 1.9} aria-hidden />
            </span>
            <span className="max-w-full truncate">{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
