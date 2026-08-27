# Setlist design system

This file is the source of truth for the whole-site UI/UX redesign. Page-specific
rules in `pages/<page>.md` override this file only when they explicitly say so.

The direction was generated with `ui-ux-pro-max` for a searchable music catalog
and then adapted for Setlist's trilingual web UI, existing React/Tailwind stack,
privacy posture, and WCAG AA requirements.

## Product direction

- Product: public VTuber karaoke song finder and browsable setlist archive.
- Primary job: find a song quickly and open the saved YouTube timestamp.
- Secondary jobs: browse performers and streams, understand catalog freshness,
  credit setlist contributors, and operate the private administrator tools.
- Visual idea: a modern red-and-neutral music archive—calm enough for long
  browsing, energetic at play/search actions, and neutral around colorful
  thumbnails. The established red identity is a product invariant.
- Pattern: search-first directory with a compact persistent navigation shell.
- Design dials: variance 6/10, motion 4/10, density 5/10.

## Non-negotiable UX rules

- Keep every existing route and feature reachable by URL and keyboard.
- Search is the primary action on the home and search pages and remains readily
  available from other desktop pages. Do not render a duplicate global search
  control in the header while the user is already on `/search`.
- Every interactive target is at least 44px high and wide where applicable.
- Never require hover to discover a primary action.
- Use one `h1` per route, sequential headings, semantic landmarks, and the skip
  link. Dynamic loading, errors, and mutation outcomes remain announced.
- Preserve search/filter/page state in the URL and preserve contextual back
  navigation on detail pages.
- Support 200% zoom, reduced motion, keyboard-only use, and no horizontal page
  scrolling at 320px and above.
- Color never carries status by itself; pair it with text and/or a Lucide icon.

## Color tokens

The confirmed pre-redesign red/neutral palette is implemented as paired semantic
themes. Both themes are first-class; dark mode is not the only polished
presentation. Green is reserved for semantic success/health states and never
replaces red as the product identity.

| Token | Light | Dark | Purpose |
|---|---|---|---|
| `background` | `#f9f9f9` | `#0f0f0f` | Page canvas |
| `foreground` | `#0f0f0f` | `#f1f1f1` | Primary text |
| `card` | `#ffffff` | `#181818` | Raised content |
| `primary` | `#c9002b` | `#ff667a` | Search, play, active state |
| `primary-foreground` | `#ffffff` | `#210008` | Text on primary |
| `secondary` | `#eeeeee` | `#272727` | Quiet controls and grouping |
| `muted-foreground` | `#5f6368` | `#b8b8b8` | Secondary text |
| `accent` | `#ffe8ed` | `#43131d` | Special metadata and highlights |
| `accent-foreground` | `#86001d` | `#ffc1c9` | Text on accent |
| `border` | `#dedede` | `#3f3f3f` | Dividers and outlines |
| `input` | `#b8b8b8` | `#5b5b5b` | Form boundaries |
| `ring` | `#c9002b` | `#ff667a` | Keyboard focus |
| `destructive` | `#b3261e` | `#ff897d` | Errors/destructive actions |
| `brand` | `#f40035` | `#ff1747` | Approved logo identity |

Use semantic utilities in components. Raw colors are limited to the token
definitions, thumbnail scrims, and verified status colors.

## Typography

- Use the bundled Figtree variable font for Latin text; it is metrically close
  to the generated Inter direction and does not add a third-party font request.
- Fallback order includes `Noto Sans TC`, `Noto Sans JP`, `Noto Sans`, and system
  sans-serif fonts so Traditional Chinese and Japanese remain readable.
- Headings use the same family with weight, spacing, and scale—not a display font
  that lacks CJK coverage.
- Body text is at least 16px on mobile, with 1.5–1.7 line height.
- Long-form text is limited to about 70 characters per line.
- Counts, timestamps, IDs, and dates use tabular numerals.

## Layout and navigation

- Desktop (>=1024px): one 72px sticky top bar with brand, primary navigation,
  global search, and preferences. Do not reserve a permanent left sidebar.
- Between 1024px and 1279px, keep icon navigation and preferences grouped at
  the right edge; at 1280px and above, restore the full labelled desktop flow.
- Mobile/tablet: compact 64px top bar plus four-item bottom navigation for Home,
  Search, Channels, and Recent. Secondary and administrator destinations live in
  the accessible menu.
- The mobile account/preferences trigger is a 44x44px circle. It may expand to a
  labelled/chevron control only from the `sm` breakpoint upward.
- Content width: 1440px maximum, with 16/24/32px responsive gutters.
- Page rhythm: 24px mobile and 40–56px desktop vertical section spacing.
- Repeated media grids use one column on phones, two on small tablets, three on
  desktop, and four only when cards retain a readable width.
- Recent updates return 12 channels so two-, three-, and four-column grids can
  form complete rows whenever the catalog contains at least 12 channels.
- Fixed navigation must reserve content padding including safe-area insets.

## Surfaces and components

- Default surfaces use a 1px semantic border, 16–24px radius, and restrained
  shadow. Elevation communicates hierarchy; it is not added to every container.
- The home hero may use subtle red ambient radial light. Avoid decorative blur on
  dense lists, reports, and forms.
- Primary buttons are solid semantic `primary`; secondary actions are outline or
  quiet. Each screen has one visually dominant action.
- Cards expose their primary action without hover. Hover/focus may add border,
  color, or a <=2px visual lift without changing layout bounds.
- Inputs have visible labels (or an equivalent accessible search landmark), 48px
  minimum height, persistent helper/error text, and strong focus rings.
- Loading skeletons reserve the final layout's dimensions. Empty and error states
  always provide a next action or recovery path.
- Lucide is the single icon family. No emoji or raster UI icons.

## Motion

- Use CSS transform/opacity transitions in the 180–260ms range with an
  `cubic-bezier(0.16, 1, 0.3, 1)` ease.
- Motion explains entrance, state, or hierarchy; never block interaction.
- Limit initial entrance motion to the hero and the first visible group. Avoid
  replaying animation across long result lists.
- Do not add GSAP for this redesign. The suggested stagger effect is implemented
  with lightweight CSS only.
- `prefers-reduced-motion: reduce` disables nonessential animation and smooth
  scrolling.

## Page priorities

- Home: asymmetric search-first hero, live collection proof, recently refreshed
  channels, and recently indexed songs.
- Search: query and filters form one coherent full-width workspace; result count
  and active filters are obvious; no-results guidance avoids a dead end.
- Channels/updates: make catalog scanning faster with stronger avatars,
  timestamps, and clear destination actions.
- Song/video/channel detail: establish a stable hierarchy of artwork, identity,
  primary YouTube action, metadata, and related archive content.
- Summary/status: emphasize the few decisive metrics before detailed operational
  values; do not render every number with equal visual weight.
- Legal/help/about: editorial reading layout with fewer nested cards and a
  comfortable text measure.
- Admin forms: clear labels, pacing context, inline errors, loading states, and
  mutation outcome summaries.

## Pre-delivery checklist

- [x] All existing routes and administrator guards still work.
- [x] Search suggestions, filters, pagination, deep links, and contextual back work.
- [x] All controls have visible hover, pressed, disabled, and focus states.
- [x] All primary touch targets are at least 44x44px.
- [x] Light and dark token pairs meet WCAG AA contrast.
- [x] Tested at 320, 375, 768, 1024, 1280, and 1440px plus mobile landscape.
- [x] No horizontal page overflow or content hidden behind sticky navigation.
- [x] Keyboard navigation, dialogs, dropdowns, and combobox behavior work.
- [x] Reduced motion and 200% zoom remain usable.
- [x] Images reserve aspect ratio, below-fold media is lazy, and no new remote font
      or decorative runtime dependency was introduced.
- [x] Unit, E2E, lint, build, production image, audit, and repository checks pass.
