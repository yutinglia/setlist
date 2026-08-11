import { Link, createFileRoute } from "@tanstack/react-router"
import { Clock3, ListFilter, Search } from "lucide-react"

import { ChannelRequestNotice } from "@/components/channel-request-notice"
import { InfoPage, InfoSection } from "@/components/info-page"
import { PageMetadata } from "@/components/page-metadata"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/how-to-use")({
  component: HowToUsePage,
})

function HowToUsePage() {
  return (
    <>
      <PageMetadata
        path="/how-to-use"
        title={`${m.how_to_heading()} | Setlist`}
        description={m.how_to_intro()}
      />
      <InfoPage
        eyebrow={m.how_to_eyebrow()}
        title={m.how_to_heading()}
        intro={m.how_to_intro()}
      >
        <InfoSection title={m.how_to_search_heading()}>
          <ol className="grid gap-5 sm:grid-cols-3">
            <HowToStep
              number="1"
              icon={Search}
              title={m.how_to_search_title()}
              body={m.how_to_search_body()}
            />
            <HowToStep
              number="2"
              icon={ListFilter}
              title={m.how_to_filter_title()}
              body={m.how_to_filter_body()}
            />
            <HowToStep
              number="3"
              icon={Clock3}
              title={m.how_to_open_title()}
              body={m.how_to_open_body()}
            />
          </ol>
          <Link
            to="/search"
            className={cn(buttonVariants(), "mt-2 inline-flex")}
          >
            <Search aria-hidden />
            {m.how_to_search_cta()}
          </Link>
        </InfoSection>

        <InfoSection title={m.how_to_browse_heading()}>
          <p>{m.how_to_browse_body()}</p>
          <Link
            to="/channels"
            className={cn(
              buttonVariants({ variant: "outline" }),
              "mt-2 inline-flex",
            )}
          >
            {m.home_browse_all()}
          </Link>
        </InfoSection>

        <InfoSection title={m.how_to_accuracy_heading()}>
          <p>{m.how_to_accuracy_body()}</p>
        </InfoSection>

        <ChannelRequestNotice />
      </InfoPage>
    </>
  )
}

function HowToStep({
  number,
  icon: Icon,
  title,
  body,
}: {
  number: string
  icon: typeof Search
  title: string
  body: string
}) {
  return (
    <li className="relative rounded-2xl border border-border/70 bg-background/50 p-4">
      <span className="absolute top-3 right-3 font-mono text-xs font-bold text-primary">
        {number.padStart(2, "0")}
      </span>
      <Icon className="size-5 text-primary" aria-hidden />
      <h3 className="mt-3 font-bold text-foreground">{title}</h3>
      <p className="mt-1.5 leading-6">{body}</p>
    </li>
  )
}
