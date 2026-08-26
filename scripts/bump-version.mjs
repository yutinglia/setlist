#!/usr/bin/env node

import { execFileSync } from "node:child_process"
import { readFileSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(scriptDirectory, "..")
const versionFile = path.join(repositoryRoot, "VERSION")
const packageFiles = [
  path.join(repositoryRoot, "frontend", "package.json"),
  path.join(repositoryRoot, "frontend", "package-lock.json"),
]
const semverPattern = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/

function fail(message) {
  console.error(`Error: ${message}`)
  process.exit(1)
}

function git(...args) {
  return execFileSync("git", args, {
    cwd: repositoryRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim()
}

function parseVersion(value, label) {
  const match = semverPattern.exec(value.trim())
  if (!match) {
    fail(`${label} must use MAJOR.MINOR.PATCH without a leading "v".`)
  }

  return match.slice(1).map(Number)
}

function compareVersions(left, right) {
  for (let index = 0; index < left.length; index += 1) {
    const difference = left[index] - right[index]
    if (difference !== 0) return difference
  }
  return 0
}

function nextVersion(current, requested) {
  const next = [...current]

  if (requested === "major") {
    return [next[0] + 1, 0, 0]
  }
  if (requested === "minor") {
    return [next[0], next[1] + 1, 0]
  }
  if (requested === "patch") {
    return [next[0], next[1], next[2] + 1]
  }

  return parseVersion(requested, "Explicit version")
}

function readPackage(file) {
  return JSON.parse(readFileSync(file, "utf8"))
}

function refExists(ref) {
  try {
    git("rev-parse", "--verify", "--quiet", ref)
    return true
  } catch {
    return false
  }
}

function requireCurrentMain() {
  if (git("branch", "--show-current") !== "main") {
    fail("Run this command from the main branch.")
  }

  if (!refExists("refs/remotes/origin/main")) {
    fail("origin/main is unavailable. Run git fetch origin before continuing.")
  }

  if (git("rev-parse", "HEAD") !== git("rev-parse", "refs/remotes/origin/main")) {
    fail("main must exactly match origin/main. Run git pull --ff-only first.")
  }
}

const requested = process.argv[2]
if (!requested) {
  fail(
    "Pass major, minor, patch, an explicit version, or tag. Example: node scripts/bump-version.mjs patch"
  )
}

if (path.resolve(git("rev-parse", "--show-toplevel")) !== repositoryRoot) {
  fail("Run this script from the Setlist repository.")
}

if (git("status", "--porcelain")) {
  fail("The working tree must be clean before creating a release.")
}

requireCurrentMain()

const currentText = readFileSync(versionFile, "utf8").trim()
const current = parseVersion(currentText, "VERSION")
const packageJson = readPackage(packageFiles[0])
const packageLock = readPackage(packageFiles[1])

if (
  packageJson.version !== currentText ||
  packageLock.version !== currentText ||
  packageLock.packages?.[""]?.version !== currentText
) {
  fail("VERSION, package.json, and package-lock.json are not synchronized.")
}

if (requested === "tag") {
  const tag = `v${currentText}`

  if (refExists(`refs/tags/${tag}`)) {
    fail(`Tag ${tag} already exists.`)
  }

  try {
    git("tag", "--annotate", tag, "--message", `Release ${tag}`)
  } catch (error) {
    fail(`Git could not create ${tag}.\n${error.message}`)
  }

  console.log(`Created annotated tag ${tag} on main.`)
  console.log(`Review it, then publish with: git push origin ${tag}`)
  process.exit(0)
}

const next = nextVersion(current, requested)
if (compareVersions(next, current) <= 0) {
  fail(`The new version must be greater than ${currentText}.`)
}

const nextText = next.join(".")
const tag = `v${nextText}`
const releaseBranch = `release/${tag}`

if (refExists(`refs/tags/${tag}`)) {
  fail(`Tag ${tag} already exists.`)
}

if (
  refExists(`refs/heads/${releaseBranch}`) ||
  refExists(`refs/remotes/origin/${releaseBranch}`)
) {
  fail(`Branch ${releaseBranch} already exists.`)
}

git("switch", "--create", releaseBranch)

packageJson.version = nextText
packageLock.version = nextText
packageLock.packages[""].version = nextText

writeFileSync(versionFile, `${nextText}\n`)
writeFileSync(packageFiles[0], `${JSON.stringify(packageJson, null, 2)}\n`)
writeFileSync(packageFiles[1], `${JSON.stringify(packageLock, null, 2)}\n`)

try {
  git("add", "VERSION", "frontend/package.json", "frontend/package-lock.json")
  git("commit", "-m", `chore(release): ${tag}`)
} catch (error) {
  fail(
    `Git could not create the release commit. Review the working tree before retrying.\n${error.message}`
  )
}

console.log(`Created release commit on ${releaseBranch}.`)
console.log("Push it and open a pull request:")
console.log(`  git push --set-upstream origin ${releaseBranch}`)
console.log(
  `  gh pr create --base main --head ${releaseBranch} --title "Release ${tag}"`
)
console.log("After the pull request passes required checks and merges:")
console.log("  git switch main")
console.log("  git pull --ff-only")
console.log("  node scripts/bump-version.mjs tag")
console.log(`  git push origin ${tag}`)
