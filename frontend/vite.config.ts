import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

import { paraglideVitePlugin } from "@inlang/paraglide-js"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(__dirname, "..")

function normalizeVersion(value: string | undefined) {
  const normalized = value?.trim().replace(/^v/, "")

  return normalized &&
    /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(
      normalized
    )
    ? normalized
    : undefined
}

function versionFromExactGitTag() {
  try {
    return normalizeVersion(
      execFileSync(
        "git",
        ["describe", "--tags", "--exact-match", "--match", "v[0-9]*"],
        {
          cwd: repositoryRoot,
          encoding: "utf8",
          stdio: ["ignore", "pipe", "ignore"],
        }
      )
    )
  } catch {
    return undefined
  }
}

function versionFromFile() {
  try {
    return normalizeVersion(
      readFileSync(path.join(repositoryRoot, "VERSION"), "utf8")
    )
  } catch {
    return undefined
  }
}

function versionFromPackage() {
  try {
    const packageJson = JSON.parse(
      readFileSync(path.join(__dirname, "package.json"), "utf8")
    ) as { version?: string }
    return normalizeVersion(packageJson.version)
  } catch {
    return undefined
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "")
  const publicSiteUrl = (
    env.VITE_PUBLIC_SITE_URL || "http://localhost:5173"
  ).replace(/\/+$/, "")
  const appVersion =
    normalizeVersion(env.VITE_APP_VERSION) ??
    versionFromExactGitTag() ??
    versionFromFile() ??
    versionFromPackage() ??
    "0.0.0"

  return {
    define: {
      __APP_VERSION__: JSON.stringify(appVersion),
    },
    plugins: [
      {
        name: "public-site-url",
        transformIndexHtml: (html) =>
          html.replaceAll("__PUBLIC_SITE_URL__", publicSiteUrl),
      },
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
      react(),
      tailwindcss(),
      paraglideVitePlugin({
        project: "./project.inlang",
        outdir: "./src/paraglide",
        emitTsDeclarations: true,
        strategy: ["localStorage", "cookie", "preferredLanguage", "baseLocale"],
      }),
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: true,
      port: 5173,
      // Poll when CHOKIDAR_USEPOLLING is set (Dev Container environment) so HMR
      // sees edits through Docker bind mounts that skip inotify.
      watch: {
        usePolling: process.env.CHOKIDAR_USEPOLLING === "true",
      },
      proxy: {
        "/v1": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  }
})
