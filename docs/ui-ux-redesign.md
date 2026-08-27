# Whole-site UI/UX redesign plan and checklist

## Goal

Redesign Setlist as a search-first, trilingual music archive while preserving
every public and administrator feature. The implementation follows
[`design-system/setlist/MASTER.md`](../design-system/setlist/MASTER.md).

## Baseline review

### What already works

- Search, suggestions, URL-backed filters, pagination, deep links, contextual
  back navigation, light/dark themes, localization, and administrator guards are
  functionally sound.
- Semantic landmarks, a skip link, Radix dialogs/menus, loading skeletons, and
  reduced-motion CSS provide a useful accessibility foundation.
- Public browse, detail, report, contributor, legal, and administrator routes are
  all deep-linkable.

### Main problems to solve

- The permanent desktop sidebar consumes valuable width and duplicates the top
  shell, while many destinations receive equal emphasis.
- Repeated bordered cards make the home, report, information, and admin pages
  feel visually uniform instead of establishing clear priority.
- Song/video card actions and metadata are fragmented; important play and detail
  actions need clearer grouping without relying on hover.
- The summary gives ten metrics equal weight, slowing comprehension.
- At 375px, several visible links and icon actions are only 32–40px high, below
  the 44px touch-target goal.
- The redesign unintentionally replaced the confirmed red/neutral product
  identity. The approved red palette, favicon, and browser/PWA colors must
  remain brand invariants while the new layout and interaction model evolve.

## Scope and route inventory

- Public discovery: `/`, `/search`, `/channels`, `/channels/:channelId`,
  `/videos/:videoId`, `/songs/:songId`, `/updates`.
- Public information: `/summary`, `/thanks`, `/how-to-use`, `/about`, `/terms`,
  `/privacy`, `/copyright`, and not-found handling.
- Private operations: `/admin/login`, `/status`, `/channels/new`, authenticated
  navigation, channel refresh, song reload, and ingest queue states.
- Shared behavior: header/menu, mobile navigation, footer, theme/language menu,
  API status, query states, filters, cards, badges, pagination, and metadata.

## Implementation plan

### 1. Foundation and shell

- [x] Replace the desktop sidebar with a responsive sticky top navigation.
- [x] Keep a four-item mobile bottom navigation and move secondary destinations
      into the menu.
- [x] Restore the approved red/neutral light and dark semantic token system.
- [x] Rework spacing, type, surfaces, focus, motion, and shared page-width rules.
- [x] Keep the global search discoverable without crowding tablet widths.

### 2. Discovery and browse flows

- [x] Recompose the home hero around the search task and live catalog proof.
- [x] Add a useful home section for recently refreshed channels using the
      existing recent-updates API.
- [x] Redesign song, video, and channel cards for clearer scanning and actions.
- [x] Turn search and filters into one coherent workspace with clear active state.
- [x] Improve channel directory, channel tabs, updates, and pagination hierarchy.

### 3. Detail, data, information, and administrator pages

- [x] Redesign song and video detail pages around thumbnail, identity, metadata,
      timestamp play action, and setlist provenance.
- [x] Redesign the channel page header and archive controls.
- [x] Prioritize decisive summary metrics before detailed pipeline/backfill data.
- [x] Improve the contributor list and long-form information-page reading flow.
- [x] Apply the same system to login, updater status, channel ingest, mutation
      feedback, and queued work.

### 4. Accessibility, responsive behavior, and quality

- [x] Maintain semantic landmarks, sequential headings, labels, live regions,
      keyboard navigation, focus return, and route guards.
- [x] Enforce 44px targets and visible focus/pressed/disabled states.
- [x] Verify no horizontal overflow at 320/375/768/1024/1280/1440px.
- [x] Verify both themes, reduced motion, mobile landscape, and 200% zoom.
- [x] Preserve image aspect ratios, lazy loading, and route-level performance.

### 5. Validation and release

- [x] Update unit/component/E2E coverage for the new shell and home channel block.
- [x] Run i18n validation, lint, tests, coverage, build, audit, notices, secret
      scan, Compose parsing, and the production frontend Docker build.
- [x] Perform visual and interaction QA in the browser across key routes.
- [x] Commit with a Conventional Commit, push a feature PR, wait for protected
      checks, merge, create the patch release PR/tag, publish images, deploy, and
      independently verify production.

### 6. Confirmed-brand and responsive correction

- [x] Restore the exact approved red semantic colors from `v0.8.2`, the red
      favicon, and matching static/generated manifest and browser theme colors.
- [x] Return 12 recently refreshed channels so the four-column desktop grid can
      render complete rows when at least 12 channels are available.
- [x] Make the search workspace span the full content width and suppress the
      duplicate header search control while already on `/search`.
- [x] Push medium-width header navigation and preferences to the right while
      preserving the full labelled desktop layout at wider breakpoints.
- [x] Make the mobile account/preferences trigger a true 44x44px circle.
- [x] Cover the corrections with backend, component/E2E, metadata, responsive,
      dark/light, build, and production-image validation before release.

## Acceptance checklist

- [x] Every route above renders and every pre-existing action remains available.
- [x] A user can search from home, filter results, open song detail, and play the
      exact YouTube timestamp.
- [x] A user can browse channels to videos and setlist songs and return with URL
      state intact.
- [x] Theme, locale, recent searches, mobile menu, and mobile navigation work.
- [x] Guests cannot access status or mutations; administrators retain all controls.
- [x] Empty, loading, error, cooldown, success, and disabled states are legible.
- [x] No new backend contract, production secret, or deployment topology change is
      required.

## Progress log

- 2026-08-27: Completed route/code/production baseline review and generated the
  adapted `ui-ux-pro-max` design system. Implementation is next.
- 2026-08-27: Implemented the new responsive shell, search-first home and browse
  flows, media cards, detail/report/information layouts, and administrator UI.
- 2026-08-27: Completed browser QA in both themes and three locales at
  320/375/667/768/1024/1280/1440px. Fixed narrow video-setlist overflow and
  compact administrator-header density. Build, lint, unit/component, and core
  E2E checks pass; the full release gate remains.
- 2026-08-27: Passed 379 backend tests at 87.22% combined coverage, 87
  frontend tests above every 80% coverage threshold, four Playwright flows,
  production Compose policy parsing, zero-vulnerability audit, repository
  security/quality/release checks, production build, and frontend image/runtime
  smoke testing. Release publication and production verification remain.
- 2026-08-27: Merged the redesign and browser-theme follow-up through protected
  pull requests, released `v0.8.4`, published and attested all four images, and
  completed automated plus independent production verification. Public routes,
  responsive browser QA, Flyway V14, the updater heartbeat, the pre-deployment
  backup, and the Valkey cache policy/hit probe all passed.
- 2026-08-27: Restored the confirmed red identity and favicon, returned 12 recent
  channels, and corrected search/header behavior at wide, medium, and mobile
  widths. The correction passed 379 backend tests at 87.23% coverage, 87
  frontend tests above every 80% threshold, five Playwright flows, lint, build,
  zero-vulnerability audit, repository checks, both production image builds,
  and frontend/backend image smoke tests. Patch release publication remains.
