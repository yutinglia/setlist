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
- [x] Require a valid pre-deployment PostgreSQL backup before any production
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
| Total videos | 52,159 | 52,159 | 52,159 |
| Karaoke videos | 6,147 | 6,187 | 6,187 |
| Song videos | 2,678 | 2,724 | 2,724 |
| Other videos | 43,334 | 43,248 | 43,248 |
| Karaoke videos with setlists | 5,841 | 5,849 | 5,849 |
| Setlist success rate | 95.022% | 94.537% | 94.537% |
| Stored songs | 99,233 | 98,851 | 98,851 |
| Unresolved karaoke videos | 306 | 338 | 338 |

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

- [x] Commit only scoped files with a Conventional Commits message.
- [x] Push the feature branch and open a source pull request.
- [x] Wait for all required feature checks and verify the exact PR head.
- [x] After checks pass, squash-merge the feature PR with an exact-head guard
  and verify the resulting `main` commit.
- [x] Compare the merged change against the private deployment control plane.
- [x] If required, update the deployment repository through its own reviewed
  pull request and wait for merge; otherwise record compatibility evidence.
- [x] From clean current source `main`, run the repository patch-version bump
  script and verify that only the three version files change.
- [x] Open, check, and merge the exact-head release pull request without an
  independent approval wait, as explicitly requested by the user.
- [x] Wait for the exact release commit's protected-main CI and CodeQL results.
- [x] Create the immutable annotated tag with the repository script and push
  only that tag.
- [x] Verify all four images, attestations, GitHub Release publication, and the
  exact-tag deployment dispatch.

## Phase 6 — Production deployment and recovery

- [x] Confirm the deployment workflow creates a nonempty mode-`600`
  custom-format backup accepted by `pg_restore --list`.
- [x] Confirm Flyway and all containers deploy the exact release and report
  healthy without unexplained restarts or OOM events.
- [x] Run the stored-data reanalysis dry run on the deployed code.
- [x] Review dry-run totals against the pre-release audit and then apply only
  the approved safe scope.
- [x] Requeue unresolved retryable karaoke records without overwriting existing
  successful setlists.
- [x] Run or wake the normal paced updater; never clear or bypass a persisted
  YouTube cooldown.
- [x] Verify post-apply corpus totals, invariants, setlist success rate, and a
  second idempotent dry run.
- [x] Independently verify public health, deployed release, migration state,
  updater heartbeat/outcome, backup validity, cache policy, and cache hit/TTL
  behavior.
- [x] Return both repositories to clean synchronized `main` branches.

## Phase 7 — Dependabot maintenance and follow-up release

- [x] Audit every open source and deployment Dependabot pull request for
  expected files, trusted commit identity, signature verification, and current
  CI results.
- [x] Rebase the source Dependabot branches onto the current protected `main`
  and wait for checks on their exact heads.
- [x] Merge only exact tested heads without administrator bypass; coordinate
  the matching Valkey digest update in the private deployment control plane.
- [x] Verify that the automated Patch release contains every merged dependency
  update and changes only the three synchronized version files.
- [x] Verify the Patch release images, attestations, deployment backup, exact
  production version, service health, and preserved data invariants.
- [x] Reproduce and repair the `GITHUB_TOKEN` post-merge event suppression gap
  without a PAT, administrator bypass, automated review, or trust in an
  unbound CI result.

## Findings and decisions

### Evidence log

- On 2026-08-27 the user explicitly removed the independent-review wait to
  speed development. Read-only `gh` checks confirmed that neither source nor
  deployment `main` currently has branch protection or an applied branch
  ruleset. Work will still use the non-owner agent identity, pull requests,
  CI, exact-head verification, and the ordered release/tag/deploy gates; it
  will not directly push `main` or use a bypass identity.
- Obsolete source Dependabot PRs #91 and #92 were rebased by Dependabot and
  closed because their requested image versions were already current. The old
  frontend group PR #94 was superseded and closed. Source PR #96 and its
  matching private-control-plane update were rebased, passed exact-head checks,
  and merged without administrator bypass; both now use the same immutable
  Valkey 9.1.1 Alpine digest.
- Replacement frontend group PR #100 updated 15 compatible minor/patch
  dependencies. Its bot commits and generated notice-only commit passed
  provenance and exact-file checks, 87 frontend coverage tests, four
  Playwright flows, the production build, npm audit, security checks, and
  CodeQL. A clean route-generation replay produced no tracked diff. Oxlint
  reports five existing nonblocking style warnings; the dependency update did
  not introduce a build or runtime failure.
- Automated release PR #101 contained only the three synchronized version
  files and merged as `25efa9d`. An annotated `v0.8.2` tag peels to that exact
  fully tested commit. Release run `33010736080` published and verified all
  four images and attestations, created the GitHub Release, and delivered the
  deployment notification. Deployment run `33011042142` created its backup,
  deployed the exact release, and passed its health gate.
- Independent `v0.8.2` verification found a 72,035,886-byte mode-`600`
  custom-format backup accepted by `pg_restore --list`, mode-`600` production
  state files, mode-`700` backup storage, healthy frontend/backend/database/
  cache services with zero restarts or OOM events, and Flyway V14 successful.
  Public `/`, `/updates`, `/channels`, and `/v1/health` returned HTTP 200. A
  real browser switched English to Traditional Chinese to Japanese and back,
  with the document language, localized title, and persisted preference all
  correct and no 5xx or page exception.
- Post-dependency-release data remained exactly 52,159 videos (6,187 karaoke,
  2,724 song, 43,248 other), 5,849 setlists, 98,851 songs, and 338 unresolved
  karaoke records. Orphan songs, non-karaoke songs/setlists, setlist/song
  mismatches, unresolved rows with songs, and duplicate normalized song keys
  are all zero. The durable updater remained in its existing cooldown with a
  fresh heartbeat; deployment did not clear or bypass it.
- `GITHUB_TOKEN` intentionally suppressed the normal `push` workflow after
  #101 auto-merged, so the old release handoff never observed a push CI run.
  The exact merge commit was manually dispatched through CI before tagging.
  The repaired workflow now captures and authenticates the exact release CI,
  revalidates and exact-head merges the three-file bot PR, dispatches exact
  main CI, and queues a bot-only continuation carrying its run id and commit.
  The continuation rejects stale commits, reruns, wrong workflows/events/
  actors, failed CI, unexpected files, and advanced `main` before tagging.

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
- Feature PR #97 merged as `c0fd41b`; release PR #98 changed only the three
  synchronized version files and merged as `9db5505`. The exact release commit
  passed backend, frontend, security, image-build, and CodeQL checks. Annotated
  tag `v0.8.1` peels to that commit; all four images, attestations, the GitHub
  Release, and deployment dispatch completed successfully.
- The private deployment control plane required no source-contract update.
  Its `v0.8.1` deployment created and validated a roughly 72 MB mode-`600`
  custom dump before replacement. All services then reported healthy with zero
  restarts and OOM events, and Flyway remained successfully applied through
  V14. A separate, equally validated pre-reanalysis dump was created before
  the stored-data mutation.
- The deployed dry run exactly matched the clone: 190 reclassifications, 54
  non-karaoke normalizations, 15 approved destructive video ids / 645 songs,
  23 recoveries, 248 unresolved requeues, and no successful-setlist rewrite.
  The atomic apply produced the candidate totals above. Orphan songs,
  non-karaoke songs, success/song mismatches, stale non-karaoke attribution,
  and non-karaoke queue states are all zero; the immediate second dry run has
  zero mutations and requeues.
- Two hard-bounded direct probes from the deployed `v0.8.1` backend used the
  same production egress without touching scraper state. A public control
  returned one requested top-level comment with yt-dlp 2026.08.19. The exact
  age-restricted record still returned its age-confirmation error but the new
  detector classified it as `blocked=false`. A normal one-shot updater then
  honored the existing persisted cooldown and made no upstream call or new
  block report.
- Production cache verification found the intended 80 MiB / `allkeys-lru` /
  5% client policy, equal 128 MiB memory and swap ceilings, and TTLs of
  900/900/3600/300 seconds. Two identical catalog requests succeeded; the
  second incremented cache hits, the exact catalog key existed, and its TTL was
  3,600 seconds. Seventeen generic error replies accumulated over 28 days, but
  there were no rejected connections, evictions, recent cache logs, or error
  increase during verification.
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
- The false-positive cooldown created before `v0.8.1` remains durable until its
  original deadline; it was not manually cleared. New age/member/private/region
  failures no longer extend it, and the normal paced updater resumes after it
  expires.

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
| Feature PR checks | Pass | PR #97 exact-head squash merge; all required checks green |
| Release CI and images | Pass | `v0.8.1` exact commit; four images and attestations verified |
| Deployment and backup | Pass | private workflow green; pre-deploy and pre-reanalysis dumps validated |
| Post-deploy reanalysis | Pass | exact reviewed apply; 23 recoveries, 15 clears, 0 successful rewrites; second dry run empty |
| Independent production verification | Pass | health, V14, runtime, containers, updater, cache hit/TTL, and yt-dlp detector probes |
| Dependabot maintenance | Pass | obsolete PRs closed; exact source/private Valkey heads and 15-package frontend group merged without bypass |
| `v0.8.2` release and deployment | Pass | exact tag, four images/attestations, deployment backup, services, locales, and preserved data invariants |
| Dependency release handoff policy | Pass | Static trust-policy/Ruff checks and exact CI/run/PR/main guards; local `act` schema predates GitHub's 2026 `queue: max`, so GitHub-hosted validation is authoritative; no PAT, review, or administrator bypass |
