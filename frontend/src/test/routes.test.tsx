import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router"
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, test, vi } from "vitest"

import { ApiError, type ApiClient } from "@/api/client"
import { ApiProvider } from "@/api/provider"
import type {
  AuthSession,
  SetlistContributor,
  SongSearchResult,
  SummaryReport,
  UpdaterStatus,
  YouTubeChannel,
  YouTubeVideo,
} from "@/api/types"
import {
  CHANNEL_REQUEST_ISSUE_URL,
  DATA_REQUEST_ISSUE_URL,
} from "@/lib/public-config"
import { m } from "@/paraglide/messages"
import { routeTree } from "@/routeTree.gen"

const channel: YouTubeChannel = {
  id: "UC1",
  name: "Test Singer",
  url: "https://youtube.test/@singer",
  thumbnail_url: "https://images.test/channel.jpg",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
}

const video: YouTubeVideo = {
  id: "video1",
  title: "Karaoke Night",
  url: "https://youtube.test/watch?v=video1",
  channel_id: channel.id,
  upload_date: "20260720",
  upload_date_precision: "exact",
  type: "karaoke",
  has_song_list_comment: true,
  setlist_comment_author: "@helper",
  setlist_comment_author_id: "UC-helper",
  setlist_comment_id: "comment-1",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-21T00:00:00Z",
}

const song: SongSearchResult = {
  id: 1,
  title: "Test Song",
  timestamp: "01:23",
  video_id: video.id,
  video_url: "https://youtube.test/watch?v=video1&t=83s",
  video_title: video.title,
  channel_id: channel.id,
  channel_name: channel.name,
  analyzed_by_llm: true,
  setlist_comment_author: "@helper",
  setlist_comment_author_id: "UC-helper",
  setlist_comment_id: "comment-1",
  created_at: "2026-07-20T00:00:00Z",
  updated_at: "2026-07-21T00:00:00Z",
}

const contributor: SetlistContributor = {
  author: "@helper",
  author_id: "UC-helper",
  song_count: 42,
  video_count: 3,
}

const summary: SummaryReport = {
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
    comments: 10,
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
  songs: { total: 1, analyzed_by_llm: 1, contributors: 1 },
}

const updater: UpdaterStatus = {
  phase: "idle",
  detail: "Waiting",
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
  steady_scan_interval_seconds: 21600,
  backfill_page_size: 100,
  backfill_pages_per_cycle: 3,
  updated_at: "2026-07-29T00:00:00Z",
}

const adminSession: AuthSession = {
  authenticated: true,
  role: "admin",
  username: "operator",
  csrf_token: "csrf",
  management_enabled: true,
}

function makeApi(
  session: AuthSession = adminSession,
  overrides: Partial<ApiClient> = {},
) {
  return {
    health: vi.fn(async () => ({
      status: "healthy",
      version: "0.4.5",
      database: "ok",
      cache: "ok" as const,
    })),
    authSession: vi.fn(async () => session),
    login: vi.fn(async () => adminSession),
    logout: vi.fn(async () => ({
      ...session,
      authenticated: false,
      role: null,
    })),
    updaterStatus: vi.fn(async () => updater),
    summaryReport: vi.fn(async () => summary),
    recentUpdates: vi.fn(async () => ({
      channels: [channel],
      songs: [song],
    })),
    searchSongs: vi.fn(async (_q, limit, offset) => ({
      items: [song],
      total: 1,
      limit,
      offset,
    })),
    suggestSongs: vi.fn(async () => [
      { title: "Test Song", occurrences: 2 },
    ]),
    getSong: vi.fn(async () => song),
    listSetlistContributors: vi.fn(async (limit, offset) => ({
      items: [contributor],
      total: 1,
      limit,
      offset,
    })),
    listChannels: vi.fn(async (limit, offset) => ({
      items: [channel],
      total: 1,
      limit,
      offset,
    })),
    getChannel: vi.fn(async () => channel),
    createChannel: vi.fn(async () => channel),
    createChannelsBulk: vi.fn(async (urls: string[]) => ({
      items: urls.map((url) => ({
        url,
        status: "created" as const,
        channel_id: channel.id,
        channel_name: channel.name,
        message: "Created",
      })),
      created: urls.length,
      already_exists: 0,
      failed: 0,
      skipped: 0,
      max_batch_size: 10,
      cooldown_seconds: 30,
    })),
    listChannelVideos: vi.fn(async (_id, limit, offset) => ({
      items: [video],
      total: 1,
      limit,
      offset,
    })),
    refreshChannelVideos: vi.fn(async () => ({
      channel_id: channel.id,
      mode: "refresh",
      scraped: 1,
      deleted: 0,
      reclassified: 0,
      cleared: 0,
      message: "Queued",
    })),
    reloadVideoSongs: vi.fn(async () => ({
      video_id: video.id,
      song_count: 1,
      has_song_list_comment: true,
      analysis_status: "done",
      message: "Reloaded",
    })),
    listVideoSongs: vi.fn(async (_id, limit, offset) => ({
      items: [
        {
          id: 1,
          title: song.title,
          video_id: video.id,
          timestamp: song.timestamp,
          analyzed_by_llm: true,
          created_at: "2026-07-20T00:00:00Z",
          updated_at: "2026-07-21T00:00:00Z",
        },
      ],
      total: 1,
      limit,
      offset,
    })),
    getVideo: vi.fn(async () => video),
    ...overrides,
  } as unknown as ApiClient
}

const activeQueryClients: QueryClient[] = []

afterEach(() => {
  for (const client of activeQueryClients.splice(0)) {
    client.clear()
  }
})

async function renderRoute(path: string, api = makeApi()) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: Infinity,
        gcTime: Infinity,
      },
      mutations: { retry: false },
    },
  })
  activeQueryClients.push(queryClient)
  const history = createMemoryHistory({ initialEntries: [path] })
  const router = createRouter({
    routeTree,
    history,
    context: { queryClient, api },
    defaultPreload: false,
    scrollRestoration: false,
  })

  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ApiProvider>,
  )

  await act(async () => {
    await router.load()
  })
  await waitFor(() => expect(router.state.status).toBe("idle"))
  await waitFor(() => expect(queryClient.isFetching()).toBe(0))
  return { api, queryClient, router }
}

describe("application routes", () => {
  test.each([
    "/",
    "/search?q=Test%20Song",
    "/channels",
    "/updates",
    "/channels/UC1",
    "/songs/1",
    "/videos/video1",
    "/summary",
    "/status",
    "/channels/new",
    "/about",
    "/thanks",
    "/how-to-use",
    "/terms",
    "/privacy",
    "/copyright",
  ])("renders %s with application data", async (path) => {
    await renderRoute(path)
    expect(document.querySelector("#main-content")?.textContent?.length)
      .toBeGreaterThan(20)
    expect(document.title).toContain("Setlist")
  })

  test("credits the YouTube setlist author on song and thanks pages", async () => {
    await renderRoute("/songs/1")
    expect(screen.getAllByText("@helper").length).toBeGreaterThan(0)

    await renderRoute("/thanks")
    expect(screen.getByText(m.thanks_heading())).toBeInTheDocument()
    expect(screen.getAllByText("@helper").length).toBeGreaterThan(1)
    expect(screen.getByText("42")).toBeInTheDocument()
  })

  test("shows the contributor total in the collection summary", async () => {
    await renderRoute("/summary")

    const label = screen.getByText(m.summary_contributors())
    expect(within(label.parentElement!).getByText("1")).toBeInTheDocument()
  })

  test("paginates tracked channels through the URL and API offset", async () => {
    const channels = Array.from({ length: 21 }, (_, index) => ({
      ...channel,
      id: `UC${index + 1}`,
      name: `Test Singer ${index + 1}`,
    }))
    const listChannels = vi.fn(async (limit: number, offset: number) => ({
      items: channels.slice(offset, offset + limit),
      total: channels.length,
      limit,
      offset,
    }))
    const api = makeApi(adminSession, { listChannels })
    const { router } = await renderRoute("/channels", api)

    expect(listChannels).toHaveBeenCalledWith(20, 0, undefined)
    await userEvent.click(
      screen.getByRole("button", { name: m.pagination_next() }),
    )

    await waitFor(() =>
      expect(listChannels).toHaveBeenCalledWith(20, 20, undefined),
    )
    expect(router.state.location.search).toMatchObject({ page: 1 })
    expect(screen.getByText("Test Singer 21")).toBeInTheDocument()
  })

  test("searches tracked channels by URL query and resets pagination", async () => {
    const listChannels = vi.fn(
      async (limit: number, offset: number, query?: string) => ({
        items: query ? [{ ...channel, name: "Matched Singer" }] : [channel],
        total: 1,
        limit,
        offset,
      }),
    )
    const { router } = await renderRoute(
      "/channels?page=3",
      makeApi(adminSession, { listChannels }),
    )

    const input = screen.getByRole("searchbox", {
      name: m.channels_search_label(),
    })
    await userEvent.type(input, "Singer %_")
    await userEvent.click(
      screen.getByRole("button", { name: m.channels_search_submit() }),
    )

    await waitFor(() =>
      expect(listChannels).toHaveBeenCalledWith(20, 0, "Singer %_"),
    )
    expect(router.state.location.search).toMatchObject({ q: "Singer %_" })
    expect(router.state.location.search).not.toHaveProperty("page")
    expect(screen.getByText("Matched Singer")).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole("button", { name: m.channels_search_clear() }),
    )
    await waitFor(() => expect(router.state.location.search).toEqual({}))
  })

  test("shows fixed recent channel and song sections", async () => {
    const recentUpdates = vi.fn(async () => ({
      channels: [channel],
      songs: [song],
    }))
    await renderRoute(
      "/updates",
      makeApi(adminSession, { recentUpdates }),
    )

    expect(recentUpdates).toHaveBeenCalledOnce()
    expect(
      screen.getByRole("heading", { name: m.recent_channels_heading() }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("heading", { name: m.recent_songs_heading() }),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/2026/).length).toBeGreaterThan(0)
  })

  test("links guest channel requests to the dedicated issue form", async () => {
    await renderRoute(
      "/channels",
      makeApi({
        authenticated: false,
        role: null,
        username: null,
        csrf_token: null,
        management_enabled: false,
      }),
    )

    const requestLinks = screen.getAllByRole("link", {
      name: m.channel_request_contact_cta(),
    })
    expect(requestLinks).toHaveLength(2)
    for (const link of requestLinks) {
      expect(link).toHaveAttribute("href", CHANNEL_REQUEST_ISSUE_URL)
    }
  })

  test.each([
    ["/privacy", m.info_contact_link()],
    ["/copyright", m.copyright_request_link()],
  ])("links %s requests to the correction form", async (path, linkName) => {
    await renderRoute(path)

    expect(screen.getByRole("link", { name: linkName })).toHaveAttribute(
      "href",
      DATA_REQUEST_ISSUE_URL,
    )
  })

  test("renders the login route for an anonymous visitor", async () => {
    await renderRoute(
      "/admin/login?returnTo=%2Fstatus",
      makeApi({
        authenticated: false,
        role: null,
        username: null,
        csrf_token: null,
        management_enabled: false,
      }),
    )
    expect(document.querySelector("input[name='username']")).not.toBeNull()
    expect(document.querySelector("input[name='password']")).not.toBeNull()
  })

  test.each([
    [429, m.auth_rate_limited()],
    [503, m.auth_not_configured()],
    [401, m.auth_invalid()],
  ])("maps login failure %s to a safe public error", async (status, message) => {
    const api = makeApi(
      {
        authenticated: false,
        role: null,
        username: null,
        csrf_token: null,
        management_enabled: false,
      },
      {
        login: vi.fn(async () => {
          throw new ApiError(status, "login failed")
        }),
      },
    )
    await renderRoute("/admin/login?returnTo=%2Fstatus", api)
    await userEvent.type(
      screen.getByLabelText(m.auth_username()),
      " operator ",
    )
    await userEvent.type(screen.getByLabelText(m.auth_password()), "secret")
    await userEvent.click(
      screen.getByRole("button", { name: m.auth_sign_in() }),
    )
    expect(await screen.findByRole("alert")).toHaveTextContent(message)
    expect(screen.getByLabelText(m.auth_password())).toHaveValue("")
  })

  test("submits bulk channels and renders every result status", async () => {
    const statuses = [
      "created",
      "already_exists",
      "invalid",
      "skipped",
      "failed",
    ] as const
    const api = makeApi(adminSession, {
      createChannelsBulk: vi.fn(async (urls: string[]) => ({
        items: statuses.map((status, index) => ({
          url: urls[index] ?? `https://youtube.test/${index}`,
          status,
          channel_id: status === "created" ? `UC${index}` : null,
          channel_name: status === "created" ? `Channel ${index}` : null,
          message: status,
        })),
        created: 1,
        already_exists: 1,
        failed: 2,
        skipped: 1,
        max_batch_size: 10,
        cooldown_seconds: 30,
      })),
    })
    await renderRoute("/channels/new", api)
    const textarea = screen.getByLabelText(m.channel_add_url_label())
    const urls = statuses.map(
      (_, index) => `https://youtube.test/${index}`,
    )
    await userEvent.type(textarea, urls.join("\n"))
    await userEvent.click(
      screen.getByRole("button", { name: m.channel_add_submit() }),
    )
    await waitFor(() =>
      expect(api.createChannelsBulk).toHaveBeenCalledWith(urls),
    )
    expect(screen.getByText(m.channel_add_status_created()))
      .toBeInTheDocument()
    expect(screen.getByText(m.channel_add_status_existing()))
      .toBeInTheDocument()
    expect(screen.getByText(m.channel_add_status_invalid()))
      .toBeInTheDocument()
    expect(screen.getByText(m.channel_add_status_skipped()))
      .toBeInTheDocument()
    expect(screen.getByText(m.channel_add_status_failed()))
      .toBeInTheDocument()
  })

  test("validates oversized bulk input and maps unexpected failures", async () => {
    const api = makeApi(adminSession, {
      createChannelsBulk: vi.fn(async () => {
        throw new Error("offline")
      }),
    })
    await renderRoute("/channels/new", api)
    const textarea = screen.getByLabelText(m.channel_add_url_label())
    const form = textarea.closest("form")
    expect(form).not.toBeNull()
    fireEvent.change(textarea, {
      target: {
        value: Array.from(
          { length: 11 },
          (_, index) => `https://youtube.test/${index}`,
        ).join("\n"),
      },
    })
    fireEvent.submit(form!)
    expect(await screen.findByRole("alert")).toHaveTextContent(
      m.channel_add_too_many({ count: 11, max: 10 }),
    )

    fireEvent.change(textarea, {
      target: { value: "https://youtube.test/ok" },
    })
    fireEvent.submit(form!)
    expect(await screen.findByRole("alert")).toHaveTextContent(
      m.channel_add_failed(),
    )
  })

  test("updates search query, filters, and result pages in the URL", async () => {
    const api = makeApi(adminSession, {
      searchSongs: vi.fn(async (_q, limit, offset) => ({
        items: [song],
        total: 50,
        limit,
        offset,
      })),
    })
    const { router } = await renderRoute("/search?q=Test", api)
    await userEvent.click(screen.getByLabelText(m.pagination_next()))
    await waitFor(() =>
      expect(router.state.location.search.page).toBe(1),
    )

    const searchInput = screen.getByLabelText(m.search_placeholder())
    await userEvent.clear(searchInput)
    await userEvent.type(searchInput, "Another{Enter}")
    await waitFor(() =>
      expect(router.state.location.search.q).toBe("Another"),
    )

    await userEvent.click(
      screen.getByRole("button", { name: m.search_filters_show() }),
    )
    await userEvent.click(
      screen.getByRole("button", { name: m.search_type_song() }),
    )
    await waitFor(() =>
      expect(router.state.location.search.type).toBe("song"),
    )
  })

  test("updates channel filters, page size, and refreshes the catalog", async () => {
    const api = makeApi()
    const { router } = await renderRoute("/channels/UC1", api)

    await userEvent.click(
      screen.getByRole("button", { name: m.setlist_filter_no() }),
    )
    await waitFor(() =>
      expect(router.state.location.search.has_song_list).toBe("false"),
    )
    expect(api.listChannelVideos).toHaveBeenLastCalledWith(
      channel.id,
      10,
      0,
      "karaoke",
      false,
    )

    await userEvent.selectOptions(
      screen.getByLabelText(m.pagination_page_size_label()),
      "20",
    )
    await waitFor(() => expect(router.state.location.search.limit).toBe(20))

    await userEvent.click(
      screen.getByRole("tab", { name: m.channel_tab_videos() }),
    )
    await waitFor(() => expect(router.state.location.search.tab).toBe("videos"))
    expect(router.state.location.search.has_song_list).toBeUndefined()

    await userEvent.click(
      screen.getByRole("button", { name: m.reload_list() }),
    )
    await waitFor(() =>
      expect(api.refreshChannelVideos).toHaveBeenCalledWith(channel.id),
    )
    expect(
      screen.getByRole("button", { name: m.reload_done() }),
    ).toBeInTheDocument()
  })

  test("shows a safe channel refresh failure and keeps filters usable", async () => {
    const api = makeApi(adminSession, {
      refreshChannelVideos: vi.fn(async () => {
        throw "upstream details"
      }),
      listChannelVideos: vi.fn(async (_id, limit, offset) => ({
        items: [],
        total: 0,
        limit,
        offset,
      })),
    })
    await renderRoute("/channels/UC1?has_song_list=%22true%22", api)
    expect(screen.getByText(m.karaoke_empty_with_setlist())).toBeInTheDocument()

    await userEvent.click(
      screen.getByRole("button", { name: m.reload_list() }),
    )
    expect(
      await screen.findByRole("button", { name: m.reload_failed() }),
    ).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent(m.reload_failed())
  })

  test("reloads a karaoke video's songs and links timestamped results", async () => {
    const api = makeApi()
    await renderRoute("/videos/video1", api)

    expect(
      screen.getByRole("link", {
        name: m.play_from_timestamp({ timestamp: song.timestamp! }),
      }),
    ).toHaveAttribute("href", song.video_url)
    await userEvent.click(
      screen.getByRole("button", { name: m.song_reload_action() }),
    )
    await waitFor(() =>
      expect(api.reloadVideoSongs).toHaveBeenCalledWith(video.id),
    )
    expect(
      screen.getByRole("button", { name: m.song_reload_done() }),
    ).toBeInTheDocument()
    expect(screen.getByText(m.song_reload_summary({ count: "1" })))
      .toBeInTheDocument()
  })

  test("does not request a setlist for standalone song uploads", async () => {
    const listVideoSongs = vi.fn()
    await renderRoute(
      "/videos/video1",
      makeApi(adminSession, {
        getVideo: vi.fn(async () => ({
          ...video,
          type: "song",
          has_song_list_comment: false,
          upload_date: null,
          upload_date_precision: null,
        })),
        listVideoSongs,
      }),
    )
    expect(screen.getByText(m.video_song_no_setlist())).toBeInTheDocument()
    expect(listVideoSongs).not.toHaveBeenCalled()
    expect(
      screen.queryByRole("button", { name: m.song_reload_action() }),
    ).not.toBeInTheDocument()
  })

  test("renders invalid song ids as not found without requesting data", async () => {
    const getSong = vi.fn()
    await renderRoute("/songs/not-a-number", makeApi(adminSession, { getSong }))
    expect(screen.getByText(m.song_not_found())).toBeInTheDocument()
    expect(getSong).not.toHaveBeenCalled()
  })

  test("submits only non-empty home searches", async () => {
    const { router } = await renderRoute("/")
    const input = screen.getByLabelText(m.search_placeholder())
    await userEvent.type(input, "   {Enter}")
    expect(router.state.location.pathname).toBe("/")

    await userEvent.clear(input)
    await userEvent.type(input, "  Test Song  {Enter}")
    await waitFor(() => expect(router.state.location.pathname).toBe("/search"))
    expect(router.state.location.search.q).toBe("Test Song")
  })

  test("shows retry behavior for failed route queries", async () => {
    const searchSongs = vi.fn(async () => {
      throw new Error("offline")
    })
    await renderRoute(
      "/search?q=Test",
      makeApi(adminSession, { searchSongs }),
    )
    const retry = await screen.findByRole("button", {
      name: m.error_retry(),
    })
    await userEvent.click(retry)
    await waitFor(() => expect(searchSongs.mock.calls.length).toBeGreaterThan(1))
  })

  test("renders warning and short-duration status branches", async () => {
    await renderRoute(
      "/status",
      makeApi(adminSession, {
        updaterStatus: vi.fn(async () => ({
          ...updater,
          phase: "cooldown",
          detail: null,
          channel_id: null,
          channel_name: "Name only",
          video_id: "video1",
          video_title: null,
          cycle_started_at: "invalid",
          last_cycle_finished_at: null,
          persistent_heartbeat_at: null,
          persistent_last_success_at: null,
          last_error: "redacted error",
          is_stalled: true,
          heartbeat_stale_seconds: 61,
          youtube_cooldown_remaining_seconds: 30,
          update_interval_seconds: 30,
          steady_scan_interval_seconds: 3600,
          is_cycle_active: true,
          background_updater_enabled: false,
        })),
      }),
    )
    expect(screen.getAllByRole("alert")).toHaveLength(2)
    expect(screen.getByText("redacted error")).toBeInTheDocument()
  })

  test("renders zero and warning summary branches", async () => {
    await renderRoute(
      "/summary",
      makeApi(adminSession, {
        summaryReport: vi.fn(async () => ({
          ...summary,
          generated_at: "invalid",
          backfill: { pending: 0, running: 0, done: 0, failed: 1 },
          videos: {
            ...summary.videos,
            karaoke: 0,
            date_unknown: 1,
            latest_discovered_at: null,
          },
          analysis: {
            ...summary.analysis,
            attempted: 10,
            with_setlist: 20,
            latest_analyzed_at: null,
          },
        })),
      }),
    )
    expect(screen.getAllByRole("progressbar")).toHaveLength(2)
  })

  test("renders the localized not-found boundary", async () => {
    await renderRoute("/missing-page")

    expect(
      screen.getByRole("heading", { name: m.not_found_heading() }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: m.not_found_home() }),
    ).toHaveAttribute("href", "/")
  })
})
