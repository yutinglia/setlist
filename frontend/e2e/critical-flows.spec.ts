import { expect, test, type Page, type Route } from "@playwright/test"

const channel = {
  id: "UC1",
  name: "Test Singer",
  url: "https://www.youtube.com/@test-singer",
  thumbnail_url: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-07-29T00:00:00Z",
}

const video = {
  id: "video-1",
  title: "Karaoke Night",
  url: "https://www.youtube.com/watch?v=video-1",
  channel_id: channel.id,
  upload_date: "20260720",
  upload_date_precision: "exact",
  type: "karaoke",
  has_song_list_comment: true,
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-21T00:00:00Z",
}

const song = {
  id: 1,
  title: "Test Song",
  timestamp: "01:23",
  video_id: video.id,
  video_url: "https://www.youtube.com/watch?v=video-1&t=83s",
  video_title: video.title,
  channel_id: channel.id,
  channel_name: channel.name,
  analyzed_by_llm: false,
  setlist_comment_author: null,
  setlist_comment_author_id: null,
  setlist_comment_id: null,
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-21T00:00:00Z",
}

const summary = {
  generated_at: "2026-07-29T00:00:00Z",
  channels: 1,
  backfill: { pending: 0, running: 0, done: 1, failed: 0 },
  videos: {
    total: 1,
    karaoke: 1,
    song: 0,
    other: 0,
    with_list_snapshot: 1,
    with_metadata_snapshot: 1,
    date_unknown: 0,
    date_approximate: 0,
    date_exact: 1,
    latest_discovered_at: "2026-07-20T00:00:00Z",
  },
  analysis: {
    attempted: 1,
    with_setlist: 1,
    videos_with_comments: 1,
    comments: 1,
    latest_analyzed_at: "2026-07-21T00:00:00Z",
    status: {
      pending: 0,
      retry: 0,
      no_setlist: 0,
      done: 1,
      exhausted: 0,
      skipped: 0,
    },
  },
  songs: { total: 1, analyzed_by_llm: 0, contributors: 1 },
}

const updaterStatus = {
  phase: "idle",
  detail: "Waiting for the next cycle",
  channel_id: null,
  channel_name: null,
  video_id: null,
  video_title: null,
  cycle_started_at: null,
  last_cycle_finished_at: "2026-07-29T00:00:00Z",
  last_error: null,
  persistent_cycle_started_at: null,
  persistent_cycle_finished_at: "2026-07-29T00:00:00Z",
  persistent_last_success_at: "2026-07-29T00:00:00Z",
  persistent_heartbeat_at: "2026-07-29T00:00:00Z",
  persistent_outcome: "success",
  persistent_owner_id: null,
  is_stalled: false,
  heartbeat_stale_seconds: 0,
  comment_scrapes_this_cycle: 0,
  comment_scrape_cap: 10,
  is_cycle_active: false,
  background_updater_enabled: true,
  youtube_cooldown_remaining_seconds: 0,
  update_interval_seconds: 300,
  steady_scan_interval_seconds: 21_600,
  backfill_page_size: 100,
  backfill_pages_per_cycle: 3,
  updated_at: "2026-07-29T00:00:00Z",
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}

async function installApiStub(page: Page) {
  let authenticated = false

  await page.route("**/v1/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (path === "/v1/auth/session") {
      return json(route, {
        authenticated,
        role: authenticated ? "admin" : null,
        username: authenticated ? "operator" : null,
        csrf_token: authenticated ? "csrf-e2e" : null,
        management_enabled: authenticated,
      })
    }
    if (path === "/v1/auth/login" && request.method() === "POST") {
      authenticated = true
      return json(route, {
        authenticated: true,
        role: "admin",
        username: "operator",
        csrf_token: "csrf-e2e",
        management_enabled: true,
      })
    }
    if (path === "/v1/report/summary") return json(route, summary)
    if (path === "/v1/updater/status") return json(route, updaterStatus)
    if (path === "/v1/songs/search") {
      return json(route, {
        items: url.searchParams.get("q") ? [song] : [],
        total: url.searchParams.get("q") ? 1 : 0,
        limit: Number(url.searchParams.get("limit")),
        offset: Number(url.searchParams.get("offset")),
      })
    }
    if (path === "/v1/songs/suggestions") {
      return json(route, [{ title: song.title, occurrences: 1 }])
    }
    if (path === "/v1/songs/1") return json(route, song)
    if (path === "/v1/updates/recent") {
      return json(route, { channels: [channel], songs: [song] })
    }
    if (path === "/v1/channels") {
      return json(route, { items: [channel], total: 1, limit: 100, offset: 0 })
    }
    if (path === `/v1/channels/${channel.id}`) return json(route, channel)
    if (path === `/v1/videos/${video.id}`) return json(route, video)
    if (path === `/v1/videos/${video.id}/songs`) {
      return json(route, {
        items: [
          {
            id: song.id,
            title: song.title,
            video_id: song.video_id,
            timestamp: song.timestamp,
            analyzed_by_llm: false,
            created_at: "2026-07-20T00:00:00Z",
            updated_at: "2026-07-21T00:00:00Z",
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      })
    }

    return json(route, { detail: `Unhandled E2E API route: ${path}` }, 404)
  })
}

async function expectNoHorizontalOverflow(page: Page) {
  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }))
  expect(widths.scroll).toBeLessThanOrEqual(widths.client)
}

test.beforeEach(async ({ page }) => {
  await installApiStub(page)
})

test("searches from the home page and opens a song detail", async ({ page }) => {
  await page.goto("/")

  await expect(
    page.locator(
      'meta[name="theme-color"][media="(prefers-color-scheme: light)"]',
    ),
  ).toHaveAttribute("content", "#f6f7fb")
  await expect(
    page.locator(
      'meta[name="theme-color"][media="(prefers-color-scheme: dark)"]',
    ),
  ).toHaveAttribute("content", "#0a0f1e")

  await expect(
    page.getByRole("heading", { name: "Start with a channel" }),
  ).toBeVisible()
  await expect(page.getByText(channel.name).first()).toBeVisible()

  await page.getByRole("combobox", { name: "Search a song title…" }).fill(
    "Test Song",
  )
  await page.getByRole("combobox", { name: "Search a song title…" }).press(
    "Enter",
  )

  await expect(page).toHaveURL(/\/search\?.*q=Test(?:\+|%20)Song/)
  const result = page.locator(".media-card").filter({ hasText: "Test Song" })
  await expect(result).toContainText("Test Singer")
  await result.getByRole("link", { name: "Details" }).click()

  await expect(page).toHaveURL(/\/songs\/1$/)
  await expect(
    page.getByRole("heading", { level: 1, name: "Test Song" }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Open on YouTube" }).last(),
  ).toHaveAttribute("href", song.video_url)
})

test("renders a video setlist with a timestamped YouTube link", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await page.goto(`/videos/${video.id}`)

  await expect(
    page.getByRole("heading", { level: 1, name: video.title }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Setlist songs" }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: `Play from ${song.timestamp}` }),
  ).toHaveAttribute("href", song.video_url)
  await expectNoHorizontalOverflow(page)
})

test("searches channels and browses recent catalog updates", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await page.goto("/channels")

  await page.getByRole("searchbox", { name: "Search channels" }).fill(
    "Test Singer",
  )
  await page
    .getByRole("search", { name: "Search channels" })
    .getByRole("button", { name: "Search" })
    .click()
  await expect(page).toHaveURL(/\/channels\?.*q=Test(?:\+|%20)Singer/)
  await expect(page.getByText(channel.name)).toBeVisible()

  await page.getByRole("link", { name: "Recent" }).click()
  await expect(page).toHaveURL(/\/updates$/)
  await expect(
    page.getByRole("heading", { level: 1, name: "Recent updates" }),
  ).toBeVisible()
  await expect(page.getByText(song.title)).toBeVisible()
  await expect(page.getByText(channel.name).first()).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test("redirects a guest to login before showing administrator status", async ({
  page,
}) => {
  await page.goto("/status")

  await expect(page).toHaveURL(/\/admin\/login\?/)
  await page.getByLabel("Username").fill(" operator ")
  await page.getByLabel("Password").fill("secret")
  await page.getByRole("button", { name: "Admin sign in" }).click()

  await expect(page).toHaveURL(/\/status$/)
  await expect(
    page.getByRole("heading", { level: 1, name: "Updater status" }),
  ).toBeVisible()
  await expect(page.getByText("Waiting for the next cycle")).toBeVisible()

  for (const width of [1440, 1280, 1024]) {
    await page.setViewportSize({ width, height: 720 })
    const headerNav = page
      .locator("header")
      .getByRole("navigation", { name: "Navigation" })
    await expect(
      headerNav.getByRole("link", { name: "Status" }),
    ).toBeInViewport()
    await expectNoHorizontalOverflow(page)
  }

  await page.setViewportSize({ width: 375, height: 740 })
  const bottomNav = page.locator("nav.fixed").filter({ hasText: "Home" })
  await expect(bottomNav).toBeVisible()
  const touchTargets = await bottomNav.getByRole("link").evaluateAll((links) =>
    links.map((link) => link.getBoundingClientRect().height),
  )
  expect(touchTargets.every((height) => height >= 44)).toBe(true)

  await page.getByRole("button", { name: "Open navigation" }).click()
  await expect(page.getByRole("link", { name: "Status" })).toBeVisible()
  await page.getByRole("button", { name: "Close navigation" }).click()
})
