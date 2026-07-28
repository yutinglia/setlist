import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { PropsWithChildren } from "react"
import { beforeEach, describe, expect, test, vi } from "vitest"

import type { ApiClient } from "@/api/client"
import {
  PAGE_SIZE,
  SONG_SUGGESTION_LIMIT,
  authSessionQueryKey,
  authSessionQueryOptions,
  useAuthSession,
  useChannel,
  useChannelOptions,
  useChannelVideos,
  useChannels,
  useCreateChannel,
  useCreateChannelsBulk,
  useHealth,
  useLogin,
  useLogout,
  useSong,
  useSongSearch,
  useSongSuggestions,
  useSummaryReport,
  useUpdaterStatus,
  useVideo,
  useVideoSongs,
} from "@/api/hooks"
import { ApiProvider } from "@/api/provider"
import { useApi } from "@/api/context"

const adminSession = {
  authenticated: true,
  role: "admin" as const,
  username: "operator",
  csrf_token: "csrf",
  management_enabled: true,
}

function makeApi(overrides: Partial<ApiClient> = {}) {
  return {
    health: vi.fn(async () => ({ status: "healthy" })),
    authSession: vi.fn(async () => adminSession),
    login: vi.fn(async () => adminSession),
    logout: vi.fn(async () => ({
      ...adminSession,
      authenticated: false,
      role: null,
    })),
    updaterStatus: vi.fn(async () => ({ phase: "idle" })),
    summaryReport: vi.fn(async () => ({ channels: 1 })),
    searchSongs: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: PAGE_SIZE,
      offset: 0,
    })),
    suggestSongs: vi.fn(async () => []),
    getSong: vi.fn(async () => ({ id: 7 })),
    listChannels: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: PAGE_SIZE,
      offset: 0,
    })),
    getChannel: vi.fn(async () => ({ id: "UC1" })),
    createChannel: vi.fn(async () => ({ id: "UC1" })),
    createChannelsBulk: vi.fn(async () => ({ items: [] })),
    listChannelVideos: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    })),
    refreshChannelVideos: vi.fn(async () => ({ channel_id: "UC1" })),
    reloadVideoSongs: vi.fn(async () => ({ video_id: "video1" })),
    listVideoSongs: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: PAGE_SIZE,
      offset: 0,
    })),
    getVideo: vi.fn(async () => ({ id: "video1" })),
    ...overrides,
  } as unknown as ApiClient
}

function harness(api: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
  function Wrapper({ children }: PropsWithChildren) {
    return (
      <ApiProvider client={api}>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </ApiProvider>
    )
  }
  return { queryClient, Wrapper }
}

describe("API context and query hooks", () => {
  beforeEach(() => vi.clearAllMocks())

  test("requires an API provider", () => {
    const { result } = renderHook(() => {
      try {
        return useApi()
      } catch (error) {
        return error
      }
    })
    expect(result.current).toEqual(
      new Error("ApiProvider is not configured"),
    )
  })

  test("builds auth query options", async () => {
    const api = makeApi()
    const options = authSessionQueryOptions(api)
    expect(options.queryKey).toEqual(authSessionQueryKey)
    await expect(options.queryFn?.({} as never)).resolves.toEqual(
      adminSession,
    )
  })

  test("runs every enabled read query with normalized arguments", async () => {
    const api = makeApi()
    const { Wrapper } = harness(api)
    const { result } = renderHook(
      () => ({
        auth: useAuthSession(),
        health: useHealth(),
        updater: useUpdaterStatus(),
        summary: useSummaryReport(),
        search: useSongSearch("hello", 2, {
          channelIds: ["UC1"],
          type: "karaoke",
          uploadDateFrom: "20260101",
          uploadDateTo: "20261231",
        }),
        suggestions: useSongSuggestions("  hello  ", {
          channelIds: ["UC2"],
          type: "song",
          uploadDateFrom: "20250101",
          uploadDateTo: "20251231",
        }),
        channelOptions: useChannelOptions(),
        song: useSong(7),
        channels: useChannels(2),
        channel: useChannel("UC1"),
        videos: useChannelVideos("UC1", 2, "karaoke", true, 10),
        video: useVideo("video1"),
        videoSongs: useVideoSongs("video1", 3),
      }),
      { wrapper: Wrapper },
    )

    await waitFor(() => {
      expect(
        Object.values(result.current).every(
          (query) => query.isSuccess,
        ),
      ).toBe(true)
    })

    expect(api.searchSongs).toHaveBeenCalledWith("hello", PAGE_SIZE, 40, {
      channelIds: ["UC1"],
      type: "karaoke",
      uploadDateFrom: "20260101",
      uploadDateTo: "20261231",
    })
    expect(api.suggestSongs).toHaveBeenCalledWith(
      "hello",
      SONG_SUGGESTION_LIMIT,
      {
        channelIds: ["UC2"],
        type: "song",
        uploadDateFrom: "20250101",
        uploadDateTo: "20251231",
      },
      expect.any(AbortSignal),
    )
    expect(api.listChannels).toHaveBeenCalledWith(PAGE_SIZE, 40)
    expect(api.listChannels).toHaveBeenCalledWith(100, 0)
    expect(api.listChannelVideos).toHaveBeenCalledWith(
      "UC1",
      10,
      20,
      "karaoke",
      true,
    )
    expect(api.listVideoSongs).toHaveBeenCalledWith(
      "video1",
      PAGE_SIZE,
      60,
    )
  })

  test("keeps invalid or explicitly disabled queries idle", async () => {
    const api = makeApi({
      authSession: vi.fn(async () => ({
        authenticated: false,
        role: null,
        username: null,
        csrf_token: null,
        management_enabled: false,
      })),
    })
    const { Wrapper } = harness(api)
    const { result } = renderHook(
      () => ({
        updater: useUpdaterStatus(),
        search: useSongSearch("  ", 0),
        suggestionsShort: useSongSuggestions("x"),
        suggestionsDisabled: useSongSuggestions("ready", {}, {
          enabled: false,
        }),
        songZero: useSong(0),
        songFloat: useSong(1.5),
        channel: useChannel(""),
        videos: useChannelVideos("", 0, "song", undefined, 20),
        video: useVideo(""),
        songs: useVideoSongs("", 0),
        songsDisabled: useVideoSongs("video1", 0, { enabled: false }),
      }),
      { wrapper: Wrapper },
    )

    await waitFor(() => expect(result.current.updater.fetchStatus).toBe("idle"))
    expect(api.updaterStatus).not.toHaveBeenCalled()
    expect(api.searchSongs).not.toHaveBeenCalled()
    expect(api.suggestSongs).not.toHaveBeenCalled()
    expect(api.getSong).not.toHaveBeenCalled()
    expect(api.getChannel).not.toHaveBeenCalled()
    expect(api.listChannelVideos).not.toHaveBeenCalled()
    expect(api.getVideo).not.toHaveBeenCalled()
    expect(api.listVideoSongs).not.toHaveBeenCalled()
  })

  test("runs mutations and updates or invalidates cached state", async () => {
    const api = makeApi()
    const { queryClient, Wrapper } = harness(api)
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    queryClient.setQueryData(["updater", "status"], { phase: "idle" })
    const { result } = renderHook(
      () => ({
        login: useLogin(),
        logout: useLogout(),
        create: useCreateChannel(),
        bulk: useCreateChannelsBulk(),
      }),
      { wrapper: Wrapper },
    )

    await act(() =>
      result.current.login.mutateAsync({
        username: "operator",
        password: "secret",
      }),
    )
    expect(queryClient.getQueryData(authSessionQueryKey)).toEqual(adminSession)

    await act(() =>
      result.current.create.mutateAsync("https://youtube.test/@one"),
    )
    await act(() =>
      result.current.bulk.mutateAsync([
        "https://youtube.test/@one",
        "https://youtube.test/@two",
      ]),
    )
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["channels"] })
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["channels", "options"],
    })

    await act(() => result.current.logout.mutateAsync())
    expect(queryClient.getQueryData(["updater", "status"])).toBeUndefined()
    expect(api.login).toHaveBeenCalledWith("operator", "secret")
    expect(api.logout).toHaveBeenCalled()
  })
})
