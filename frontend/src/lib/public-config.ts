const configuredSourceUrl = (
  import.meta.env.VITE_SOURCE_URL as string | undefined
)?.trim()
const configuredPublicSiteUrl = (
  import.meta.env.VITE_PUBLIC_SITE_URL as string | undefined
)?.trim()
const configuredChannelRequestUrl = (
  import.meta.env.VITE_CHANNEL_REQUEST_URL as string | undefined
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

const sourceBaseUrl = SOURCE_URL.replace(/\/+$/, "")

export const ISSUES_URL = `${sourceBaseUrl}/issues/new/choose`
export const CHANNEL_REQUEST_ISSUE_URL =
  `${sourceBaseUrl}/issues/new?template=channel-request.yml`
export const DATA_REQUEST_ISSUE_URL =
  `${sourceBaseUrl}/issues/new?template=correction-or-removal.yml`
export const CHANNEL_REQUEST_URL = isSafeContactUrl(configuredChannelRequestUrl)
  ? configuredChannelRequestUrl
  : CHANNEL_REQUEST_ISSUE_URL
export const LICENSE_URL = `${sourceBaseUrl}/blob/main/LICENSE`
export const THIRD_PARTY_NOTICES_URL = "/THIRD_PARTY_NOTICES.md"

function isSafeContactUrl(value: string | undefined): value is string {
  if (!value) {
    return false
  }
  if (value.startsWith("/") && !value.startsWith("//")) {
    return true
  }

  try {
    return ["https:", "http:", "mailto:"].includes(new URL(value).protocol)
  } catch {
    return false
  }
}
