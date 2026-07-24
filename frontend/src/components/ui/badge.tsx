import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-[0.65rem] font-medium tracking-wide uppercase",
  {
    variants: {
      variant: {
        default: "border-border/80 bg-secondary/80 text-secondary-foreground",
        karaoke: "border-primary/30 bg-primary/10 text-primary",
        song: "border-accent/35 bg-accent/12 text-foreground",
        muted: "border-transparent bg-muted text-muted-foreground",
        success: "border-primary/25 bg-secondary text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
