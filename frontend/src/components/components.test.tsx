import { QueryClient } from "@tanstack/react-query"
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, test, vi } from "vitest"

import { ChannelCard } from "@/components/channel-card"
import { ChannelRequestNotice } from "@/components/channel-request-notice"
import { ContextualBackButton } from "@/components/contextual-back-button"
import { InfoPage, InfoSection } from "@/components/info-page"
import { PageMetadata } from "@/components/page-metadata"
import { PaginationControls } from "@/components/pagination-controls"
import { QueryState } from "@/components/query-state"
import { SearchFilters } from "@/components/search-filters"
import { SearchForm } from "@/components/search-form"
import { SiteHeader } from "@/components/site-header"
import {
  SongResultCard,
  SongResultRow,
} from "@/components/song-result-row"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { VideoCard } from "@/components/video-card"
import {
  VideoListBadges,
  videoTypeBadge,
} from "@/components/video-list-badges"
import { useClampPage } from "@/hooks/use-clamp-page"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { m } from "@/paraglide/messages"
import { useUiStore } from "@/stores/ui-store"
import {
  makeTestApi,
  renderWithProviders,
} from "@/test/test-utils"

const channel = {
  id: "UC1",
  name: "Test Singer",
  url: "https://youtube.test/@singer",
  thumbnail_url: "https://images.test/channel.jpg",
  created_at: null,
  updated_at: null,
}

const video = {
  id: "video1",
  title: "Karaoke Night",
  url: "https://youtube.test/watch?v=video1",
  channel_id: channel.id,
  upload_date: "20260720",
  upload_date_precision: "exact" as const,
  type: "karaoke",
  has_song_list_comment: true,
  created_at: null,
  updated_at: null,
}

const song = {
  id: 1,
  title: "Test Song",
  timestamp: "01:23",
  video_id: video.id,
  video_url: "https://youtube.test/watch?v=video1&t=83s",
  video_title: video.title,
  channel_id: channel.id,
  channel_name: channel.name,
  analyzed_by_llm: true,
}

beforeEach(() => {
  useUiStore.setState({
    locale: "en",
    theme: "light",
    recentSearches: [],
  })
})

describe("shared display components", () => {
  test("renders query loading, error, empty, and success states", async () => {
    const retry = vi.fn()
    const { rerender } = render(
      <QueryState isLoading emptyMessage="Nothing">
        Loaded
      </QueryState>,
    )
    expect(screen.getByLabelText(m.loading())).toBeInTheDocument()

    rerender(
      <QueryState isLoading loadingLayout="grid" emptyMessage="Nothing">
        Loaded
      </QueryState>,
    )
    expect(screen.getByLabelText(m.loading()).className).toContain("media-grid")

    rerender(
      <QueryState isError emptyMessage="Nothing" onRetry={retry}>
        Loaded
      </QueryState>,
    )
    await userEvent.click(screen.getByRole("button"))
    expect(retry).toHaveBeenCalledOnce()

    rerender(
      <QueryState isError emptyMessage="Nothing">
        Loaded
      </QueryState>,
    )
    expect(screen.queryByRole("button")).toBeNull()

    rerender(
      <QueryState isEmpty emptyMessage="Nothing">
        Loaded
      </QueryState>,
    )
    expect(screen.getByText("Nothing")).toBeInTheDocument()

    rerender(<QueryState emptyMessage="Nothing">Loaded</QueryState>)
    expect(screen.getByText("Loaded")).toBeInTheDocument()
  })

  test("renders pagination controls and dispatches every navigation action", async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    const onPageSizeChange = vi.fn()
    const { rerender } = render(
      <PaginationControls
        page={5}
        total={240}
        pageSize={20}
        onPageChange={onPageChange}
        pageSizeOptions={[10, 20, 50]}
        onPageSizeChange={onPageSizeChange}
      />,
    )

    await user.click(screen.getByLabelText(m.pagination_first()))
    await user.click(screen.getByLabelText(m.pagination_prev()))
    await user.click(screen.getByLabelText(m.pagination_next()))
    await user.click(screen.getByLabelText(m.pagination_last()))
    await user.click(screen.getByLabelText(m.pagination_goto({ page: "1" })))
    await user.selectOptions(
      screen.getByLabelText(m.pagination_select_label()),
      "8",
    )
    await user.selectOptions(
      screen.getByLabelText(m.pagination_page_size_label()),
      "50",
    )
    expect(onPageChange.mock.calls.flat()).toEqual(
      expect.arrayContaining([0, 4, 6, 11, 7]),
    )
    expect(onPageSizeChange).toHaveBeenCalledWith(50)

    rerender(
      <PaginationControls
        page={0}
        total={3}
        pageSize={20}
        onPageChange={onPageChange}
        pageSizeOptions={[20]}
        disabled
      />,
    )
    expect(screen.queryByRole("navigation")).toBeNull()
    expect(
      screen.getByLabelText(m.pagination_page_size_label()),
    ).toBeDisabled()

    rerender(
      <PaginationControls
        page={0}
        total={3}
        pageSize={20}
        onPageChange={onPageChange}
      />,
    )
    expect(document.body.textContent).not.toContain(m.pagination_page_size_label())
  })

  test("renders card, badge, notice, info, and primitive variants", async () => {
    await renderWithProviders(
      <>
        <ul>
          <ChannelCard channel={channel} index={7} />
          <ChannelCard
            channel={{ ...channel, thumbnail_url: null }}
            index={1}
          />
          <VideoCard video={video} index={6} />
          <VideoCard
            video={{
              ...video,
              upload_date: null,
              upload_date_precision: "approximate",
              type: "song",
              has_song_list_comment: false,
            }}
          />
          <SongResultCard song={song} index={6} />
          <SongResultRow
            song={{
              ...song,
              timestamp: null,
              video_title: null,
              analyzed_by_llm: false,
            }}
          />
        </ul>
        <ChannelRequestNotice className="custom" />
        <InfoPage eyebrow="Eye" title="Info" intro="Intro">
          <InfoSection title="Section">Body</InfoSection>
        </InfoPage>
        <VideoListBadges type="other" hasSetlist={false} />
        <VideoListBadges type="song" hasSetlist showSetlist={false} />
        <Badge variant="success">Badge</Badge>
        <Button variant="destructive">Button</Button>
        <Input aria-label="input" />
        <Skeleton>Skeleton</Skeleton>
      </>,
    )
    expect(screen.getAllByText(channel.name).length).toBeGreaterThan(1)
    expect(screen.getByText("Info")).toBeInTheDocument()
    expect(buttonVariants({ size: "sm", variant: "outline" })).toContain(
      "outline",
    )
    expect(videoTypeBadge("karaoke").variant).toBe("karaoke")
    expect(videoTypeBadge("SONG").variant).toBe("song")
    expect(videoTypeBadge("video").variant).toBe("muted")
    expect(videoTypeBadge("was_live").variant).toBe("muted")
    expect(videoTypeBadge("unknown").variant).toBe("muted")
    expect(videoTypeBadge(null).variant).toBe("muted")
  })

  test("updates and restores page metadata", () => {
    const { unmount } = render(
      <PageMetadata path="/search" noIndex />,
    )
    expect(document.title).toBe(m.meta_default_title())
    expect(
      document.querySelector('meta[name="robots"]')?.getAttribute("content"),
    ).toBe("noindex,follow")
    expect(
      document.querySelector('link[rel="canonical"]')?.getAttribute("href"),
    ).toContain("/search")
    unmount()
    expect(
      document.querySelector('meta[name="robots"]')?.getAttribute("content"),
    ).toContain("index,follow")
  })
})

describe("hooks and UI preference store", () => {
  test("clamps changed result pages and ignores valid or unknown totals", () => {
    const onPageChange = vi.fn()
    const { rerender } = renderHook(
      ({ page, total }) => useClampPage(page, total, 20, onPageChange),
      { initialProps: { page: 5, total: undefined as number | undefined } },
    )
    expect(onPageChange).not.toHaveBeenCalled()
    rerender({ page: 0, total: 1 })
    rerender({ page: 5, total: 21 })
    expect(onPageChange).toHaveBeenCalledWith(1)
  })

  test("debounces values and cancels an obsolete timer", () => {
    vi.useFakeTimers()
    const { result, rerender, unmount } = renderHook(
      ({ value, delay }) => useDebouncedValue(value, delay),
      { initialProps: { value: "one", delay: 100 } },
    )
    expect(result.current).toBe("one")
    rerender({ value: "two", delay: 100 })
    expect(result.current).toBe("one")
    act(() => vi.advanceTimersByTime(100))
    expect(result.current).toBe("two")
    rerender({ value: "three", delay: 100 })
    unmount()
    act(() => vi.runAllTimers())
  })

  test("updates theme, locale, and bounded recent searches", () => {
    const state = useUiStore.getState()
    state.setLocalePref("en")
    state.toggleTheme()
    expect(useUiStore.getState().theme).toBe("dark")
    state.toggleTheme()
    expect(useUiStore.getState().theme).toBe("light")
    state.addRecentSearch(" ")
    state.addRecentSearch("Song")
    state.addRecentSearch("song")
    for (let i = 0; i < 10; i += 1) {
      state.addRecentSearch(`query ${i}`)
    }
    expect(useUiStore.getState().recentSearches).toHaveLength(8)
    expect(useUiStore.getState().recentSearches).not.toContain("Song")
    state.clearRecentSearches()
    expect(useUiStore.getState().recentSearches).toEqual([])
  })
})

describe("interactive search controls", () => {
  test("submits, clears, navigates, and selects suggestions", async () => {
    const user = userEvent.setup()
    const submit = vi.fn()
    const cancelQueries = vi.spyOn(QueryClient.prototype, "cancelQueries")
    const api = makeTestApi({
      suggestSongs: vi.fn(async () => [
        { title: "Test Song", occurrences: 2 },
        { title: "Second Song", occurrences: 1 },
      ]),
    })
    await renderWithProviders(
      <SearchForm
        onQuerySubmit={submit}
        autoFocus
        variant="hero"
        hint="Hint"
        showAdvancedSearchLink
      />,
      { api },
    )
    const input = screen.getByRole("combobox")

    await user.type(input, "Te")
    expect(cancelQueries).toHaveBeenCalled()
    await waitFor(
      () => expect(screen.getByRole("listbox")).toBeInTheDocument(),
      { timeout: 1500 },
    )
    await waitFor(
      () => expect(screen.getByText("Test Song")).toBeInTheDocument(),
      { timeout: 1500 },
    )
    const secondSuggestion = screen.getByText("Second Song")
    fireEvent.mouseEnter(secondSuggestion)
    fireEvent.mouseDown(secondSuggestion)
    await user.click(secondSuggestion)
    expect(submit).toHaveBeenCalledWith("Second Song")

    await user.type(input, "Te")
    await waitFor(
      () => expect(screen.getByText("Test Song")).toBeInTheDocument(),
      { timeout: 1500 },
    )
    await user.keyboard("{ArrowDown}{ArrowDown}{ArrowUp}{Enter}")
    expect(submit).toHaveBeenCalledWith("Test Song")

    await user.clear(input)
    await user.type(input, "Other")
    await user.keyboard("{Escape}")
    expect(screen.queryByRole("listbox")).toBeNull()
    await user.keyboard("{Enter}")
    expect(submit).toHaveBeenCalledWith("Other")

    await user.click(screen.getByLabelText(m.search_clear()))
    expect(submit).toHaveBeenCalledWith("")
    fireEvent.keyDown(window, { key: "/" })
    expect(input).toHaveFocus()
  })

  test("renders recent searches and clears them", async () => {
    useUiStore.setState({ recentSearches: ["Recent"] })
    const submit = vi.fn()
    await renderWithProviders(
      <SearchForm initialQuery="Initial" onQuerySubmit={submit} />,
    )
    await userEvent.click(
      screen.getByRole("button", { name: "Recent" }),
    )
    expect(submit).toHaveBeenCalledWith("Recent")
    await userEvent.click(screen.getByText(m.clear_recent()))
    expect(screen.queryByText("Recent")).toBeNull()
  })

  test("changes search filters, dates, channels, and reset state", async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const api = makeTestApi({
      listChannels: vi.fn(async () => ({
        items: [channel, { ...channel, id: "UC2", name: "Other Singer" }],
        total: 2,
        limit: 100,
        offset: 0,
      })),
    })
    await renderWithProviders(
      <SearchFilters
        filters={{
          channel_ids: ["UC1"],
          type: "karaoke",
          date_from: "20260101",
          date_to: "20261231",
        }}
        onChange={onChange}
      />,
      { api },
    )

    await user.click(
      screen.getByRole("button", { name: m.search_type_song() }),
    )
    fireEvent.change(screen.getByLabelText(m.search_date_from()), {
      target: { value: "2026-02-03" },
    })
    fireEvent.change(screen.getByLabelText(m.search_date_to()), {
      target: { value: "" },
    })
    await user.click(
      screen.getByRole("button", { name: /selected/i }),
    )
    await waitFor(() =>
      expect(screen.getByText("Other Singer")).toBeInTheDocument(),
    )
    await user.click(screen.getByText("Other Singer"))
    await user.click(screen.getByText(m.search_filters_clear()))

    expect(onChange.mock.calls.flat()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "song" }),
        expect.objectContaining({ date_from: "20260203" }),
        expect.objectContaining({ date_to: undefined }),
        expect.objectContaining({ channel_ids: ["UC1", "UC2"] }),
        {
          channel_ids: undefined,
          type: undefined,
          date_from: undefined,
          date_to: undefined,
        },
      ]),
    )
  })
})

describe("header and contextual navigation", () => {
  test("handles theme, locale, logout, and router back/fallback", async () => {
    const logout = vi.fn(async () => ({
      authenticated: false,
      role: null,
      username: null,
      csrf_token: null,
      management_enabled: false,
    }))
    const api = makeTestApi({
      authSession: vi.fn(async () => ({
        authenticated: true,
        role: "admin" as const,
        username: "operator",
        csrf_token: "csrf",
        management_enabled: true,
      })),
      logout,
    })
    const fallback = vi.fn()
    const { history } = await renderWithProviders(
      <>
        <SiteHeader />
        <ContextualBackButton label="Back" onFallback={fallback} />
      </>,
      { api, initialEntries: ["/previous", "/"] },
    )
    await waitFor(() =>
      expect(screen.getByLabelText(m.auth_sign_out())).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByLabelText(m.theme_switch_dark()))
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    await userEvent.click(screen.getByText(m.locale_en()))
    await userEvent.click(screen.getByLabelText(m.auth_sign_out()))
    expect(logout).toHaveBeenCalled()

    await userEvent.click(screen.getByText("Back"))
    expect(history.location.pathname).toBe("/previous")
  })

  test("uses contextual navigation fallback without browser history", async () => {
    const fallback = vi.fn()
    await renderWithProviders(
      <ContextualBackButton label="Back" onFallback={fallback} />,
    )
    await userEvent.click(screen.getByText("Back"))
    expect(fallback).toHaveBeenCalled()
  })
})
