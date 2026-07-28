import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRouteWithContext,
  createRoute,
  createRouter,
} from "@tanstack/react-router"
import { act, render } from "@testing-library/react"
import type { ReactNode } from "react"
import { vi } from "vitest"

import type { ApiClient } from "@/api/client"
import { ApiProvider } from "@/api/provider"

export function makeTestApi(overrides: Partial<ApiClient> = {}) {
  const session = {
    authenticated: false,
    role: null,
    username: null,
    csrf_token: null,
    management_enabled: false,
  } as const
  return {
    health: vi.fn(async () => ({ status: "healthy" })),
    authSession: vi.fn(async () => session),
    login: vi.fn(async () => ({ ...session })),
    logout: vi.fn(async () => ({ ...session })),
    updaterStatus: vi.fn(async () => ({ phase: "idle" })),
    summaryReport: vi.fn(async () => ({ channels: 0 })),
    searchSongs: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })),
    suggestSongs: vi.fn(async () => []),
    getSong: vi.fn(async () => ({ id: 1 })),
    listSetlistContributors: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })),
    listChannels: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })),
    getChannel: vi.fn(async () => ({ id: "UC1" })),
    createChannel: vi.fn(async () => ({ id: "UC1" })),
    createChannelsBulk: vi.fn(async () => ({ items: [] })),
    listChannelVideos: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })),
    refreshChannelVideos: vi.fn(async () => ({ channel_id: "UC1" })),
    reloadVideoSongs: vi.fn(async () => ({ video_id: "video1" })),
    listVideoSongs: vi.fn(async () => ({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    })),
    getVideo: vi.fn(async () => ({ id: "video1" })),
    ...overrides,
  } as unknown as ApiClient
}

export async function renderWithProviders(
  ui: ReactNode,
  options: {
    api?: ApiClient
    initialEntries?: string[]
  } = {},
) {
  const api = options.api ?? makeTestApi()
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
  const rootRoute = createRootRouteWithContext<{
    queryClient: QueryClient
    api: ApiClient
  }>()({
    component: Outlet,
    notFoundComponent: () => null,
  })
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => ui,
  })
  const routeTree = rootRoute.addChildren([indexRoute])
  const history = createMemoryHistory({
    initialEntries: options.initialEntries ?? ["/"],
  })
  const router = createRouter({
    routeTree,
    history,
    context: { queryClient, api },
  })

  const rendered = render(
    <ApiProvider client={api}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ApiProvider>,
  )
  await act(async () => {
    await router.load()
  })
  return { ...rendered, api, history, queryClient, router }
}
