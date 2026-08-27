import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-[0.7rem] font-semibold",
  {
    variants: {
      variant: {
        default: "border-border bg-secondary text-secondary-foreground",
        karaoke: "border-primary/30 bg-primary/10 text-primary",
        song: "border-accent bg-accent text-accent-foreground",
        muted: "border-transparent bg-muted text-muted-foreground",
        success: "border-success/25 bg-success/10 text-success",
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
