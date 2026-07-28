import { describe, expect, test, vi } from "vitest"

import { ApiError, createApiClient } from "@/api/client"

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

describe("createApiClient", () => {
  test("injects base URL and fetch implementation", async () => {
    const fetch = vi.fn(async () =>
      jsonResponse({ status: "healthy", version: "v1", database: "ok" }),
    )
    const client = createApiClient({
      baseUrl: "https://api.example.test/",
      fetch,
    })

    await client.health()

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.test/v1/health",
      expect.objectContaining({ credentials: "include" }),
    )
  })

  test("keeps CSRF state inside each injected client instance", async () => {
    const firstFetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          authenticated: true,
          role: "admin",
          username: "operator",
          csrf_token: "csrf-one",
          management_enabled: true,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: "UC-test",
          name: "Test",
          url: "https://www.youtube.com/@test",
        }),
      )
    const secondFetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(
        jsonResponse({
          id: "UC-other",
          name: "Other",
          url: "https://www.youtube.com/@other",
        }),
      )
    const first = createApiClient({ fetch: firstFetch })
    const second = createApiClient({ fetch: secondFetch })

    await first.authSession()
    await first.createChannel("https://www.youtube.com/@test")
    await second.createChannel("https://www.youtube.com/@other")

    const firstMutation = firstFetch.mock.calls[1]?.[1]
    const secondMutation = secondFetch.mock.calls[0]?.[1]
    expect(new Headers(firstMutation?.headers).get("X-CSRF-Token")).toBe(
      "csrf-one",
    )
    expect(new Headers(secondMutation?.headers).has("X-CSRF-Token")).toBe(false)
  })

  test("maps API detail responses to ApiError", async () => {
    const client = createApiClient({
      fetch: vi.fn(async () => jsonResponse({ detail: "not allowed" }, 403)),
    })

    await expect(client.createChannel("invalid")).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: "ApiError",
        status: 403,
        message: "not allowed",
      }),
    )
  })

  test("maps validation arrays, status text, and non-JSON errors", async () => {
    const validation = createApiClient({
      fetch: vi.fn(async () =>
        jsonResponse(
          { detail: [{ msg: "first" }, "second"] },
          422,
        ),
      ),
    })
    await expect(validation.health()).rejects.toThrow("first; second")

    const statusText = createApiClient({
      fetch: vi.fn(async () =>
        new Response("not json", {
          status: 502,
          statusText: "Bad Gateway",
        }),
      ),
    })
    await expect(statusText.health()).rejects.toThrow("Bad Gateway")

    const unknownDetail = createApiClient({
      fetch: vi.fn(async () =>
        new Response(JSON.stringify({ detail: { reason: "hidden" } }), {
          status: 409,
          statusText: "Conflict",
          headers: { "Content-Type": "application/json" },
        }),
      ),
    })
    await expect(unknownDetail.health()).rejects.toThrow("Conflict")
  })

  test("covers every read endpoint and encoded query parameter", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        jsonResponse({}),
    )
    const client = createApiClient({ baseUrl: "/api///", fetch })

    await client.updaterStatus()
    await client.summaryReport()
    await client.searchSongs("song name", 20, 40, {
      channelIds: ["UC one", "UC/two"],
      type: "karaoke",
      uploadDateFrom: "20260101",
      uploadDateTo: "20261231",
    })
    const controller = new AbortController()
    await client.suggestSongs(
      "song",
      8,
      {
        channelIds: ["UC1"],
        type: "song",
        uploadDateFrom: "20260101",
        uploadDateTo: "20261231",
      },
      controller.signal,
    )
    await client.getSong(7)
    await client.listSetlistContributors(20, 40)
    await client.listChannels(20, 40)
    await client.getChannel("UC / one")
    await client.listChannelVideos("UC / one", 10, 20, "song", true)
    await client.listChannelVideos("UC2", 10, 0)
    await client.listVideoSongs("vid / one", 20, 40)
    await client.getVideo("vid / one")

    const urls = fetch.mock.calls.map(([url]) => String(url))
    expect(urls).toEqual([
      "/api/v1/updater/status",
      "/api/v1/report/summary",
      "/api/v1/songs/search?q=song+name&limit=20&offset=40&channel_id=UC+one&channel_id=UC%2Ftwo&type=karaoke&upload_date_from=20260101&upload_date_to=20261231",
      "/api/v1/songs/suggestions?q=song&limit=8&channel_id=UC1&type=song&upload_date_from=20260101&upload_date_to=20261231",
      "/api/v1/songs/7",
      "/api/v1/contributors?limit=20&offset=40",
      "/api/v1/channels?limit=20&offset=40",
      "/api/v1/channels/UC%20%2F%20one",
      "/api/v1/channels/UC%20%2F%20one/videos?limit=10&offset=20&type=song&has_song_list=true",
      "/api/v1/channels/UC2/videos?limit=10&offset=0",
      "/api/v1/videos/vid%20%2F%20one/songs?limit=20&offset=40",
      "/api/v1/videos/vid%20%2F%20one",
    ])
    expect(fetch.mock.calls[3]?.[1]?.signal).toBe(controller.signal)
  })

  test("covers login, logout, bulk add, refresh, and reload mutations", async () => {
    const fetch = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        jsonResponse({
          authenticated: true,
          role: "admin",
          username: "operator",
          csrf_token: "token",
          management_enabled: true,
        }),
    )
    const client = createApiClient({ fetch })

    await client.login("operator", "secret")
    await client.createChannelsBulk(["https://youtube.test/a"])
    await client.refreshChannelVideos("UC/1")
    await client.reloadVideoSongs("video/1")
    await client.logout()

    expect(
      fetch.mock.calls.slice(1, 4).map(([, init]) =>
        new Headers(init?.headers).get("X-CSRF-Token"),
      ),
    ).toEqual(["token", "token", "token"])
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "/v1/auth/login",
      "/v1/channels/bulk",
      "/v1/channels/UC%2F1/videos/refresh",
      "/v1/videos/video%2F1/songs/reload",
      "/v1/auth/logout",
    ])
    expect(fetch.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          username: "operator",
          password: "secret",
        }),
      }),
    )
  })

  test("uses the global transport and omits absent optional filters", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => jsonResponse({}))
    const client = createApiClient()

    await client.health()
    await client.searchSongs("plain", 10, 0)
    await client.suggestSongs("plain", 5)
    await client.listChannelVideos("UC1", 10, 0, "karaoke", false)

    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([
      "/v1/health",
      "/v1/songs/search?q=plain&limit=10&offset=0",
      "/v1/songs/suggestions?q=plain&limit=5",
      "/v1/channels/UC1/videos?limit=10&offset=0&type=karaoke&has_song_list=false",
    ])
  })
})
