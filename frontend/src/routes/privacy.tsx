import { createFileRoute } from "@tanstack/react-router"

import { InfoPage, InfoSection } from "@/components/info-page"
import { PageMetadata } from "@/components/page-metadata"
import { ISSUES_URL } from "@/lib/public-config"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/privacy")({
  component: PrivacyPage,
})

function PrivacyPage() {
  return (
    <InfoPage
      eyebrow={m.info_updated()}
      title={m.privacy_heading()}
      intro={m.privacy_intro()}
    >
      <PageMetadata
        path="/privacy"
        title={`${m.privacy_heading()} | Setlist`}
        description={m.privacy_intro()}
      />
      <InfoSection title={m.privacy_collected_heading()}>
        <p>{m.privacy_collected_body()}</p>
      </InfoSection>
      <InfoSection title={m.privacy_storage_heading()}>
        <p>{m.privacy_storage_body()}</p>
      </InfoSection>
      <InfoSection title={m.privacy_admin_heading()}>
        <p>{m.privacy_admin_body()}</p>
      </InfoSection>
      <InfoSection title={m.privacy_external_heading()}>
        <p>{m.privacy_external_body()}</p>
      </InfoSection>
      <InfoSection title={m.privacy_retention_heading()}>
        <p>{m.privacy_retention_body()}</p>
      </InfoSection>
      <InfoSection title={m.info_contact_heading()}>
        <p>
          {m.info_contact_body()}{" "}
          <a
            href={ISSUES_URL}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            {m.info_contact_link()}
          </a>
        </p>
      </InfoSection>
    </InfoPage>
  )
}
