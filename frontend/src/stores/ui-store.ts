import { create } from "zustand"
import { persist } from "zustand/middleware"

import { getLocale, setLocale, type Locale } from "@/paraglide/runtime"

const MAX_RECENT = 8
const MAX_QUERY_LENGTH = 200
const DEFAULT_THEME =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light"

export type Theme = "light" | "dark"

type UiState = {
  locale: Locale
  theme: Theme
  sidebarCollapsed: boolean
  recentSearches: string[]
  setLocalePref: (locale: Locale) => void
  toggleTheme: () => void
  toggleSidebar: () => void
  addRecentSearch: (q: string) => void
  clearRecentSearches: () => void
}

function isLocale(value: string): value is Locale {
  return value === "en" || value === "zh-hant" || value === "ja"
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      locale: getLocale(),
      theme: DEFAULT_THEME,
      sidebarCollapsed: false,
      recentSearches: [],
      setLocalePref: (locale) => {
        if (get().locale === locale) return
        set({ locale })
        setLocale(locale, { reload: true })
      },
      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === "dark" ? "light" : "dark",
        })),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      addRecentSearch: (q) => {
        const trimmed = q.trim().slice(0, MAX_QUERY_LENGTH)
        if (!trimmed) return
        set((state) => {
          const next = [
            trimmed,
            ...state.recentSearches.filter(
              (item) => item.toLowerCase() !== trimmed.toLowerCase(),
            ),
          ].slice(0, MAX_RECENT)
          return { recentSearches: next }
        })
      },
      clearRecentSearches: () => set({ recentSearches: [] }),
    }),
    {
      name: "vks-ui",
      partialize: (state) => ({
        locale: state.locale,
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
        recentSearches: state.recentSearches,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return
        if (isLocale(state.locale) && state.locale !== getLocale()) {
          setLocale(state.locale, { reload: false })
        }
      },
    },
  ),
)
