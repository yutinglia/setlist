import path from "node:path"
import { fileURLToPath } from "node:url"

import { paraglideVitePlugin } from "@inlang/paraglide-js"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "")
  const publicSiteUrl = (
    env.VITE_PUBLIC_SITE_URL || "http://localhost:5173"
  ).replace(/\/+$/, "")

  return {
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
