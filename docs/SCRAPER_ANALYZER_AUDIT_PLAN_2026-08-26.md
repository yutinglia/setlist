# Scraper and Analyzer Audit Plan — 2026-08-26

## Objective

Audit the complete stored video corpus and the unresolved karaoke-analysis
queue, validate real YouTube comment retrieval across every stored channel,
then improve classification, scraping, and setlist extraction using evidence
from reproducible failures. Safely reprocess eligible production records and
publish the result through the protected release and deployment workflow.

This file is the live checklist and evidence log for the audit. Checkboxes and
findings will be updated as work progresses.

## Safety and scope rules

- [x] Read the repository, machine-local, and release/deployment instructions.
- [x] Confirm both source and deployment repositories start from synchronized
  `main` branches.
- [x] Confirm the active GitHub identity is the non-owner agent account.
- [x] Create a dedicated `codex/*` feature branch before tracked changes.
- [x] Keep all database discovery read-only until a reviewed apply step.
- [x] Preserve successful stored setlists unless a separately reviewed rule
  proves that replacing or clearing them is safe.
- [x] Respect the shared YouTube lock, global cooldown, retry bounds, pacing,
  and maximum comment depth during live sampling and production work.
- [x] Do not expose production configuration values, private topology, or raw
  user comment text in committed artifacts.
- [x] Follow the current GitHub repository rules. The user explicitly removed
  the independent-approval requirement on 2026-08-27; retain pull requests,
  required CI, exact-head merge checks, and the guarded release sequence.
- [ ] Require a valid pre-deployment PostgreSQL backup before any production
  mutation.

## Phase 1 — Establish the evidence baseline

- [x] Record current version, deployed release, health, schema migration,
  updater state, and corpus totals.
- [x] Query every stored video and stream record for classification evidence:
  title, description, live/archive metadata, persisted source snapshots,
  analysis state, comment availability, and stored songs.
- [x] Re-evaluate every record with the current classifier and report all
  proposed `other`/`song`/`karaoke` transitions without applying them.
- [x] Audit every karaoke record without a successful setlist and assign a
  failure category (not attempted, retryable scrape failure, unavailable or
  disabled comments, no setlist comment, parser rejection, inaccessible
  archive, or inconsistent persisted state).
- [x] Check invariants: no songs on non-karaoke records, successful analyses
  have songs and source attribution, attempts and pending states are coherent,
  and exact metadata is not downgraded by flat-list snapshots.
- [x] Save only privacy-safe aggregate statistics and synthetic/minimized
  regression fixtures in tracked files.

### Baseline metrics

| Metric | Before | Candidate rules | After apply |
| --- | ---: | ---: | ---: |
| Total videos | 52,159 | 52,159 | Pending |
| Karaoke videos | 6,147 | 6,187 | Pending |
| Song videos | 2,678 | 2,724 | Pending |
| Other videos | 43,334 | 43,248 | Pending |
| Karaoke videos with setlists | 5,841 | 5,849 | Pending |
| Setlist success rate | 95.022% | 94.537% | Pending |
| Stored songs | 99,233 | 98,851 | Pending |
| Unresolved karaoke videos | 306 | 338 | Pending |

## Phase 2 — Live yt-dlp sampling

- [x] Select a deterministic random sample covering every stored channel,
  weighted toward unresolved karaoke records while retaining successful and
  non-karaoke controls.
- [x] Run yt-dlp from Python through the same bounded configuration used by
  production; do not bypass cooldown or shared-lock requirements on the
  production service.
- [x] Record fetch outcome, top-level comment count, current-parser result,
  expected result, and failure category without committing raw comments.
- [x] Include edge cases such as members-only/private/deleted archives,
  disabled comments, uploader/pinned setlists, multilingual titles,
  timestamp variants, chapters mixed with chat, encore blocks, and very long
  streams.
- [x] Convert confirmed misses and false positives into minimized fixtures.
- [x] Stop live requests if block detection or cooldown signals appear.

## Phase 3 — Implement evidence-backed improvements

- [x] Improve video/song/karaoke classification only for patterns supported by
  reviewed corpus cases; add negative controls for every broadened rule.
- [x] Review the comment retrieval strategy against live evidence. No cap,
  ordering, depth, or reply expansion was justified; retain bounded retries,
  pacing, killable subprocess execution, and the cross-process YouTube
  singleton.
- [x] Add bounded retrieval diagnostics so future snapshots distinguish
  unavailable comments, empty responses, likely truncation, and the exact
  yt-dlp request/runtime shape without storing additional user content.
- [x] Improve comment ranking, setlist section detection, timestamp parsing,
  or title cleanup only for reproduced analyzer failures.
- [x] Keep repositories transaction-free and preserve `DataUpdater` ownership
  of durable page/analysis commits.
- [x] Keep last-successful-analysis-wins semantics and avoid erasing a good
  setlist after a later negative observation.
- [x] Add focused unit/integration tests for each fixed failure and for nearby
  false-positive risks.
- [x] Add or update a safe, idempotent dry-run/apply reanalysis command if the
  current production data cannot already be reprocessed safely.
- [x] Document exactly which existing records are eligible for reanalysis and
  which successful records remain intentionally untouched.

## Phase 4 — Verify code and data behavior

- [x] Run focused analyzer, scraper, updater, repository, and reanalysis tests.
- [x] Run the complete backend pytest suite and Ruff in the supported
  environment. (`mypy` is not configured in dependencies, CI, or project
  configuration and is therefore not an applicable project check.)
- [x] Run repository credential/history scanning.
- [x] Validate Compose parsing and production image builds if runtime or
  deployment inputs change.
- [x] Run a full production-corpus dry run and compare before/candidate totals.
- [x] Manually review every destructive candidate (classification downgrade,
  song clearing, or successful-setlist replacement).
- [x] Confirm a second dry run is deterministic and idempotent.
- [x] Update this plan with root causes, rule impact, remaining failures, and
  exact commands/tests executed.

## Phase 5 — Protected feature and release workflow

- [ ] Commit only scoped files with a Conventional Commits message.
- [ ] Push the feature branch and open a source pull request.
- [ ] Wait for all required feature checks and verify the exact PR head.
- [ ] After checks pass, squash-merge the feature PR with an exact-head guard
  and verify the resulting `main` commit.
- [ ] Compare the merged change against the private deployment control plane.
- [ ] If required, update the deployment repository through its own reviewed
  pull request and wait for merge; otherwise record compatibility evidence.
- [ ] From clean current source `main`, run the repository patch-version bump
  script and verify that only the three version files change.
- [ ] Open, check, and merge the exact-head release pull request without an
  independent approval wait, as explicitly requested by the user.
- [ ] Wait for the exact release commit's protected-main CI and CodeQL results.
- [ ] Create the immutable annotated tag with the repository script and push
  only that tag.
- [ ] Verify all four images, attestations, GitHub Release publication, and the
  exact-tag deployment dispatch.

## Phase 6 — Production deployment and recovery

- [ ] Confirm the deployment workflow creates a nonempty mode-`600`
  custom-format backup accepted by `pg_restore --list`.
- [ ] Confirm Flyway and all containers deploy the exact release and report
  healthy without unexplained restarts or OOM events.
- [ ] Run the stored-data reanalysis dry run on the deployed code.
- [ ] Review dry-run totals against the pre-release audit and then apply only
  the approved safe scope.
- [ ] Requeue unresolved retryable karaoke records without overwriting existing
  successful setlists.
- [ ] Run or wake the normal paced updater; never clear or bypass a persisted
  YouTube cooldown.
- [ ] Verify post-apply corpus totals, invariants, setlist success rate, and a
  second idempotent dry run.
- [ ] Independently verify public health, deployed release, migration state,
  updater heartbeat/outcome, backup validity, cache policy, and cache hit/TTL
  behavior.
- [ ] Return both repositories to clean synchronized `main` branches.

## Findings and decisions

### Evidence log

- On 2026-08-27 the user explicitly removed the independent-review wait to
  speed development. Read-only `gh` checks confirmed that neither source nor
  deployment `main` currently has branch protection or an applied branch
  ruleset. Work will still use the non-owner agent identity, pull requests,
  CI, exact-head verification, and the ordered release/tag/deploy gates; it
  will not directly push `main` or use a bypass identity.

- The read-only production audit covered all 52,158 videos in all 50 channels,
  all 6,147 stored karaoke records, all 5,841 successful setlists, and all 306
  unresolved karaoke records.
- The unresolved set contains 112 records without a stored comment snapshot,
  eight with comments unavailable, 186 with stored comments, and no persisted
  consistency violations. The current parser safely recovers 21 real setlists;
  one additional detection is a known birthday-live recap false positive that
  the classifier reclassifies as `other`.
- Description and chapter metadata were reviewed separately. Only one record
  contains a plausible chapter-based setlist, while the other candidates are
  schedules, opening times, ticket times, waiting screens, MC, or announcements.
  A generic metadata fallback is therefore rejected as unsafe.
- Replaying the new parser over all 5,841 successful records would change
  1,904 setlists (32.597%) and remove thousands of songs. Successful replay will
  remain disabled by default and requires per-video approval.
- The manually reviewed classifier dry run currently proposes 92
  `other -> karaoke`, 46 `other -> song`, and 52 `karaoke -> other`
  transitions. Every broadened rule has a nearby negative regression control.
- A deterministic local Python/yt-dlp sample completed all 58 records and all
  50 channels through an egress proven distinct from production. It made no
  production lock, cooldown, or database mutation. Forty extractions returned
  1,685 bounded top-level comments; 18 ordinary failures were members-only,
  two successful extractions exposed comments as unavailable, and no request
  produced a block, hard timeout, or cap anomaly. The analyzer selected 18
  setlists / 270 songs, including all 15 stored-success controls. Two genuine
  live recoveries (14 and four songs) independently confirm records already in
  the 21 offline / 23 clone recoveries. One 35-row chapter false positive is
  correctly guarded by the reviewed reclassification to `other`. The other
  non-success buckets were 13 without a timestamp cluster, three with one
  parseable row, one whose timestamps were all non-song rows, and three
  untrusted/unseparated two-row candidates below threshold. All 40 returned
  counts stayed within their requested caps; every one of the 28 responses
  with a reported count matched its returned count.
- Production logs since the v0.8.0 deployment contained 47 supposed global
  block events, all caused by the same age-restricted video saying “Sign in to
  confirm your age.” A single user-requested, 300-second-bounded public control
  from the same production backend container and egress succeeded with 50
  comments and the expected eight-song setlist. The persisted cooldown was not
  cleared or changed. This proves the production egress was accessible and the
  repeated six-hour cooldown was a detector false positive, not an IP block.
- The production updater added one new `other` record during the audit. The
  latest read-only replay therefore covers 52,159 records; the manually
  reviewed transition counts remain exactly 92 `other -> karaoke`, 46
  `other -> song`, and 52 `karaoke -> other`.
- A validated custom-format production dump was restored into a disposable,
  loopback-only PostgreSQL instance. The final full-service dry run proposed
  exactly 190 classifications, 645 song clears on 15 individually reviewed
  videos, 23 recovered setlists, no successful-setlist rewrite, and 248
  unresolved requeues. The recovered setlists add 263 songs after the approved
  false-positive clears, producing 98,851 stored songs in the candidate state.
- Two newly recognized karaoke records exposed final parser boundaries in the
  database clone. One Traditional Chinese interval list mixed 12 real songs
  with `OP`, opening chat, repeated chat, an accidental-click marker, and a
  closing marker. One Japanese comment placed three songs under a standalone
  live-singing heading before a separate cute-scenes chapter list. Narrow
  chapter/header rules now recover only the 12 and three real songs.
- The 54 non-karaoke state normalizations consist of the 52 reviewed
  `karaoke -> other` transitions plus two records that were already `other`,
  had no songs, and retained only obsolete contributor-attribution fields.
  No additional destructive clear is hidden in that count.
- Applying the exact reviewed manifest to the disposable clone produced
  6,187 karaoke, 2,724 song, and 43,248 other records; 5,849 karaoke records
  have setlists and 98,851 songs remain. Orphan songs, songs on non-karaoke
  records, mismatches between success flags and songs, non-karaoke attribution,
  and non-karaoke queue states all remained zero. An immediate second dry run
  reported zero classifications, clears, recoveries, rewrites, and requeues.
- The candidate success rate is 94.537%, lower than the old 95.022% because
  the corrected classifier adds 92 previously omitted karaoke records while
  removing false-positive song rows. This is a more accurate denominator, not
  an analyzer regression; live retrieval and the paced post-deploy queue are
  still required for the newly eligible unresolved records.

### Confirmed root causes

- The title classifier missed multilingual practice/singing frames, exact
  `Song`/`歌` labels, original-song catalog streams, bounded relay/performance
  formats, and several short standalone performance formats. It also treated
  creator boilerplate (`KARAOKE/Vsinger`, `Singing Stream`) as content and
  lacked precise recap, watchalong, promotion, and non-singing activity guards.
- The comment parser mishandled full-width numbering and colons, custom emoji
  adjacent to timestamps, punctuation immediately after timestamps, legacy
  and localized headers, late prose containing “setlist”, section boundaries,
  ordinal placeholders, trusted two-song setlists, Traditional/Simplified
  Chinese chat intervals, and Japanese live-singing/cute-scene boundaries.
- Pinned/uploader authority alone could make a generic two-row chapter list
  pass. Trusted two-song recovery now also requires song/artist separators;
  this preserves both confirmed production recoveries and rejects chapter-only
  authority comments.
- Stored comment observations did not record the request cap, returned count,
  sort/depth/reply policy, yt-dlp version, or likely truncation. New schema-2
  snapshots add only those bounded diagnostics; request depth and caps remain
  unchanged until live evidence supports a retrieval-policy change.
- Missing EJS support is a packaging risk, not yet a proven cause of comment
  misses. Both the old production-container control and the new-runtime local
  sample fetched and parsed comments, so this audit found no causal evidence
  that EJS absence explains the unresolved records.
- Global block detection matched the generic phrase `sign in to confirm` and
  every bare HTTP 403. That made one age-restricted video repeatedly activate
  six-hour global cooldowns and starve the entire analysis queue.

### Implemented changes

- Added corpus-derived classifier rules and precise non-performance exclusions,
  with duration/live-status gates retained for weak and short formats.
- Improved timestamp/header/section/title parsing and added minimized synthetic
  tests for every confirmed parser failure and nearby false-positive cases.
- Made unresolved requeue state-exact and idempotent; added dry-run reporting
  and per-video approvals for destructive clears and successful-setlist
  rewrites. Non-karaoke cleanup now also clears stale contributor attribution.
- Pinned yt-dlp 2026.08.19 with its official EJS component and a pinned Deno
  runtime in backend requirements. The production runtime image reports
  yt-dlp 2026.08.19, yt-dlp-ejs 0.8.0, and Deno 2.9.5.
- Added privacy-safe retrieval diagnostics to new stored comment snapshots;
  missing comments and available-but-empty responses remain distinct.
- Restricted global block detection to high-confidence 429, explicit bot or
  CAPTCHA, yt-dlp rate-limit, and IP/network-block signals. Age, membership,
  private/region restrictions and bare 403s now consume the normal bounded
  per-video retry budget. Typed block exceptions survive wrapper/subprocess
  boundaries even when their public message is opaque.

### Remaining limitations

- Stored-data replay cannot recover comments that were never fetched, were
  outside the bounded top-comment window, were replies, or are unavailable.
- Generic description/chapter parsing remains intentionally unsupported.
- Existing successful setlists are intentionally not blanket-rewritten.
- Persisted scraper state records the cooldown deadline and coarse outcome but
  not a durable reason category; detailed block causes remain available only
  in bounded server logs.
- Reviewed release, backup, deployment, and post-deploy reanalysis remain
  pending.

## Verification log

| Check | Result | Notes |
| --- | --- | --- |
| Focused backend tests | Pass | Classifier/analyzer/reanalysis/scraper/updater suites plus 56 block/subprocess/updater regression tests |
| Full backend tests | Pass | 379 tests with PostgreSQL integration and coverage; 87.22% total coverage |
| Ruff | Pass | Full check and format-check; 106 files |
| mypy | N/A | Not configured in project dependencies, CI, or configuration |
| Secret scan | Pass | No high-confidence credentials in files or history |
| Frontend | Pass | lint, 87 coverage tests, four Playwright tests, production build |
| Compose and images | Pass | production/dev config; backend, frontend, Flyway, and PostgreSQL images |
| Corpus dry run | Pass | disposable clone of all 52,159 rows; 190 transitions, 15 approved clears, 23 recoveries, no successful rewrite |
| Clone apply and invariants | Pass | 98,851 songs; all consistency checks zero; second dry run has no mutations |
| Live cross-channel sample | Pass | 58/58 records across 50/50 channels; 40 extracts, 1,685 comments, 18 parser successes / 270 songs, 0 blocks/timeouts/cap anomalies |
| Production block diagnosis | Pass | 47 false cooldown triggers were one age-restricted record; same-container public control returned 50 comments and the expected eight-song setlist |
| Feature PR checks | Pending | |
| Release CI and images | Pending | |
| Deployment and backup | Pending | |
| Post-deploy reanalysis | Pending | |
| Independent production verification | Pending | |
