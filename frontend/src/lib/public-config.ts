const configuredSourceUrl = (
  import.meta.env.VITE_SOURCE_URL as string | undefined
)?.trim()

export const SOURCE_URL =
  configuredSourceUrl?.startsWith("https://")
    ? configuredSourceUrl
    : "https://github.com/yutinglia/vtuber-karaoke-search"

export const ISSUES_URL = `${SOURCE_URL.replace(/\/+$/, "")}/issues/new`
export const LICENSE_URL = `${SOURCE_URL.replace(/\/+$/, "")}/blob/main/LICENSE`
