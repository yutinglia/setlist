/// <reference types="vite/client" />

declare const __APP_VERSION__: string

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_APP_VERSION?: string
  readonly VITE_PUBLIC_SITE_URL?: string
  readonly VITE_SOURCE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
