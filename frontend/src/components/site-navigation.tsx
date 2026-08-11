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
import { useUiStore } from "@/stores/ui-store"

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
    items.push({ to: "/status", label: m.nav_status(), icon: Activity })
  }
  if (canManage) {
    items.push({
      to: "/channels/new",
      label: m.channel_add_cta(),
      icon: CirclePlus,
      exact: true,
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

function NavigationLink({
  item,
  compact = false,
  mobile = false,
  onNavigate,
}: {
  item: NavigationItem
  compact?: boolean
  mobile?: boolean
  onNavigate?: () => void
}) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const active = pathIsActive(pathname, item)
  const Icon = item.icon

  return (
    <Link
      to={item.to}
      className={cn(
        "group relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
        active && "bg-secondary font-semibold text-foreground",
        compact
          ? "justify-center px-0"
          : "lg:max-xl:justify-center lg:max-xl:px-0",
        mobile && "min-h-12",
      )}
      aria-current={active ? "page" : undefined}
      aria-label={compact ? item.label : undefined}
      title={item.label}
      onClick={onNavigate}
    >
      <Icon
        className={cn(
          "size-5 shrink-0 transition-colors",
          active && "text-primary",
        )}
        strokeWidth={active ? 2.35 : 1.9}
        aria-hidden
      />
      <span
        className={cn(
          "truncate lg:max-xl:sr-only",
          compact && "hidden",
        )}
      >
        {item.label}
      </span>
      {active ? (
        <span
          className={cn(
            "absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-primary",
            compact
              ? "top-auto right-2 bottom-0 left-2 h-0.5 w-auto"
              : "lg:max-xl:top-auto lg:max-xl:right-2 lg:max-xl:bottom-0 lg:max-xl:left-2 lg:max-xl:h-0.5 lg:max-xl:w-auto",
          )}
          aria-hidden
        />
      ) : null}
    </Link>
  )
}

function NavigationSection({
  label,
  items,
  compact = false,
  mobile = false,
  onNavigate,
}: {
  label: string
  items: NavigationItem[]
  compact?: boolean
  mobile?: boolean
  onNavigate?: () => void
}) {
  if (items.length === 0) return null

  return (
    <div>
      <p
        className={cn(
          "mb-2 px-3 text-[0.68rem] font-semibold tracking-[0.12em] text-muted-foreground uppercase",
          compact ? "sr-only" : "lg:max-xl:sr-only",
        )}
      >
        {label}
      </p>
      <div className="grid gap-1">
        {items.map((item) => (
          <NavigationLink
            key={item.to}
            item={item}
            compact={compact}
            mobile={mobile}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </div>
  )
}

function ApiHealth({ compact = false }: { compact?: boolean }) {
  const health = useHealth()
  const label = health.isLoading
    ? m.api_checking()
    : health.isSuccess
      ? m.api_ok()
      : m.api_down()

  return (
    <div
      className={cn(
        "flex min-h-10 items-center gap-2 rounded-xl border border-border bg-card px-3 text-xs text-muted-foreground lg:max-xl:justify-center lg:max-xl:px-0",
        compact && "justify-center px-0",
      )}
      title={label}
      role="status"
    >
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          health.isSuccess
            ? "bg-emerald-600 dark:bg-emerald-400"
            : health.isLoading
              ? "bg-muted-foreground"
              : "bg-destructive",
        )}
        aria-hidden
      />
      <span
        className={cn("truncate lg:max-xl:sr-only", compact && "sr-only")}
      >
        {label}
      </span>
    </div>
  )
}

export function DesktopSidebar() {
  const collapsed = useUiStore((state) => state.sidebarCollapsed)
  const { items: adminItems } = useAdminNavigation()

  return (
    <aside
      className={cn(
        "sticky top-16 hidden h-[calc(100svh-4rem)] shrink-0 flex-col border-r border-border bg-background transition-[width] duration-200 lg:flex",
        collapsed ? "w-[4.75rem]" : "w-[4.75rem] xl:w-60",
      )}
    >
      <nav
        className="scrollbar-none flex-1 space-y-6 overflow-y-auto px-2 py-4"
        aria-label={m.nav_menu()}
      >
        <NavigationSection
          label={m.nav_menu()}
          items={primaryItems()}
          compact={collapsed}
        />
        <NavigationSection
          label={m.nav_library()}
          items={libraryItems()}
          compact={collapsed}
        />
        {adminItems.length > 0 ? (
          <NavigationSection
            label={m.auth_admin()}
            items={adminItems}
            compact={collapsed}
          />
        ) : null}
        <NavigationSection
          label={m.nav_information()}
          items={informationItems()}
          compact={collapsed}
        />
      </nav>
      <div className="border-t border-border p-2">
        <ApiHealth compact={collapsed} />
      </div>
    </aside>
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
        mobile
        onNavigate={onNavigate}
      />
      <NavigationSection
        label={m.nav_library()}
        items={libraryItems()}
        mobile
        onNavigate={onNavigate}
      />
      {adminItems.length > 0 ? (
        <NavigationSection
          label={m.auth_admin()}
          items={adminItems}
          mobile
          onNavigate={onNavigate}
        />
      ) : null}
      <NavigationSection
        label={m.nav_information()}
        items={informationItems()}
        mobile
        onNavigate={onNavigate}
      />
      <ApiHealth />
    </nav>
  )
}

export function MobileBottomNavigation() {
  const items = primaryItems()

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 grid h-[calc(4rem+env(safe-area-inset-bottom))] grid-cols-4 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-8px_30px_-24px_rgba(0,0,0,0.45)] backdrop-blur-xl lg:hidden"
      aria-label={m.nav_menu()}
    >
      {items.map((item) => (
        <MobileBottomLink key={item.to} item={item} />
      ))}
    </nav>
  )
}

function MobileBottomLink({ item }: { item: NavigationItem }) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const active = pathIsActive(pathname, item)
  const Icon = item.icon

  return (
    <Link
      to={item.to}
      className={cn(
        "relative flex min-w-0 flex-col items-center justify-center gap-1 px-1 text-[0.68rem] font-medium text-muted-foreground outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        active && "font-semibold text-foreground",
      )}
      aria-current={active ? "page" : undefined}
    >
      <Icon
        className={cn("size-5", active && "text-primary")}
        strokeWidth={active ? 2.4 : 1.9}
        aria-hidden
      />
      <span className="max-w-full truncate">{item.label}</span>
      {active ? (
        <span
          className="absolute top-0 right-[28%] left-[28%] h-0.5 rounded-full bg-primary"
          aria-hidden
        />
      ) : null}
    </Link>
  )
}
