import { QueryClient } from "@tanstack/react-query"
import { isRedirect } from "@tanstack/react-router"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { createApiClient } from "@/api/client"
import {
  requireAdminRoute,
  requireManagementRoute,
} from "@/lib/auth-guard"
import {
  currentIntlLocale,
  formatDateTime,
  formatInteger,
} from "@/lib/locale-format"
import { buildPageItems, buildPageOptions } from "@/lib/pagination"
import {
  CHANNEL_PAGE_SIZES,
  channelVideosSearchSchema,
  htmlDateToYyyymmdd,
  loginSearchSchema,
  pageSearchSchema,
  parseChannelIds,
  resolveChannelPageSize,
  serializeChannelIds,
  songSearchSchema,
  toChannelVideosSearch,
  yyyymmddToHtmlDate,
} from "@/lib/search-schemas"
import {
  compareUploadDateDesc,
  formatUploadDate,
  sortVideosByUploadDateDesc,
  uploadDateTimeAttr,
} from "@/lib/upload-date"
import { cn } from "@/lib/utils"
import {
  youtubeThumbnailUrl,
  youtubeUrlAtTimestamp,
  youtubeVideoUrl,
} from "@/lib/youtube"
import { setLocale } from "@/paraglide/runtime"

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

describe("pagination helpers", () => {
  test("builds empty, compact, clamped, and ellipsized page ranges", () => {
    expect(buildPageItems(0, 0)).toEqual([])
    expect(buildPageItems(-4, 3)).toEqual([0, 1, 2])
    expect(buildPageItems(99, 12)).toEqual([
      0,
      1,
      2,
      "ellipsis",
      9,
      10,
      11,
    ])
    expect(buildPageItems(6, 12)).toEqual([
      0,
      1,
      2,
      "ellipsis",
      5,
      6,
      7,
      "ellipsis",
      9,
      10,
      11,
    ])
    expect(buildPageOptions(0)).toEqual([])
    expect(buildPageOptions(3)).toEqual([0, 1, 2])
  })
})

describe("search parameter schemas", () => {
  test("validates and normalizes route search values", () => {
    expect(pageSearchSchema.parse({ page: "2" })).toEqual({ page: 2 })
    expect(pageSearchSchema.parse({ page: "-1" })).toEqual({
      page: undefined,
    })
    expect(loginSearchSchema.parse({ returnTo: 2 })).toEqual({
      returnTo: undefined,
    })
    expect(
      channelVideosSearchSchema.parse({
        tab: "videos",
        page: "3",
        has_song_list: "true",
        limit: "50",
      }),
    ).toEqual({
      tab: "videos",
      page: 3,
      has_song_list: "true",
      limit: 50,
    })
    expect(
      songSearchSchema.parse({
        q: "  song  ",
        page: "1",
        type: "karaoke",
        date_from: "20260102",
        date_to: "invalid",
      }),
    ).toEqual({
      q: "song",
      page: 1,
      type: "karaoke",
      date_from: "20260102",
      date_to: undefined,
    })
  })

  test("serializes channel page and search filters", () => {
    expect(CHANNEL_PAGE_SIZES).toEqual([10, 20, 50])
    expect(toChannelVideosSearch({})).toEqual({
      tab: undefined,
      page: undefined,
      has_song_list: undefined,
      limit: undefined,
    })
    expect(
      toChannelVideosSearch({
        tab: "videos",
        page: 2,
        has_song_list: "false",
        limit: 20,
      }),
    ).toEqual({
      tab: "videos",
      page: 2,
      has_song_list: "false",
      limit: 20,
    })
    expect(toChannelVideosSearch({ limit: 999 }).limit).toBeUndefined()
    expect(resolveChannelPageSize(undefined)).toBe(10)
    expect(resolveChannelPageSize(50)).toBe(50)

    expect(parseChannelIds(undefined)).toEqual([])
    expect(parseChannelIds(" a, b, a, ,c ")).toEqual(["a", "b", "c"])
    expect(parseChannelIds(Array.from({ length: 30 }, (_, i) => i).join(",")))
      .toHaveLength(25)
    expect(serializeChannelIds(undefined)).toBeUndefined()
    expect(serializeChannelIds([" a ", "", "a", "b"])).toBe("a,b")
    expect(htmlDateToYyyymmdd("2026-07-29")).toBe("20260729")
    expect(htmlDateToYyyymmdd("20260729")).toBeUndefined()
    expect(yyyymmddToHtmlDate("20260729")).toBe("2026-07-29")
    expect(yyyymmddToHtmlDate("bad")).toBe("")
    expect(yyyymmddToHtmlDate(undefined)).toBe("")
  })
})

describe("date, locale, and class helpers", () => {
  beforeEach(() => setLocale("en", { reload: false }))

  test("sorts, formats, and annotates upload dates", () => {
    expect(compareUploadDateDesc(null, undefined)).toBe(0)
    expect(compareUploadDateDesc(null, "20260101")).toBe(1)
    expect(compareUploadDateDesc("20260101", null)).toBe(-1)
    expect(compareUploadDateDesc("20260101", "20260201")).toBeGreaterThan(0)
    expect(formatUploadDate("20260729")).toBe("2026-07-29")
    expect(formatUploadDate("2026-Q3")).toBe("2026-Q3")
    expect(formatUploadDate(" ")).toBeNull()
    expect(uploadDateTimeAttr("20260729", "exact")).toBe("2026-07-29")
    expect(uploadDateTimeAttr("20260729", "approximate")).toBeUndefined()
    expect(uploadDateTimeAttr(null, "exact")).toBeUndefined()

    expect(
      sortVideosByUploadDateDesc([
        { id: "b", upload_date: "20260101" },
        { id: "z", upload_date: null },
        { id: "a", upload_date: "20260101" },
        { id: "c", upload_date: "20260201" },
      ]).map((item) => item.id),
    ).toEqual(["c", "a", "b", "z"])
  })

  test("maps supported locales and formats values", () => {
    expect(currentIntlLocale()).toBe("en-US")
    expect(formatInteger(1234)).toMatch(/1,234/)
    expect(formatDateTime(new Date("2026-07-29T00:00:00Z"))).toContain("2026")
    setLocale("zh-hant", { reload: false })
    expect(currentIntlLocale()).toBe("zh-TW")
    setLocale("ja", { reload: false })
    expect(currentIntlLocale()).toBe("ja-JP")
  })

  test("merges Tailwind class names", () => {
    expect(cn("px-2", undefined, "px-4")).toBe("px-4")
  })
})

describe("YouTube helpers", () => {
  test.each([
    ["01:30", "https://youtube.test/watch?v=x&t=90s"],
    ["1:02:03", "https://youtube.test/watch?v=x&t=3723s"],
    ["bad", "https://youtube.test/watch?v=x"],
    ["1:60", "https://youtube.test/watch?v=x"],
    ["1:70:00", "https://youtube.test/watch?v=x"],
    ["-1:02", "https://youtube.test/watch?v=x"],
  ])("maps %s timestamps", (timestamp, expected) => {
    expect(
      youtubeUrlAtTimestamp("https://youtube.test/watch?v=x", timestamp),
    ).toBe(expected)
  })

  test("supports non-URL fallbacks and canonical assets", () => {
    expect(youtubeUrlAtTimestamp("not-a-url?x=1", "00:05")).toBe(
      "not-a-url?x=1&t=5s",
    )
    expect(youtubeUrlAtTimestamp("not-a-url", "00:05")).toBe(
      "not-a-url?t=5s",
    )
    expect(youtubeThumbnailUrl("id/x")).toContain("id%2Fx")
    expect(youtubeVideoUrl("id/x")).toContain("id%2Fx")
  })
})

describe("administrator route guards", () => {
  function guardArgs(session: unknown, href = "/status") {
    const api = createApiClient({
      fetch: vi.fn(async () => jsonResponse(session)),
    })
    return {
      context: { queryClient: new QueryClient(), api },
      location: { href },
    }
  }

  test("allows administrators and management-enabled administrators", async () => {
    const admin = {
      authenticated: true,
      role: "admin",
      username: "operator",
      csrf_token: "token",
      management_enabled: true,
    }
    await expect(requireAdminRoute(guardArgs(admin))).resolves.toBeUndefined()
    await expect(requireManagementRoute(guardArgs(admin))).resolves
      .toBeUndefined()
  })

  test("redirects anonymous and failed sessions to a safe login return URL", async () => {
    const anonymous = {
      authenticated: false,
      role: null,
      username: null,
      csrf_token: null,
      management_enabled: false,
    }
    for (const href of ["/status", "https://evil.test/"]) {
      try {
        await requireAdminRoute(guardArgs(anonymous, href))
        throw new Error("expected redirect")
      } catch (error) {
        expect(isRedirect(error)).toBe(true)
        expect((error as { options: { search: { returnTo: string } } }).options
          .search.returnTo).toBe(href.startsWith("/") ? href : "/")
      }
    }

    const failedApi = createApiClient({
      fetch: vi.fn(async () => jsonResponse({}, 500)),
    })
    await expect(
      requireAdminRoute({
        context: { queryClient: new QueryClient(), api: failedApi },
        location: { href: "/status" },
      }),
    ).rejects.toSatisfy(isRedirect)
  })

  test("redirects administrators without management access", async () => {
    try {
      await requireManagementRoute(
        guardArgs({
          authenticated: true,
          role: "admin",
          username: "viewer",
          csrf_token: "token",
          management_enabled: false,
        }),
      )
      throw new Error("expected redirect")
    } catch (error) {
      expect(isRedirect(error)).toBe(true)
      expect((error as { options: { to: string } }).options.to).toBe(
        "/channels",
      )
    }
  })

  test("delegates anonymous management access to the administrator guard", async () => {
    await expect(
      requireManagementRoute(
        guardArgs({
          authenticated: false,
          role: null,
          username: null,
          csrf_token: null,
          management_enabled: false,
        }),
      ),
    ).rejects.toSatisfy(isRedirect)
  })
})
