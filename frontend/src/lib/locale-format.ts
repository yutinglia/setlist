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
