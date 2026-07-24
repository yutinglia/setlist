import { create } from "zustand"
import { persist } from "zustand/middleware"

import { getLocale, setLocale, type Locale } from "@/paraglide/runtime"

const MAX_RECENT = 8

type UiState = {
  locale: Locale
  recentSearches: string[]
  setLocalePref: (locale: Locale) => void
  addRecentSearch: (q: string) => void
  clearRecentSearches: () => void
}

function isLocale(value: string): value is Locale {
  return value === "en" || value === "zh-hant"
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      locale: getLocale(),
      recentSearches: [],
      setLocalePref: (locale) => {
        if (get().locale === locale) return
        set({ locale })
        setLocale(locale, { reload: true })
      },
      addRecentSearch: (q) => {
        const trimmed = q.trim()
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
