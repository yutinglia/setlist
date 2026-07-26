import { readFileSync, readdirSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
)
const messagesRoot = path.join(frontendRoot, "messages")
const settings = JSON.parse(
  readFileSync(
    path.join(frontendRoot, "project.inlang", "settings.json"),
    "utf8",
  ),
)
const locales = settings.locales
const baseLocale = settings.baseLocale

if (!Array.isArray(locales) || !locales.includes(baseLocale)) {
  throw new Error("Invalid Paraglide locale configuration.")
}

const declaredFiles = new Set(locales.map((locale) => `${locale}.json`))
const messageFiles = readdirSync(messagesRoot).filter((name) =>
  name.endsWith(".json"),
)
const undeclaredFiles = messageFiles.filter((name) => !declaredFiles.has(name))
if (undeclaredFiles.length > 0) {
  throw new Error(
    `Message files missing from project.inlang settings: ${undeclaredFiles.join(", ")}`,
  )
}

const messages = Object.fromEntries(
  locales.map((locale) => [
    locale,
    JSON.parse(
      readFileSync(path.join(messagesRoot, `${locale}.json`), "utf8"),
    ),
  ]),
)
const baseKeys = Object.keys(messages[baseLocale]).sort()

function placeholders(message) {
  return [...message.matchAll(/\{([^{}]+)\}/g)]
    .map((match) => match[1])
    .sort()
}

for (const locale of locales) {
  const keys = Object.keys(messages[locale]).sort()
  const missing = baseKeys.filter((key) => !keys.includes(key))
  const extra = keys.filter((key) => !baseKeys.includes(key))

  if (missing.length > 0 || extra.length > 0) {
    throw new Error(
      `${locale} message-key mismatch; missing: ${missing.join(", ") || "none"}; extra: ${extra.join(", ") || "none"}`,
    )
  }

  for (const key of baseKeys) {
    const expected = placeholders(messages[baseLocale][key])
    const actual = placeholders(messages[locale][key])
    if (expected.join("\0") !== actual.join("\0")) {
      throw new Error(
        `${locale}.${key} placeholder mismatch; expected: ${expected.join(", ") || "none"}; actual: ${actual.join(", ") || "none"}`,
      )
    }
  }
}

console.log(
  `Verified ${baseKeys.length} messages across ${locales.length} locales: ${locales.join(", ")}`,
)
