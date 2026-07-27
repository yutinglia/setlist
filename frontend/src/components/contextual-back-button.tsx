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
        "inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-primary",
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
