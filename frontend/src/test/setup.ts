import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, beforeEach, vi } from "vitest"

resetDomPreferences()
Object.defineProperties(HTMLElement.prototype, {
  hasPointerCapture: {
    configurable: true,
    value: vi.fn(() => false),
  },
  releasePointerCapture: {
    configurable: true,
    value: vi.fn(),
  },
  scrollIntoView: {
    configurable: true,
    value: vi.fn(),
  },
})

beforeEach(() => {
  document.head.innerHTML = `
    <link rel="canonical" href="http://localhost:5173/" />
    <meta name="description" content="" />
    <meta name="robots" content="" />
    <meta property="og:locale" content="" />
    <meta property="og:title" content="" />
    <meta property="og:description" content="" />
    <meta property="og:url" content="" />
    <meta name="twitter:title" content="" />
    <meta name="twitter:description" content="" />
  `
  localStorage.clear()
  resetDomPreferences()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

function resetDomPreferences() {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
  Object.defineProperty(window, "scrollTo", {
    configurable: true,
    value: vi.fn(),
  })
  Object.defineProperty(window, "ResizeObserver", {
    configurable: true,
    value: class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  })
}
