const configuredSourceUrl = (
  import.meta.env.VITE_SOURCE_URL as string | undefined
)?.trim()
const configuredPublicSiteUrl = (
  import.meta.env.VITE_PUBLIC_SITE_URL as string | undefined
)?.trim()

export const SOURCE_URL =
  configuredSourceUrl?.startsWith("https://")
    ? configuredSourceUrl
    : "https://github.com/yutinglia/setlist"

export const PUBLIC_SITE_URL =
  configuredPublicSiteUrl?.startsWith("http://") ||
  configuredPublicSiteUrl?.startsWith("https://")
    ? configuredPublicSiteUrl.replace(/\/+$/, "")
    : "http://localhost:5173"

export const ISSUES_URL = `${SOURCE_URL.replace(/\/+$/, "")}/issues/new`
export const LICENSE_URL = `${SOURCE_URL.replace(/\/+$/, "")}/blob/main/LICENSE`
export const THIRD_PARTY_NOTICES_URL = "/THIRD_PARTY_NOTICES.md"
