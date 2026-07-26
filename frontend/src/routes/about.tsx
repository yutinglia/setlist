import { createFileRoute } from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"

import { InfoPage, InfoSection } from "@/components/info-page"
import { buttonVariants } from "@/components/ui/button"
import { SOURCE_URL } from "@/lib/public-config"
import { cn } from "@/lib/utils"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/about")({
  component: AboutPage,
})

function AboutPage() {
  return (
    <InfoPage
      eyebrow={m.info_project()}
      title={m.about_heading()}
      intro={m.about_intro()}
    >
      <InfoSection title={m.about_how_heading()}>
        <p>{m.about_how_body()}</p>
      </InfoSection>
      <InfoSection title={m.about_scope_heading()}>
        <p>{m.about_scope_body()}</p>
      </InfoSection>
      <InfoSection title={m.about_source_heading()}>
        <p>{m.about_source_body()}</p>
        <a
          href={SOURCE_URL}
          target="_blank"
          rel="noreferrer"
          className={cn(buttonVariants({ variant: "outline" }), "mt-2")}
        >
          {m.about_view_source()}
          <ExternalLink aria-hidden />
        </a>
      </InfoSection>
    </InfoPage>
  )
}
