import { useEffect } from "react"

import { currentIntlLocale } from "@/lib/locale-format"
import { PUBLIC_SITE_URL } from "@/lib/public-config"
import { m } from "@/paraglide/messages"

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
  title,
  description,
  path,
  noIndex = false,
}: PageMetadataProps) {
  const resolvedTitle = title ?? m.meta_default_title()
  const resolvedDescription = description ?? m.meta_default_description()

  useEffect(() => {
    const canonicalUrl = new URL(path, `${PUBLIC_SITE_URL}/`).toString()
    const canonical = document.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    )
    const ogLocale = currentIntlLocale().replace("-", "_")

    document.title = resolvedTitle
    canonical?.setAttribute("href", canonicalUrl)
    setMetaContent('meta[name="description"]', resolvedDescription)
    setMetaContent(
      'meta[name="robots"]',
      noIndex
        ? "noindex,follow"
        : "index,follow,max-image-preview:large",
    )
    setMetaContent('meta[property="og:locale"]', ogLocale)
    setMetaContent('meta[property="og:title"]', resolvedTitle)
    setMetaContent('meta[property="og:description"]', resolvedDescription)
    setMetaContent('meta[property="og:url"]', canonicalUrl)
    setMetaContent('meta[name="twitter:title"]', resolvedTitle)
    setMetaContent('meta[name="twitter:description"]', resolvedDescription)

    return () => {
      const defaultTitle = m.meta_default_title()
      const defaultDescription = m.meta_default_description()
      document.title = defaultTitle
      canonical?.setAttribute("href", `${PUBLIC_SITE_URL}/`)
      setMetaContent('meta[name="description"]', defaultDescription)
      setMetaContent(
        'meta[name="robots"]',
        "index,follow,max-image-preview:large",
      )
      setMetaContent('meta[property="og:title"]', defaultTitle)
      setMetaContent('meta[property="og:description"]', defaultDescription)
      setMetaContent('meta[property="og:url"]', `${PUBLIC_SITE_URL}/`)
      setMetaContent('meta[name="twitter:title"]', defaultTitle)
      setMetaContent(
        'meta[name="twitter:description"]',
        defaultDescription,
      )
    }
  }, [noIndex, path, resolvedDescription, resolvedTitle])

  return null
}
