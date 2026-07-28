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
})
