import { createFileRoute } from "@tanstack/react-router"

import { InfoPage, InfoSection } from "@/components/info-page"
import { PageMetadata } from "@/components/page-metadata"
import { ISSUES_URL } from "@/lib/public-config"
import { m } from "@/paraglide/messages"

export const Route = createFileRoute("/terms")({
  component: TermsPage,
})

function TermsPage() {
  return (
    <InfoPage
      eyebrow={m.info_updated()}
      title={m.terms_heading()}
      intro={m.terms_intro()}
    >
      <PageMetadata
        path="/terms"
        title={`${m.terms_heading()} | Setlist`}
        description={m.terms_intro()}
      />
      <InfoSection title={m.terms_use_heading()}>
        <p>{m.terms_use_body()}</p>
      </InfoSection>
      <InfoSection title={m.terms_accuracy_heading()}>
        <p>{m.terms_accuracy_body()}</p>
      </InfoSection>
      <InfoSection title={m.terms_external_heading()}>
        <p>{m.terms_external_body()}</p>
      </InfoSection>
      <InfoSection title={m.terms_availability_heading()}>
        <p>{m.terms_availability_body()}</p>
      </InfoSection>
      <InfoSection title={m.terms_changes_heading()}>
        <p>{m.terms_changes_body()}</p>
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
