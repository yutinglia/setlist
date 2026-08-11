import { useRouter } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"

import { cn } from "@/lib/utils"

type Props = {
  label: string
  onFallback: () => void | Promise<void>
  className?: string
}

export function ContextualBackButton({
  label,
  onFallback,
  className,
}: Props) {
  const router = useRouter()

  return (
    <button
      type="button"
      className={cn(
        "inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full px-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      onClick={() => {
        if (router.history.canGoBack()) {
          router.history.back()
          return
        }
        void onFallback()
      }}
    >
      <ArrowLeft className="size-4" aria-hidden />
      {label}
    </button>
  )
}
