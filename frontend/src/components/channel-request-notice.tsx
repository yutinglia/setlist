import {
  ExternalLink,
  MessageSquarePlus,
  Server,
  ShieldCheck,
} from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { CHANNEL_REQUEST_URL } from "@/lib/public-config"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export function ChannelRequestNotice({ className }: { className?: string }) {
  return (
    <aside className={cn("surface overflow-hidden", className)}>
      <div className="border-b border-border bg-primary/5 p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
            <ShieldCheck className="size-5" aria-hidden />
          </span>
          <div>
            <h2 className="text-xl font-bold tracking-tight">
              {m.channel_request_title()}
            </h2>
            <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
              {m.channel_request_admin_only()}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-px bg-border sm:grid-cols-2">
        <section className="bg-card p-5 sm:p-6">
          <MessageSquarePlus className="size-5 text-primary" aria-hidden />
          <h3 className="mt-3 font-bold">
            {m.channel_request_contact_title()}
          </h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {m.channel_request_contact_body()}
          </p>
          <a
            href={CHANNEL_REQUEST_URL}
            target="_blank"
            rel="noreferrer"
            className={cn(
              buttonVariants({ variant: "outline" }),
              "mt-4",
            )}
          >
            {m.channel_request_contact_cta()}
            <ExternalLink aria-hidden />
          </a>
        </section>

        <section className="bg-card p-5 sm:p-6">
          <Server className="size-5 text-primary" aria-hidden />
          <h3 className="mt-3 font-bold">
            {m.channel_request_host_title()}
          </h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {m.channel_request_host_body()}
          </p>
        </section>
      </div>
    </aside>
  )
}
