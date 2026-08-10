import { getLocale } from "@/paraglide/runtime"

export function currentIntlLocale(): string {
  switch (getLocale()) {
    case "zh-hant":
      return "zh-TW"
    case "ja":
      return "ja-JP"
    default:
      return "en-US"
  }
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat(currentIntlLocale()).format(value)
}

export function formatDateTime(value: Date): string {
  return value.toLocaleString(currentIntlLocale())
}

/** Parse the API's UTC timestamps, including legacy values without a suffix. */
export function formatApiDateTime(value: string): string {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? value : formatDateTime(date)
}
