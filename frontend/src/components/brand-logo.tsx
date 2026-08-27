import { Link } from "@tanstack/react-router"
import { ListMusic } from "lucide-react"

import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export function BrandLogo({
  compact = false,
  className,
  onNavigate,
}: {
  compact?: boolean
  className?: string
  onNavigate?: () => void
}) {
  return (
    <Link
      to="/"
      className={cn(
        "group inline-flex min-h-11 min-w-0 items-center gap-3 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className,
      )}
      aria-label={m.brand_name()}
      onClick={onNavigate}
    >
      <span className="brand-mark" aria-hidden>
        <ListMusic className="relative z-10 size-5" strokeWidth={2.35} />
      </span>
      <span className={cn("min-w-0", compact && "hidden")}>
        <span className="block truncate text-[1.08rem] leading-none font-bold tracking-[-0.03em]">
          {m.brand_name()}
        </span>
        <span className="mt-1.5 block truncate text-[0.58rem] leading-none font-bold tracking-[0.16em] text-muted-foreground uppercase">
          VTuber karaoke
        </span>
      </span>
    </Link>
  )
}
