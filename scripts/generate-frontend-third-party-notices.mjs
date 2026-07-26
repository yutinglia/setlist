#!/usr/bin/env node

import { createHash } from "node:crypto"
import {
  existsSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(scriptDirectory, "..")
const frontendDirectory = path.join(repositoryRoot, "frontend")
const lockFile = path.join(frontendDirectory, "package-lock.json")
const outputFile = path.join(repositoryRoot, "THIRD_PARTY_NOTICES.md")

const lock = JSON.parse(readFileSync(lockFile, "utf8"))
const packages = []
const licenseBlocks = new Map()

function normalizeLicenseText(value) {
  return value
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trimEnd())
    .join("\n")
    .trim()
}

function packageRepository(metadata) {
  if (typeof metadata.homepage === "string") return metadata.homepage
  if (typeof metadata.repository === "string") return metadata.repository
  if (typeof metadata.repository?.url === "string") {
    return metadata.repository.url
      .replace(/^git\+/, "")
      .replace(/\.git$/, "")
  }
  return undefined
}

function readLicenseText(packageDirectory) {
  const candidates = readdirSync(packageDirectory, { withFileTypes: true })
    .filter(
      (entry) =>
        entry.isFile() &&
        /^(licen[cs]e|copying|notice)(?:[._-].*)?$/i.test(entry.name),
    )
    .map((entry) => entry.name)
    .sort((left, right) => left.localeCompare(right))

  if (candidates.length === 0) return undefined

  return normalizeLicenseText(
    candidates
      .map((name) => readFileSync(path.join(packageDirectory, name), "utf8"))
      .join("\n\n---\n\n"),
  )
}

function fallbackLicenseDirectory(packageName) {
  if (packageName.startsWith("@rolldown/binding-")) {
    return path.join(frontendDirectory, "node_modules", "rolldown")
  }
  if (packageName === "@sqlite.org/sqlite-wasm") {
    // sqlite-wasm declares Apache-2.0 but omits the standard text from its
    // package tarball. TypeScript ships the identical unmodified license text.
    return path.join(frontendDirectory, "node_modules", "typescript")
  }
  if (packageName === "react-remove-scroll-bar") {
    // This companion package omits the shared Anton Korzunov MIT text.
    return path.join(frontendDirectory, "node_modules", "react-remove-scroll")
  }
  return undefined
}

for (const [packagePath, lockMetadata] of Object.entries(lock.packages ?? {})) {
  if (
    !packagePath.startsWith("node_modules/") ||
    lockMetadata.dev === true ||
    lockMetadata.link === true
  ) {
    continue
  }

  const packageDirectory = path.join(frontendDirectory, packagePath)
  const metadataFile = path.join(packageDirectory, "package.json")
  if (!existsSync(metadataFile)) {
    if (lockMetadata.optional === true) continue
    throw new Error(
      `Missing installed package metadata for ${packagePath}; run npm ci first.`,
    )
  }

  const metadata = JSON.parse(readFileSync(metadataFile, "utf8"))
  const fallbackDirectory = fallbackLicenseDirectory(metadata.name)
  const licenseText =
    readLicenseText(packageDirectory) ??
    (fallbackDirectory ? readLicenseText(fallbackDirectory) : undefined)
  let licenseId

  if (licenseText) {
    const digest = createHash("sha256").update(licenseText).digest("hex")
    if (!licenseBlocks.has(digest)) {
      licenseBlocks.set(digest, {
        text: licenseText,
        packages: [],
      })
    }
    licenseBlocks.get(digest).packages.push(
      `${metadata.name}@${lockMetadata.version ?? metadata.version}`,
    )
    licenseId = digest
  }

  packages.push({
    name: metadata.name,
    version: lockMetadata.version ?? metadata.version,
    license: metadata.license ?? lockMetadata.license ?? "Not declared",
    author:
      typeof metadata.author === "string"
        ? metadata.author
        : metadata.author?.name,
    repository: packageRepository(metadata),
    licenseId,
  })
}

packages.sort((left, right) =>
  `${left.name}@${left.version}`.localeCompare(
    `${right.name}@${right.version}`,
  ),
)

const sortedLicenseBlocks = [...licenseBlocks.entries()].sort(
  ([, left], [, right]) =>
    left.packages[0].localeCompare(right.packages[0]),
)
const licenseLabels = new Map(
  sortedLicenseBlocks.map(([digest], index) => [
    digest,
    `L${String(index + 1).padStart(3, "0")}`,
  ]),
)

const lines = [
  "# Setlist frontend third-party notices",
  "",
  "This file records licenses and notices for production frontend packages",
  "whose code, assets, or fonts may be redistributed in the compiled site.",
  "It is generated deterministically from `frontend/package-lock.json` and the",
  "installed package license files by",
  "`node scripts/generate-frontend-third-party-notices.mjs`.",
  "",
  "Setlist's project-authored source remains licensed under the repository's",
  "MIT License. The packages below remain subject to their respective terms.",
  "",
  "## Package index",
  "",
]

for (const pkg of packages) {
  const source = pkg.repository ? ` — ${pkg.repository}` : ""
  const author = pkg.author ? ` — ${pkg.author}` : ""
  const license = pkg.licenseId
    ? `${pkg.license}; full text ${licenseLabels.get(pkg.licenseId)}`
    : `${pkg.license}; no license file was included in the installed package`
  lines.push(
    `- \`${pkg.name}@${pkg.version}\` — ${license}${author}${source}`,
  )
}

lines.push("", "## License texts", "")

for (const [digest, block] of sortedLicenseBlocks) {
  lines.push(
    `### ${licenseLabels.get(digest)}`,
    "",
    `Applies to: ${block.packages.map((name) => `\`${name}\``).join(", ")}`,
    "",
    "```text",
    block.text,
    "```",
    "",
  )
}

writeFileSync(outputFile, `${lines.join("\n").trimEnd()}\n`)
console.log(
  `Wrote ${path.relative(repositoryRoot, outputFile)} for ${packages.length} packages and ${licenseBlocks.size} license texts.`,
)
