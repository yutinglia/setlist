import { useEffect } from "react"

import { PUBLIC_SITE_URL } from "@/lib/public-config"

const DEFAULT_TITLE = "Setlist — VTuber Karaoke Search"
const DEFAULT_DESCRIPTION =
  "Search VTuber karaoke setlists and jump straight to the exact performance on YouTube."

type PageMetadataProps = {
  title?: string
  description?: string
  path: string
  noIndex?: boolean
}

function setMetaContent(selector: string, content: string) {
  const element = document.querySelector<HTMLMetaElement>(selector)
  element?.setAttribute("content", content)
}

export function PageMetadata({
  title = DEFAULT_TITLE,
  description = DEFAULT_DESCRIPTION,
  path,
  noIndex = false,
}: PageMetadataProps) {
  useEffect(() => {
    const canonicalUrl = new URL(path, `${PUBLIC_SITE_URL}/`).toString()
    const canonical = document.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    )

    document.title = title
    canonical?.setAttribute("href", canonicalUrl)
    setMetaContent('meta[name="description"]', description)
    setMetaContent(
      'meta[name="robots"]',
      noIndex
        ? "noindex,follow"
        : "index,follow,max-image-preview:large",
    )
    setMetaContent('meta[property="og:title"]', title)
    setMetaContent('meta[property="og:description"]', description)
    setMetaContent('meta[property="og:url"]', canonicalUrl)
    setMetaContent('meta[name="twitter:title"]', title)
    setMetaContent('meta[name="twitter:description"]', description)

    return () => {
      document.title = DEFAULT_TITLE
      canonical?.setAttribute("href", `${PUBLIC_SITE_URL}/`)
      setMetaContent('meta[name="description"]', DEFAULT_DESCRIPTION)
      setMetaContent(
        'meta[name="robots"]',
        "index,follow,max-image-preview:large",
      )
      setMetaContent('meta[property="og:title"]', DEFAULT_TITLE)
      setMetaContent('meta[property="og:description"]', DEFAULT_DESCRIPTION)
      setMetaContent('meta[property="og:url"]', `${PUBLIC_SITE_URL}/`)
      setMetaContent('meta[name="twitter:title"]', DEFAULT_TITLE)
      setMetaContent(
        'meta[name="twitter:description"]',
        DEFAULT_DESCRIPTION,
      )
    }
  }, [description, noIndex, path, title])

  return null
}
