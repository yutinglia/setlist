import { createFileRoute } from "@tanstack/react-router"

import { InfoPage, InfoSection } from "@/components/info-page"
import { PageMetadata } from "@/components/page-metadata"
import { ISSUES_URL, LICENSE_URL } from "@/lib/public-config"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/copyright")({
  component: CopyrightPage,
})

function CopyrightPage() {
  return (
    <InfoPage
      eyebrow={m.info_project()}
      title={m.copyright_heading()}
      intro={m.copyright_intro()}
    >
      <PageMetadata
        path="/copyright"
        title={`${m.copyright_heading()} | Setlist`}
        description={m.copyright_intro()}
      />
      <InfoSection title={m.copyright_media_heading()}>
        <p>{m.copyright_media_body()}</p>
      </InfoSection>
      <InfoSection title={m.copyright_metadata_heading()}>
        <p>{m.copyright_metadata_body()}</p>
      </InfoSection>
      <InfoSection title={m.copyright_source_heading()}>
        <p>
          {m.copyright_source_body()}{" "}
          <a
            href={LICENSE_URL}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            {m.copyright_source_link()}
          </a>
        </p>
      </InfoSection>
      <InfoSection title={m.copyright_request_heading()}>
        <p>{m.copyright_request_body()}</p>
        <a
          href={ISSUES_URL}
          target="_blank"
          rel="noreferrer"
          className="font-medium text-primary underline-offset-2 hover:underline"
        >
          {m.copyright_request_link()}
        </a>
      </InfoSection>
    </InfoPage>
  )
}
