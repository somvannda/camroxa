## 1. Execution Strategy
This task plan is ordered to reduce migration risk by establishing the Electron foundation first, then reproducing the current runtime entry flow, and only after that moving into workspace-heavy pages.

### 1.1 Status Legend
- `pending`
- `in progress`
- `completed`
- `blocked`
- `needs review`

### 1.2 Delivery Principles
1. Build the app under `d:\Development\Projects\Electron\MusicGenerator\camxora\`
2. Keep Python/backend as the source of truth
3. Never ship UI-only placeholder routes pretending to be functional
4. Validate route-by-route rather than attempting a big-bang migration
5. Update documentation continuously as scope or architecture changes

## 2. Milestones
| Milestone | Goal | Status |
|-----------|------|--------|
| M1 | Project foundation and desktop shell bootstrap | in progress |
| M2 | Startup, login, register, session restore | completed |
| M3 | Onboarding flow | in progress |
| M4 | Main shell and essential pages | pending |
| M5 | Music, workflow, and progress workspaces | pending |
| M6 | Image workspace | in progress |
| M7 | Video workspace and renderer preview migration | in progress |
| M8 | Packaging, QA, migration hardening | pending |

## 3. Detailed Tasks

### 3.1 Milestone M1 — Project Foundation
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M1.1 | Initialize Electron + React + TypeScript + Vite workspace in `camxora` | none | completed | Workspace scaffolded with Vite template and converted for Electron |
| M1.2 | Configure Tailwind CSS, shadcn/ui, Lucide, ESLint, Prettier, Vitest | M1.1 | in progress | Tailwind, Lucide, ESLint, and Vitest are configured; renderer shadcn `Select` is now added for Settings parity, while fuller shadcn and Prettier setup remains |
| M1.3 | Create Electron main, preload, and renderer folders | M1.1 | completed | Secure process-separated structure is in place |
| M1.4 | Set up route system with desktop-safe router | M1.1 | completed | `HashRouter` route skeleton is live |
| M1.5 | Set up TanStack Query and shared providers | M1.1 | completed | Base app providers added |
| M1.6 | Create shared UI primitives and desktop layout tokens | M1.2 | in progress | Initial button, card, and input primitives exist; shared `AppSelect`, `DatePickerField`, and `InlineToggle` now standardize themed dropdown/date/toggle controls across the renderer while broader token work remains |
| M1.7 | Establish API client abstraction and typed error handling | M1.3 | completed | Platform HTTP client + typed errors are implemented and used by auth/onboarding |
| M1.8 | Set up secure token/settings persistence bridge | M1.3 | completed | Electron main/preload secure storage bridge is implemented |
| M1.9 | Create app shell skeleton with placeholder protected routes | M1.4 | completed | Startup, auth, and shell routes are available |
| M1.10 | Add CI/lint/test scripts for the new app | M1.2 | in progress | `check`, `lint`, `test`, and `build` scripts are working; CI pipeline still pending |

### 3.2 Milestone M2 — Startup, Auth, And Session Restore
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M2.1 | Build splash/startup route and staged bootstrap UI | M1.9 | completed | Real bootstrap runs in main window and drives splash progress via IPC |
| M2.2 | Implement secure session load at launch | M1.8 | completed | Tokens are hydrated from secure storage before route decision |
| M2.3 | Implement session validation and refresh orchestration | M1.7, M2.2 | completed | Refresh + `/users/me` + `/profiles` orchestration gates routing |
| M2.4 | Implement auth route guard and redirect strategy | M1.5, M2.3 | completed | `/app/*` and `/onboarding/*` are protected and redirect on missing/expired tokens |
| M2.5 | Build login page UI | M1.6 | completed | Desktop-focused split/auth card layout implemented |
| M2.6 | Build register page UI | M1.6 | completed | Consistent with login shell implemented |
| M2.7 | Implement login API flow | M1.7, M2.5 | completed | Real backend login + secure token persist + bootstrap rerun |
| M2.8 | Implement register API flow | M1.7, M2.6 | completed | Real backend register + login + route to onboarding |
| M2.9 | Implement immediate logout on `401` globally | M1.7, M2.4 | completed | Global 401 handler clears tokens and routes to auth |
| M2.10 | Implement route decision: auth vs onboarding vs app shell | M2.3, M2.7, M2.8 | completed | `/startup` decides between auth, onboarding, and app shell |
| M2.11 | Add auth form tests and bootstrap routing tests | M2.10 | in progress | Basic auth/startup tests exist; expand coverage for refresh/error scenarios |

### 3.3 Milestone M3 — Onboarding
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M3.1 | Define onboarding step model and route map | M2.10 | completed | Route map now uses the Python-aligned order genre → names → logos → covers → overview |
| M3.2 | Build onboarding shell, stepper, and sticky footer actions | M1.6, M3.1 | completed | Shared desktop header, onboarding sidebar, logout action, and wizard footer are now in place |
| M3.3 | Implement profile identity step | M3.2 | in progress | Primary/secondary names are implemented; persona/basics remain |
| M3.4 | Implement genre/options step | M3.2 | completed | Backend-driven genre list is implemented |
| M3.5 | Implement asset generation step | M3.2, M1.7 | completed | Logo + cover generation now includes Python-parity upload/save actions and the final create payload persists assets through the shared backend create-profile flow |
| M3.6 | Implement overview generation step | M3.2, M1.7 | completed | Final step is now `Overview` with Python-style profile summary, shared SEO generation, and copy helpers using the same backend endpoints |
| M3.7 | Implement review and final create step | M3.3, M3.4, M3.5, M3.6 | completed | Creates both profiles against the backend and routes into the app shell |
| M3.8 | Implement onboarding resume/back navigation behavior | M3.2 | completed | Verified-email restart routing resumes directly into the wizard, completed steps stay clickable, and onboarding draft state now persists in Electron secure storage for same-account recovery |
| M3.9 | Implement success transition into authenticated shell | M3.7 | completed | Routes to `/app/home` after successful creation |
| M3.10 | Add onboarding integration tests | M3.9 | in progress | Coverage now includes full-step navigation, final create payload, overview generation, logo upload, and secure-storage draft hydration/reset behavior |

### 3.4 Milestone M4 — Main Shell And Essential Pages
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M4.1 | Build authenticated shell layout | M2.10 | completed | Shared header, sidebar, content outlet, and footer are implemented |
| M4.2 | Build sidebar navigation config and active route styling | M4.1 | completed | Sidebar order now matches the Python shell route map |
| M4.3 | Build top-level account summary area | M4.1 | completed | Sidebar now shows user avatar/initials, plan, credits, and profile usage |
| M4.4 | Implement dashboard route and data hooks | M4.1, M1.7 | completed | Dashboard now uses live stats/license endpoints for KPIs, resource charts, weekly usage, and recent activity |
| M4.5 | Implement profile route and data hooks | M4.1, M1.7 | completed | Profile page now uses real account, plan, license, usage, and per-profile metadata instead of a thin summary view |
| M4.6 | Implement settings route foundation | M4.1, M1.7 | in progress | `/app/settings` now starts on `Profiles`, mirrors the Python primary settings content groups, replaces native dropdowns with renderer-side shadcn selects across Settings, uses scheduled publication time dropdowns where the batch date provides the date portion, is being hardened so `Preferences` matches the Music Settings logic for paths/workers/image defaults, and now keeps `Pools` as a read-only usage-aware surface while the real content-pool manager moves into the Admin Portal |
| M4.6a | Add Profile Image Mode selector to Settings → Profiles | M4.6 | completed | Settings → Profiles now exposes `profile.image_config.mode` (`bg_thumb`, `bg_only`, `thumb_only`) via a shadcn Select and persists it with profile updates |
| M4.7 | Implement log route foundation | M4.1 | completed | Route foundation exists in the authenticated shell |
| M4.8 | Add essential page tests | M4.4, M4.5, M4.6, M4.7 | in progress | Dashboard, Profile, and the Python-clone Settings route coverage are in place; Log remains foundation-only |

### 3.4.1 Admin Content-Pool Control Plane
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| ACP.1 | Implement admin content-pool manager foundation | M4.6 | completed | Admin Portal page, stats, list, import, edit, delete, clear, and built-in preset generation are live |
| ACP.2 | Add persisted preset-pack schema for content-pool generation | ACP.1 | completed | Added Alembic migration for shared pool tables and `content_pool_preset_packs` JSON-backed storage |
| ACP.3 | Add preset-pack CRUD endpoints and backend generation integration | ACP.2 | completed | Content-pool generation now accepts an optional preset-pack id and the backend exposes preset-pack CRUD routes |
| ACP.4 | Extend Admin Portal content-pool page with preset-pack management UI | ACP.3 | completed | The Content Pools page now manages preset packs inline and the generate dialog can choose `Default Mixer` or a saved pack |
| ACP.5 | Add focused verification and docs for preset-pack flow | ACP.3, ACP.4 | completed | Backend tests, portal typecheck, diagnostics, and development-log updates all pass for the preset-pack slice |
| ACP.6 | Add reservation-based pool consumption guardrails in the runtime | ACP.5 | completed | Pool rows are now claimed before draft generation and only finalized after a successful song record is persisted |
| ACP.7 | Align shared pool normalization and schema for reservation metadata | ACP.6 | completed | Shared migrations and Python DB migration now add reservation columns, and Python normalization matches the stricter backend rule set |
| ACP.8 | Add focused runtime tests and logs for pool reservation flow | ACP.6, ACP.7 | completed | Added focused Python tests for claim/finalize/release plus avoid-list coverage and documented the change in the development log |
| ACP.9 | Add admin reservation-health visibility to content-pool stats and lists | ACP.8 | completed | Admin content-pool stats now report reserved, stale-reserved, and available counts, and list rows include reservation state metadata |
| ACP.10 | Extend Admin Portal content-pool UI with reservation-health badges and details | ACP.9 | completed | The Admin Portal now shows reservation-health badges in the summary cards and row-level reservation state, owner, and timestamp |
| ACP.11 | Verify and document reservation-health visibility | ACP.9, ACP.10 | completed | Backend tests, portal typecheck, diagnostics, and development-log updates now cover reservation visibility |
| ACP.12 | Add centralized content-pool claim/release/finalize API in Platform API | ACP.8 | completed | Added authenticated shared backend endpoints for per-kind claim, release, and finalize so reservation lifecycle no longer depends on Python-only DB helpers |
| ACP.13 | Add focused tests for centralized content-pool claim flow | ACP.12 | completed | Added router tests covering authenticated claim selection plus release and finalize actions |
| ACP.14 | Document shared claim API contract and verification | ACP.12, ACP.13 | completed | Updated design, technical, and development log documents for the centralized claim API slice |
| ACP.15 | Add one-click massive preset-bank autofill for Admin Portal preset packs | ACP.5 | completed | Added a generate icon/button that fills the visible preset fields with built-in 10,000-entry bank suggestions |
| ACP.16 | Add backend support for deterministic massive preset-bank generation | ACP.15 | completed | Admin backend now returns reusable 10,000-entry bank suggestions per preset field without depending on a single LLM response |
| ACP.17 | Verify and document the massive preset-bank autofill flow | ACP.15, ACP.16 | completed | Backend tests, portal typecheck, diagnostics, and development-log updates now cover the one-click generator |
| ACP.18 | Add one-click Generate And Save Massive Pack flow in the preset-pack dialog | ACP.15 | completed | The Admin Portal now supports creating or updating a preset pack in one step after generating the 10,000-entry banks |
| ACP.19 | Auto-fill safe default preset-pack metadata for one-click massive saves | ACP.18 | completed | The one-click shortcut now generates a stable default name and description when the preset metadata is still blank |
| ACP.20 | Verify and document the Generate And Save Massive Pack flow | ACP.18, ACP.19 | completed | Diagnostics, portal typecheck, and development-log updates now cover the one-click save shortcut |
| ACP.21 | Add Generate, Save, And Open shortcut for preset packs | ACP.18 | completed | The preset-pack dialog now opens the pool Generate dialog with the saved pack already selected |
| ACP.22 | Reuse shared preset-pack save results for generation handoff | ACP.21 | completed | The save helper now returns the saved pack so the UI can preselect it for the generation dialog without duplicating API calls |
| ACP.23 | Verify and document the Generate, Save, And Open flow | ACP.21, ACP.22 | completed | Diagnostics, portal typecheck, and development-log updates now cover the generation handoff shortcut |
| ACP.24 | Expand content-pool generator mixing and per-request pre-insert dedupe | ACP.23 | completed | Backend generation now uses broader random template mixing and avoids retrying the same normalized candidate repeatedly within one generate request |
| ACP.25 | Expose duplicate-aware generate summary in Platform API and Admin Portal | ACP.24 | completed | Generate responses now report requested, attempted, inserted, and duplicate-skipped counts so admins can see saturation instead of only raw inserts |
| ACP.26 | Verify and document generation-randomization hardening | ACP.24, ACP.25 | completed | Added focused router tests, portal typecheck, diagnostics, and development-log updates for the randomization and duplicate-summary slice |
| ACP.27 | Add inline generate-result summary panel in the Admin Portal dialog | ACP.25 | completed | The generate modal now keeps the latest requested, attempted, inserted, and duplicate-skipped metrics visible after a run instead of relying on a toast alone |

### 3.5 Milestone M5 — Workflow, Progress, And Music
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M5.1 | Implement workflow route shell and status surfaces | M4.1 | completed | Workflow route now uses the shared progress aggregate feed for run selection, notes, status, and timeline states |
| M5.2 | Implement progress route table, filters, and polling | M4.1, M1.7 | completed | Progress route now has real filters, polling, and a read-only aggregate table backed by `/progress` |
| M5.3 | Implement music route shell and internal tabs | M4.1 | in progress | `/app/music` keeps the correct route ownership and is now being refactored toward strict Python workspace parity for composer/history/session controls |
| M5.4 | Implement music Profiles tab list/detail editor | M5.3, M1.7 | completed | Deprecated route ownership was removed from `/app/music`; equivalent functionality now lives in `/app/settings` |
| M5.5 | Implement music Publication tab | M5.3, M1.7 | completed | Deprecated route ownership was removed from `/app/music`; equivalent functionality now lives in `/app/settings` |
| M5.6 | Implement music Settings tab | M5.3, M1.7 | completed | Deprecated route ownership was removed from `/app/music`; equivalent functionality now lives in `/app/settings` |
| M5.7 | Implement profile limit gating UX in music route | M5.4 | completed | Create flow is disabled when the backend-reported profile allowance is reached |
| M5.8 | Add workflow/progress/music tests | M5.1, M5.2, M5.6 | pending | Include gating, empty states, and composer actions |

### 3.5.1 Next Music Slice
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M5.C1 | Add composer session controls to `/app/music` | M5.3 | completed | Music route now includes language, creativity, song count, and profile pairing controls backed by real state |
| M5.C2 | Add description/structure editors and draft preview | M5.C1 | completed | Uses `/generation/draft` and `/generation/polish-lyrics` with live draft editing |
| M5.C3 | Add batch create action and batch status polling summary | M5.C1 | completed | Uses `/batches` and `GET /batches/{batch_id}` for live status without fake filesystem actions |
| M5.C4 | Extend batch creation with date-range planning controls and backend validation | M5.C3 | completed | `from_date` / `to_date` are now part of the batch contract, persisted on `batches`, and validated on both client and server |
| M5.C5 | Implement dedicated music history API contract and renderer history panel | M5.C3 | completed | `/music/history` now drives a read-only history surface using existing batch/song/Suno/image/YouTube tables |
| M5.C6 | Run live verification for composer, date-range batch flow, and history loading | M5.C4, M5.C5 | needs review | Targeted backend tests and renderer type-checks pass; runtime boot and route registration are verified, while authenticated end-to-end Music interaction still needs manual sign-in validation |
| M5.C7 | Refactor `/app/music` to Python workspace parity | M5.C6 | needs review | Python-style one-screen composer/history layout now replaces the older summary surface; remaining review is manual signed-in validation and backend-limited row backfill/actions |
| M5.C8 | Restore Python-style multi-channel section behavior in Electron Music | M5.C7 | completed | Music now supports ordered multi-selection for Primary and Secondary channels and fans out one generate action into multiple `/batches` calls using the existing single-pair contract while keeping description/structure dropdown-only |
| M5.C9 | Align Electron draft generation with pool-seeded Python flow | M5.C7 | completed | Electron `Draft` now claims title/album/opening seeds from shared content pools, injects them as inspiration plus forced opening into `/generation/draft`, finalizes reservations on success, and charges once through the routed `lyric` pricing path |
| M5.C10 | Expand music history contract and renderer backfill toward Python parity | M5.C7 | completed | `/music/history` now returns lyrics, description/structure IDs and names, and OK/ALT output folders so row selection can hydrate the editor and open channel folders like Python |
| M5.C11 | Audit Music endpoint reuse versus backend gaps before implementation | M5.C8, M5.C9, M5.C10 | completed | Existing `/generation/*`, `/batches`, `/settings`, `/music/history`, and `/content-pools/*` contracts were reused where possible; a small user-safe `/credits/operation-costs` endpoint was added so Electron can display admin-configured costs resolved through AI routing without exposing the admin pricing manager |
| M5.C12 | Resolve hidden Admin prompt content for batch orchestration and surface total batch credits in Generate CTA | M5.C8, M5.C9, M5.C11 | completed | `BatchService.orchestrate_drafts()` now resolves stored `description_id` / `structure_id` to hidden Admin prompt content when drafting songs, and the Music `Generate` area now follows the Python-style `planned days × channel pairs` batch model while showing the total routed batch estimate using draft + Suno only when `Auto-GSuno` is enabled and, when enabled, image-generation credits |
| M5.C13 | Align Auto-GSuno batch intent and cost gating with the Electron Music toggle | M5.C12 | completed | `auto_gsuno` is now persisted on batch requests/storage and the Music credit totals only add Suno when the run enables `Auto-GSuno` |
| M5.C14 | Verify public batch execution path for real Auto-GSuno orchestration | M5.C13 | completed | Confirmed `POST /batches` only persisted batch/song rows and that callback wiring also lacked a clean batch-service handoff for song/image progression |
| M5.C15 | Start real batch execution after public batch creation | M5.C14 | in progress | Keep the current UI contract, but make `POST /batches` schedule backend execution in a background task, submit Suno only when `auto_gsuno` is enabled, and route callback completion back through batch-service status/image handling |
| M5.C16 | Add OK/ALT Suno audio download flow in the desktop app (not Platform API) | M5.C15 | in progress | Platform API now exposes pending desktop download work and sync endpoints, while Electron main downloads Suno MP3s with retry/existing-file checks into deterministic run dirs; richer Progress/Merger runtime truth still remains |
| M5.C17 | Validate Suno callback reachability and production callback base URL strategy | M5.C15 | pending | Recommend `https://api.camxora.com/api/v1/callbacks/suno` as the production callback URL, require public reachability, and document dev testing guidance (HMAC simulation / temporary tunnel) |
| M5.C18 | Insert explicit `Merger` stage into Progress/Workflow pipeline semantics | M5.C16 | in progress | Progress and Workflow now read local run-directory MP4 and merged outputs through the Electron desktop bridge so converter/merger status is no longer API-placeholder-only; Music auto-toggles still need pipeline orchestration before they can be enabled honestly |
| M5.C19 | Differentiate Workflow vs Progress UX so they are complementary, not duplicate | M5.C18 | completed | Workflow now uses a visual single-run board with a left run picker and stage cards, while Progress uses one operational toolbar plus the dense recovery table; both pages now share the same themed date/toggle/dropdown controls instead of mixed native browser widgets |
| M5.C20 | Refine Workflow into a best-fit mission-control board | M5.C19 | completed | Workflow now uses a compact filter rail, a denser left lane list, a selected-run hero surface, and a cleaner stage board/empty-state flow so it reads like a visual monitor instead of another stacked dashboard |

### 3.6 Milestone M6 — Image Workspace
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M6.1 | Implement image route shell | M4.1 | completed | `/app/image` now uses a real Image workspace page instead of a placeholder route |
| M6.2 | Implement prompt/config form state | M6.1 | completed | Initial Image page supported single-image generation + per-profile defaults; superseded by Python-style queue UI parity |
| M6.3 | Integrate image generation API flows | M6.1, M1.7 | completed | `POST /generation/image` remains available for ad-hoc generation, while Python-style batch job execution uses `image_jobs` + server-side runner |
| M6.4 | Build result gallery and history surfaces | M6.3 | completed | Replaced by Python-style previews that load generated BG/TH outputs per queue row; progress feed remains supplemental |
| M6.5 | Add image route tests | M6.4 | in progress | Python-parity layout tests are in place; expand coverage for queue actions, previews, and error states |
| M6.6 | Audit Python Image tab parity and map missing features | M6.4 | completed | Python Image workspace is DB/job-queue-driven with batch selection, BG/TH statuses, prompt preset manager, random sample selection, and a background worker; Electron Image workspace is currently a single-image generator + profile defaults + progress feed |
| M6.7 | Add Platform API endpoints for image job queue visibility | M6.6 | completed | Added authenticated `GET/POST` queue endpoints under `/api/v1/image-jobs` for list/enqueue/run/retry/clear |
| M6.8 | Add Platform API image-job execution service (Python worker parity) | M6.7 | completed | Implemented server-side `ImageJobService` to process pending jobs, write PNG outputs, and persist status/errors without double-charging prepaid batch jobs |
| M6.9 | Wire Suno callback → image-job execution (optional auto pipeline) | M6.8 | completed | Suno SUCCESS callbacks now schedule the image job runner for the owning batch when `batch.auto_gen_image=true` |
| M6.10 | Refactor Electron Image tab to mirror Python workflow | M6.7 | completed | Rebuilt Image workspace around the real queue workflow, then refined it into a queue-first execution page with date filters, stacked previews, and no visible batch table while moving sample curation into `Preferences` |
| M6.11 | Add full backend + renderer verification for Image parity slice | M6.8, M6.10 | needs review | Backend/router tests + renderer tests/typecheck exist; still needs signed-in manual QA for enqueue/run/retry/preview and callback-driven automation |
| M6.12 | Redesign Image layout to place queue beside previews | M6.10 | completed | Queue stays beside the stacked BG/TH previews. Prompts live below the queue so browsing stays above the fold. |
| M6.13 | Add dual prompt controls for background and thumbnail generation | M6.12 | completed | Replaced the single Image prompt with `imageBackgroundPrompt` and `imageThumbnailPrompt`, persisted from the renderer with legacy fallback from `imagePrompt` |
| M6.14 | Extend image-job model for reference-image workflows | M6.13, M6.8 | completed | Added `input_image_path`, `style_reference_path`, and `source_job_id` to image-job persistence so jobs can track sample-library references and chained background dependencies |
| M6.15 | Implement background → thumbnail chaining in image runner | M6.14 | completed | The runner now loads a background sample/base image when available and waits for source background output before generating dependent thumbnail jobs |
| M6.16 | Add sample-pack download/install flow in user app | M6.12 | completed | Preferences now loads `/image-sample-packs`, lets users pick a pack per category, installs it into BG/TH sample folders, and refreshes the sample library automatically |
| M6.17 | Add admin-managed sample-pack link manager in Admin Portal | M6.16 | completed | Admin Portal now supports full CRUD for `/admin/image-sample-packs`, with multiple named entries per category and activation/sort order |
| M6.18 | Verify queue redesign + chained image generation end-to-end | M6.12, M6.15, M6.16, M6.17 | pending | Validate queue selection, previews, dual prompts, BG→TH chaining, download/extract, and callback-driven automation together in signed-in QA |
| M6.19 | Remove manual Generate Now UX | M6.12 | completed | Image workspace is automation-first (no manual generation CTA); it remains a queue monitor + retry/clear recovery surface |
| M6.20 | Move prompts below queue | M6.12 | completed | Background + Thumbnail prompts now sit under the queue list inside the same left control card |
| M6.21 | Add “Image Source Mode” (AI vs User-Provided) and folder guidance | M6.10 | in progress | Preferences now exposes the global AI vs Manual mode selector, and manual mode now plans the same paired run dirs as the AI pipeline and persists them on each batch; downstream bypass logic is still pending |
| M6.22 | Implement user-provided BG/TH ingestion + job bypass logic | M6.21 | in progress | Manual mode now skips AI image-job creation, syncs ready manual assets into success image state, and removes image-credit charging in Manual mode; downstream long/reel video consumption of the paired manual files still remains |
| M6.23 | Add Progress-page manual-image alerts and “Continue Pipeline” affordance | M6.21, M6.22 | in progress | Progress now shows missing/ready manual-image alerts per batch/profile/role using the persisted batch run dir, opens the prepared folder, and exposes a real backend sync action that advances ready rows out of the Image waiting stage |
| M6.24 | Add batch-channel asset manifest and long/reel readiness contract | M6.22, M6.23 | in progress | Persist the full four-file BG/TH asset set per batch/profile/role and expose separate long-video and reel readiness instead of collapsing everything into a single representative image path |

### 3.7 Milestone M7 — Video Workspace And Renderer Preview Migration
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.1 | Finalize video control-page information architecture | M4.1 | completed | Phase 1 locks a read-only workspace layout around template snapshot, assets, playback/export status, and next-phase preview notes |
| M7.2 | Build video route layout in React | M7.1 | in progress | `/app/video` must match the Python Video workspace arrangement exactly: left rail, center preview/playback/export stack, and right inspector rail using the same section order and operator flow |
| M7.3 | Define preview bridge protocol | M7.1, M1.3 | blocked | Native Python embed protocol exists as an experimental branch, but Boss selected Option B so this track is frozen and no longer the target architecture |
| M7.4 | Implement Electron-side preview bridge service | M7.3 | blocked | Existing main/preload preview IPC remains as legacy/frozen work and should not receive new feature investment |
| M7.5 | Implement Python preview controller entrypoint | M7.3 | blocked | Experimental stdin/embed entrypoint is retained only as prior work; it is not the future preview path |
| M7.6 | Implement preview session and host-binding commands | M7.4, M7.5 | blocked | Win32 host-binding path is frozen because Option B replaces native embed with a renderer-owned preview |
| M7.7 | Implement real-time control updates from React to Python | M7.2, M7.6 | blocked | Real-time control streaming now moves to the new renderer preview engine instead of Python preview |
| M7.8 | Implement preview status feedback in UI | M7.6 | blocked | Existing status UX remains legacy until the renderer preview provider replaces it |
| M7.9 | Add video route and preview integration tests | M7.8 | blocked | Native preview lifecycle tests are superseded by renderer preview lifecycle and parity tests |
| M7.10 | Add long + reel output parity (16:9 and 9:16) including auto-merge rules | M7.2 | pending | Support both aspect ratios as first-class outputs; detect user image dimensions and drive video conversion + merge for both long and reel variants, including `Auto Merge` for long and `Auto Reel` / reel merge when enabled |
| M7.11 | Pre-create per-batch output folders before downstream pipeline starts | M5.C15, M6.21 | in progress | The desktop app now plans the same paired run dirs used by the AI pipeline, passes them during batch creation, and persists them on the batch so manual-folder inspection never has to guess; downstream execution/resume semantics still remain pending |
| M7.12 | Wire video-route pipeline input resolver to batch-channel assets | M6.24, M7.2 | completed | The Video route now consumes canonical long/reel inputs from `batch_channel_assets` instead of generic settings background paths |
| M7.13 | Add desktop export coordinator using the Python visualizer CLI | M7.12 | completed | Electron main/preload now expose start/stop export commands, the Video route can launch long or reel exports from canonical pipeline runs, and the workspace keeps progress plus the last output path visible after completion; merge/live preview transport remain pending |
| M7.14 | Clone Python Video workstation UI into Electron while preparing for renderer-owned preview | M7.13 | in progress | Implemented Layer tab (replacing Text tab), compact center text-layer manager, right-rail `Text / Animation / Export` inspector tabs, compact playback row, and live background asset picking; the next phase replaces Python-owned preview with a renderer preview engine mounted inside the same center slot |
| M7.15 | Add desktop merge coordinator for long outputs | M7.13, M5.C18 | in progress | Electron main now performs real long-output merge work from exported MP4s with Python-style validation, shuffle/order logging, and FFmpeg copy-then-reencode fallback; Progress/Workflow runtime consumption still remains |
| M7.16 | Revamp Text overlays (CapCut-style) + unlock unlimited overlays | M7.14 | completed | Adds a list-based text-layer manager (add/duplicate/delete/reorder), preset templates, and updates Python template normalization + renderer to support unlimited `textOverlays` |
| M7.17 | Compact Video Export Queue UI (Actions/Status) | M7.14 | completed | Tighten layout, spacing, and control density for the Export Queue block while preserving the Python arrangement and existing export runtime wiring |
| M7.18 | Add desktop reel merge coordinator and `Auto Reel` parity | M7.15 | in progress | Electron main now performs separate reel-output merge work with `MERGED_REEL_*` naming and branch-aware merge gating; full Music auto-toggle parity and downstream stage consumption still remain |
| M7.19 | Turn Music automation toggles into real downstream desktop actions | M5.C16, M7.15, M7.18 | in progress | The global Electron coordinator is mounted; the current hardening pass now focuses on gating against real downloaded MP3 readiness, active export/merge state, and deterministic long-first then reel-after-long branch scheduling before final honest toggle sign-off |
| M7.20 | Add post-merge YouTube upload parity for Electron | M7.15, M7.19 | in progress | Added the lane-level merged-output enqueue contract, the real `platform_api` upload worker entrypoint (`POST /api/v1/youtube/uploads/run`), queue claim/run status transitions, honest Progress handling for queued/running/blocked states, and the Electron shell hook that detects long merged outputs, enqueues lane uploads, and kicks the worker with cooldown guards; remaining work is signed-in end-to-end desktop validation before the `Auto-Upload` toggle can be enabled honestly |
| M7.21 | Freeze Python preview path and document Option B migration boundary | M7.14 | completed | Native preview debugging artifacts are removed, legacy preview IPC stays frozen, and the source-of-truth docs now treat renderer preview as the forward path |
| M7.22 | Define renderer preview engine contract and migration plan | M7.12, M7.14, M7.21 | completed | Locked the renderer-owned scene/state boundary around `VideoWorkspacePage`, `TemplateSettingsDraft`, local asset resolution, capability detection, and phased preview/export parity so implementation can proceed without touching Python live preview |
| M7.23 | Add renderer preview foundation in the Video preview slot | M7.22 | in progress | The center pane now mounts a renderer-owned preview foundation that lives entirely in React, resolves local assets safely, and replaces the frozen Python live-preview session wiring in the current slot; Boss has now approved a WebGPU-only spectrum direction instead of keeping a Canvas rollback path |
| M7.24 | Implement background + logo layers in renderer preview | M7.23, M7.12 | in progress | First compositor slice is now live: background and logo are no longer mounted as DOM preview layers, and the WebGPU surface now owns the visible preview output through a compositor-fed backdrop texture with image transforms, logo masking, and attachment-aware placement |
| M7.25 | Implement audio analysis + spectrum renderer in the new preview engine | M7.23, M7.12 | in progress | The renderer preview now uses local MP3 Web Audio analysis, shape-aware logo attachment clearance, and a curated `Spectrum Preset` recipe flow with distinct `Straight Bars`, `Flying Glow`, `Dot Matrix`, `Wave Ribbon`, `Liquid Mass`, and `Halo Stack` looks; the active direction is to rebuild the whole live preview around one WebGPU compositor, with the spectrum staying on a linear-bar foundation and `Curve 180` / `Mirror 360` driving arc/ring behavior |
| M7.26 | Implement particles/reactivity layer in the new preview engine | M7.25 | in progress | Particle logic is no longer allowed to return through a legacy Canvas path; the engine-first next slice is a native WebGPU particle simulation/render pass inside the compositor before any non-blocking workstation polish resumes |
| M7.27 | Implement text layer + animation parity in the new preview engine | M7.16, M7.23 | in progress | Text timing and presentation now render into the compositor-fed backdrop instead of mounted DOM overlays; remaining work is renderer-fidelity tuning, richer typography/shader treatment, and export-parity QA against Python |
| M7.28 | Implement preview effects/compositing stack | M7.24, M7.25, M7.26, M7.27 | in progress | The live preview now composites background, native GPU smoke/vignette, logo, timed text, particles, and spectrum through one WebGPU surface; post-FX bloom is a native engine pass with scene-driven tuning (threshold/knee/intensity/strength/blur), and the renderer also owns a visible no-background fallback scene for engine validation, with remaining work focused on bloom tuning refinement plus deeper native migration of logo/text fidelity so fewer layers rely on CPU raster upload |
| M7.29 | Bind existing Video controls to the renderer preview provider | M7.24, M7.25, M7.26, M7.27, M7.28 | in progress | Preview playback buttons and scrubber now issue typed renderer transport commands and stay synchronized with renderer-reported playback state; playback-timed text visibility/animation is now implemented in the renderer preview and the next hardening slice routes honest WebGPU-only status back into the preview status surface |
| M7.30 | Add renderer preview lifecycle, capability, and parity tests | M7.29 | pending | Cover capability detection, WebGPU-only behavior, scene updates, and preview/export mismatch reporting |
| M7.31 | Audit Python export parity against the renderer preview engine | M7.28, M7.30 | needs review | Audit completed and partially addressed: core spectrum semantics are partially aligned, logo attachment/zero-gap is now first-pass implemented in Python export, curated preset/export recipe identity is now first-pass implemented in Python export, and text timing is now first-pass implemented in Electron preview but still needs renderer-fidelity tuning against Python |
| M7.32 | Design long-term export migration away from Python preview ownership | M7.31 | pending | Define how the renderer engine can become the future render source without breaking current export/merge/upload flows |

### 3.6.X Renderer Preview Engine Core Modules (Tracking)
This checklist tracks the target “core modules” as responsibilities. The current engine is functional but several modules are still merged into a few large files. The goal is to tackle these one-by-one without reintroducing a second preview backend.

| Module | Status | Primary Location Today | Next Work |
|--------|--------|------------------------|-----------|
| PreviewProvider | partial | `features/video/preview/PreviewProvider.tsx` + `features/video/preview/RendererVideoPreviewSurface.tsx` + `features/video/RendererVideoPreview.tsx` | Provider and presentation shell are extracted, and `RendererVideoPreview.tsx` is now reduced to helper exports plus the thin wrapper entrypoint |
| CapabilitySelector | partial | `features/video/useRendererVideoPreview.ts` | Keep WebGPU-only; add richer diagnostics instead of WebGL2 fallback |
| SceneStateAdapter | partial | `features/video/preview/previewScene.ts` + `features/video/preview/spectrumAdapter.ts` + `features/video/preview/particleAdapter.ts` | Immutable preview scene payload is now extracted, and the old compatibility adapter is removed; continue moving remaining normalization and GPU-node payload shaping out of the component |
| AssetManager | partial | `features/video/useRendererVideoPreview.ts` | Add explicit decode/cache/lifetime ownership |
| RenderSurface | implemented | `features/video/webgpu/webgpuSpectrumRenderer.ts` | Continue expanding pass graph (native nodes + post-FX) |
| AudioEngine | implemented | `features/video/RendererVideoPreview.tsx` | Extract runtime module when stable |
| TransportClock | partial | `features/video/RendererVideoPreview.tsx` | Extract timeline/clock module and remove implicit coupling |
| BackgroundNode | partial | `features/video/RendererVideoPreview.tsx` | Move from CPU raster upload to native GPU sampling |
| LogoNode | partial | `features/video/RendererVideoPreview.tsx` | Move from CPU raster upload to native GPU sprite + masking |
| SpectrumNode | implemented | `features/video/RendererVideoPreview.tsx` + `webgpuSpectrumRenderer.ts` | Polish parity + add more GPU-native shaping |
| ParticleNode | partial | `features/video/preview/particleAdapter.ts` + `features/video/webgpu/webgpuSpectrumRenderer.ts` | Move simulation to GPU later; add emitter fidelity now |
| TextNode | partial | `features/video/RendererVideoPreview.tsx` | Move to native GPU text later |
| AtmosphereNode | implemented | `features/video/webgpu/webgpuSpectrumRenderer.ts` | Tune quality + add reactive atmosphere hooks |
| PostFXComposer | implemented | `features/video/webgpu/webgpuSpectrumRenderer.ts` | Tune bloom + add color grading/noise later |

### 3.7.1 Video Parity Matrix And Fix Order
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.P1 | Lock Video parity policy: keep Electron UX improvements, port Python render/output semantics only where missing | M7.31 | completed | Electron remains the product UX; Python remains the temporary render/export reference |
| M7.P2 | Port Python spectrum audio-analysis semantics into the Electron renderer | M7.P1 | needs review | Renderer preview now uses Python-like 64-bin log-frequency mapping, smoothing, mirrored layer derivation, and bass/kick-reactive energy, but still needs signed-in visual QA against the Python reference |
| M7.P3 | Align Electron spectrum preset families with Python-native preset identities before further style tuning | M7.P2 | needs review | Renderer preview now preserves Python-native style semantics like `thin-lines`, `symmetrical-bars`, `pixel-bars`, `floating-blocks`, `mountain`, `liquid`, and `neon-pulse` under the compact Electron preset UX, but still needs signed-in visual QA/tuning against the Python reference |
| M7.P4 | Upgrade Electron spectrum rendering backend/compositing toward Python-native glow and blend behavior | M7.P2 | in progress | Renderer preview now uses Python-inspired multi-pass glow/body rendering and additive blend handling for spectrum layers, but the approved direction is no longer to tune Canvas2D; the active migration path is a WebGPU-only linear-bar compositor foundation with curve/mirror semantics driving 180/360 presentation |
| M7.P4a | Audit the WebGPU spectrum engine against premium-look requirements and identify fake/non-honored layer semantics | M7.P4 | completed | Audit confirmed the main blockers are renderer-side: curated families still collapse into the same primitive family, while `fillCircle`, `gradientDirection`, and `blend_mode` are not yet honored strongly enough in the active GPU path |
| M7.P4b | Implement distinct WebGPU spectrum family variants and smoother premium gradient rendering | M7.P4a | in progress | First revamp slice should make `Straight Bars`, `Flying Glow`, `Dot Matrix`, `Wave Ribbon`, `Liquid Mass`, and `Halo Stack` look structurally different in the renderer rather than only numerically different in inspector values |
| M7.P4c | Separate normal-body rendering from luminous additive rendering inside the WebGPU spectrum compositor | M7.P4b | pending | Prevent all layers from reading as the same additive neon wash and preserve cleaner premium contrast between body and glow |
| M7.P4d | Increase spectrum bin contrast and reduce over-soft rendering so reactive height separation stays crisp | M7.P4b, M7.P4c | in progress | Lower artificial value floors, reshape analysed bins for clearer separation, and keep preset body rendering cleaner before glow softening is applied |
| M7.P4e | Final-tune premium family behavior for `Wave Ribbon`, `Liquid Mass`, `Halo Stack`, and scene bloom thresholds | M7.P4b, M7.P4c, M7.P4d | in progress | Deepen family-specific motion/body/light hierarchy and keep bloom supportive rather than flattening all premium families into one luminous wash |
| M7.P4f | Upgrade `Straight Bars` into the flagship premium bar preset with dedicated shader material and tighter bloom discipline | M7.P4b, M7.P4c, M7.P4d | in progress | Give the default bar preset cleaner spacing, brighter peak-tip energy, sharper body definition, and restrained premium glow instead of leaving it on the generic capsule branch |
| M7.P4g | Tune `Straight Bars` “smooth premium motion” profile (slower release, softer gate, less global pumping) | M7.P4f | in progress | Ensure bars do not all move together; prefer smooth premium motion while preserving band separation and contrast |
| M7.P4h | Rebuild `Flying Glow` as a true wing preset rather than a generic glow bar variant | M7.P4b, M7.P7g | in progress | Add arc-native wing envelope, shoulder flare bias, center dip, and faster transient lift so the preset reads closer to Vizzy-style wing/cat-ear motion |
| M7.P4i | Make `Flying Glow` pulse collapse quickly between kicks and expose Solid Color more clearly in the Spectrum color editor | M7.P4h, M7.P7f | completed | `Flying Glow` now uses a style-aware collapse envelope so the wing falls back between beats, and the Spectrum layer UI now labels `Color Style` with explicit `Solid Color` / `Gradient` guidance |
| M7.P4j | Tighten `Flying Glow` into a near-solid continuous wing with minimal visible gaps between bars | M7.P4h, M7.P4i | completed | Increased the wing-family bar count, widened the wing-body width bias, and nudged the preset width so `Flying Glow` reads as a smooth continuous surface rather than separated ribs |
| M7.P4k | Make `Flying Glow` keep an evenly rounded resting ring around the logo and reserve large wing flare for active music/kick moments | M7.P4i, M7.P4j | completed | Separated the uniform resting ring from dynamic wing flare, so the circle stays balanced around the logo at rest while kick-driven shoulder lift opens and collapses on music and bass-drop hits |
| M7.P4l | Make `Flying Glow` use a subtle full-circle waveform bed for normal music and reserve the large wing flare for kick/bass-drop hits | M7.P4k | completed | Split `Flying Glow` into a circular waveform bed driven by general music energy and a separate kick/drop-dominant shoulder flare so the ring breathes continuously but only opens into the larger wing on transient hits |
| M7.P4m | Add a new rounded circular bar preset that reacts around the logo with distributed music motion | M7.P4b | completed | Added `Orbital Bars` as a separate curved mirrored rounded-bar preset with circular gradient, full-ring motion, and its own curated preset identity instead of reusing `Flying Glow` |
| M7.P4n | Fix shared audio-analysis flattening so all spectrum families show clearer per-instrument spike separation | M7.P4d, M7.P4e, M7.P4m | completed | Extended adaptive per-bin baseline removal and local accent shaping across spectrum families, added style-aware analyser profiles, and reset analyser history on family switches so the renderer no longer reacts as one average bed with weak instrument spikes |
| M7.P4o | Rebuild the equalizer around a standard analysis pipeline with shared feature extraction and style-level rendering adapters | M7.P4d, M7.P4e, M7.P4n | completed | Added a dedicated audio-analysis module with perceptual band mapping, shared energy/transient/kick/drop feature extraction, and style adapters so all spectrum families now consume the same base audio model while keeping the existing UI contract stable |
| M7.P4p | Revamp the Spectrum audio-control UI and persisted draft contract to match the new equalizer engine | M7.P4o, M7.P7 | completed | Replaced the legacy spectrum audio controls with `Input Gain`, `Band Contrast`, `Transient Focus`, `Kick Impact`, and `Motion Smoothing`, updated the draft/session/persistence contract, and kept backward fallback for older saved templates and session snapshots |
| M7.P4q | Fix post-revamp spectrum height range so bars can grow taller and local spikes separate more clearly | M7.P4o, M7.P4p | completed | Added post-shaping height-range expansion in the new audio engine, increased spectrum geometry headroom by family, and raised the `Spike Height` slider ceiling so bars no longer stay trapped short and local peaks separate more clearly |
| M7.P4r | Add per-band onset-delta shaping to the spectrum engine without collapsing families into one global beat pulse | M7.P4o, M7.P4q | completed | Added slow per-band baseline tracking plus onset-delta extraction in the shared audio-analysis module, blended the onset layer into base band shaping, and kept global kick/drop helpers style-specific so local spikes separate more clearly without whole-strip pumping |
| M7.P4s | Make Audio Engine controls read clearly in the live spectrum and restore visible `Flying Glow` motion | M7.P4r | in progress | Harden the shared analyzer and family adapters so `Input Gain`, `Band Contrast`, `Transient Focus`, and `Kick Impact` all create obvious visible differences across curated families, while `Flying Glow` regains an honest resting ring plus clear circular/wing reaction under normal playback; the current deep fix now adds a minimum-close retrigger gate so rapid repeated hits cannot reopen the wing while it is still visually too open, forcing a clearer close-then-reopen rhythm during fast `beb beb beb` patterns |
| M7.P5 | Close export-tab functional parity gaps without regressing current Electron workflow | M7.P1 | pending | Finish honest page wiring for thumbnail generation, speed/workers, auto-merge/reel toggles, merge stop, and manual MP3-folder workflow where needed |
| M7.P6 | Audit and port remaining Python output-critical semantics that Electron preview already diverged from | M7.P2, M7.P4, M7.P5 | needs review | Audit completed and first follow-ups landed: logo attachment/zero-gap and curated preset/export recipe handling are now first-pass implemented in Python export, while the highest-priority remaining truth gaps are renderer-fidelity tuning, strict visual QA, and branch-output parity follow-up |
| M7.P7 | Revamp the Video route into a preview-first workstation shell without changing the underlying preview/export contracts | M7.P4, M7.P5 | in progress | Reorganize the route so template/run context and visual-system controls live in the left rail, preview/transport/assets/text stay in the center, and text/export inspection remains in the right rail |
| M7.P7a | Remove redundant spectrum-preset apply UX and let one preset selector own the recipe change | M7.P7 | in progress | Avoid “Spectrum Preset” plus an extra “pick preset” interaction that does not add value |
| M7.P7b | Make the center preview consume resolved pipeline branch backgrounds when no manual preview background is chosen | M7.P7 | in progress | Prevent the Video route from showing loaded background context while the compositor still falls back to the default dark scene |
| M7.P7c | Keep curated spectrum presets single-layer by default and let the Spectrum tab layer panel own stacked look authoring | M7.P7 | in progress | The user should start with one layer only; additional layers are explicit authoring actions through Add or Duplicate inside the Spectrum surface |
| M7.P7e | Consolidate spectrum-layer editing into the Spectrum tab and remove the standalone Layer tab | M7.P7c | in progress | Reduce duplicate “sources of truth” by placing preset selection + layer editing in one tab and leaving only `Spectrum`, `Background`, `Logo`, `Particles` tabs |
| M7.P7d | Keep preview background and logo visibly rendered through a reliable shell-layer path when Electron local asset upload is flaky | M7.P7 | in progress | The live Video route should not show a black background or missing logo just because the GPU texture handoff is inconsistent for desktop file assets |
| M7.P7f | Preserve a local spectrum editing session without auto-writing every tweak back into the saved template | M7.P7e | in progress | Spectrum controls should update the live preview immediately, survive same-app refresh/remount, and only persist to the template when Boss clicks an explicit save action |
| M7.P7g | Add a bass-drop helper control for premium kick transient shaping, especially for 180/360 wing-like looks | M7.P4g, M7.P7f | in progress | Add a dedicated helper that creates a fast bass-hit flare with quick decay so ring/wing looks read more alive without duplicating sensitivity/dynamics |
| M7.P7h | Make background and logo preview behavior truthful and premium on the current hybrid renderer path | M7.P7d, M7.24 | in progress | Ensure the live preview uses the same motion, smoothing, opacity, pulse, and placement semantics whether background/logo are shown through the compositor texture path or the temporary DOM shell fallback |

### 3.8 Milestone M8 — Packaging, QA, And Hardening
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M8.1 | Configure production build and packaging | M1.1 | pending | Installer and app metadata |
| M8.2 | Add environment configuration strategy | M1.1 | pending | Dev/staging/prod base URLs |
| M8.3 | Run route-by-route QA pass | M2.11, M3.10, M4.8, M5.8, M6.5, M7.9 | pending | Record parity gaps |
| M8.4 | Validate auth expiration and recovery behavior | M8.3 | pending | Must match product rule |
| M8.5 | Validate preview stability across resize/move/multi-monitor | M7.9 | pending | Especially important for video route |
| M8.6 | Prepare migration sign-off checklist | M8.3 | pending | Confirm readiness for user rollout |

### 3.9 Active Hardening Items
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| H1 | Add MailHog to `start-services.ps1` with ownership-aware start/reuse logic | M1.1 | completed | Reuses existing MailHog safely and only tracks owned MailHog for later stop |
| H2 | Add `stop-services.ps1` for owned process cleanup including optional MailHog stop | H1 | completed | Stops only script-owned services and leaves reused MailHog running |
| H3 | Expose email-confirmed state to Electron bootstrap/onboarding | M2.10, M3.8 | completed | Verified users now skip redundant confirm-code routing on restart |
| H4 | Rebuild onboarding entry UX with professional verification code inputs and shared header continuity | M3.2 | completed | Shared desktop header is restored and the confirm page now uses six dedicated code inputs |
| H5 | Add onboarding logout path and verified resume behavior | H3, H4 | completed | Onboarding includes logout and verified users resume directly into the wizard |

### 3.10 Video Effect Domain Isolation And Marketplace Architecture
| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A1 | Audit current Video workspace coupling between spectrum, background, logo, particles, assets, and preview runtime | M7.28 | completed | Verified hotspots: `RendererVideoPreview.tsx`, `VideoWorkspacePage.tsx`, and `settingsTemplateDraft.ts` still act as shared orchestration surfaces |
| M7.A2 | Split the current shared draft into domain-owned settings contracts for Spectrum, Background, Logo, Particles, Text, and Atmosphere | M7.A1 | completed | Completed through `M7.A2.1` to `M7.A2.5`: preview/runtime and scene/binding helpers now consume domain-owned or preview-owned draft contracts, and `settingsTemplateDraft.ts` is restricted to workspace compatibility flows. |
| M7.A3 | Introduce a scene-composition boundary that assembles immutable domain scene nodes instead of letting domains read each other directly | M7.A1 | completed | Completed through `M7.A3.1` to `M7.A3.5`: preview/runtime now consumes immutable scene nodes, intentional cross-domain edits stay behind explicit binding helpers, and boundary audits enforce the scene layer as the valid composition entry. |
| M7.A4 | Extract renderer runtime into core services (`PreviewProvider`, `AssetManager`, `AudioFeatureBus`, `TransportClock`, `SceneGraphComposer`) | M7.A3 | completed | Completed through `M7.A4.1` to `M7.A4.5`: provider/runtime ownership is split into dedicated services, `previewGpuRuntimeCoordinator.ts` is the frozen GPU runtime entry seam, and compatibility-only GPU adapters are removed. |
| M7.A5 | Move Spectrum, Background, Logo, and Particles into separate feature-domain folders with isolated editor, schema, runtime, and renderer adapters | M7.A2, M7.A4 | completed | Completed through `M7.A5.1` to `M7.A5.5`: Spectrum, Background, Logo, and Particles now route through domain-owned editor/runtime contracts, compatibility wrappers are reduced to explicit legacy shells only, and boundary audits prove production callers no longer reach across domains outside approved seams. |
| M7.A6 | Add a registry-driven effect pack system for installable Spectrum styles, Particle effects, Background motion packs, and Logo behaviors | M7.A5 | completed | Shared effect-pack contracts, the Electron registry/install bridge, renderer catalog/query seams, four-domain workspace selectors, and template/runtime pack references are now implemented and documented. |
| M7.A7 | Build pack-safe versioning, validation, rollback, and disabled-pack recovery for marketplace delivery | M7.A6 | completed | Compatibility checks, fail-closed validation, transactional install rollback, disabled/missing/incompatible status handling, and recovery actions are now implemented across the registry and workspace flows. |
| M7.A8 | Add focused tests for domain boundaries, manifest validation, registry loading, and per-domain patch isolation | M7.A2, M7.A5, M7.A7 | completed | Shared manifest/runtime helpers, registry install/recovery behavior, boundary audits, and per-domain patch-isolation coverage are now in place and verified alongside the full Vitest sweep. |
| M7.A9 | Harden the Video workspace into an enterprise-grade operator surface by thinning orchestration, moving save assembly into Video-owned modules, and exposing diagnostics/recovery controls | M7.A5, M7.A8 | completed | `/app/video` now saves through a Video-owned workspace module, `useVideoWorkspaceCoordinator.ts` composes dedicated save and diagnostics hooks, the left rail exposes a diagnostics/recovery panel with real actions, and focused plus full-suite verification are green. |
| M7.A10 | Harden the renderer preview lifecycle with explicit capability/runtime states, recovery-aware diagnostics, and focused lifecycle tests | M7.A9 | completed | `/app/video` now exposes explicit preview lifecycle truth through the provider, stage, and diagnostics panel, handles WebGPU device-loss/remount recovery, and closes with focused lifecycle coverage plus a green full Vitest sweep after stabilizing `VideoWorkspacePage.test.tsx`. |
| M7.A11 | Harden unsupported and degraded preview UX so `/app/video` explains fallback mode, missing capability, and recovery actions without reading like a debug console | M7.A10 | completed | The Video stage and diagnostics card now turn lifecycle truth into operator guidance, distinguish hard preview loss from fallback mode, and keep recovery steps explicit while preserving one lifecycle source of truth. |
| M7.A12 | Refine the Video page layout so preview stays visually primary while diagnostics and empty inspector states feel production-ready | M7.A11 | completed | `/app/video` now pushes diagnostics behind a compact support disclosure, gives the center stage slightly more width, and renders a purposeful right-rail empty state when no text layer is selected. |
| M7.A13 | Remove duplicated status and low-value context from the Video page so the workstation reads as professional instead of diagnostic-heavy | M7.A12 | completed | `/app/video` now removes repeated status chips from the right rail and preview overlay, trims low-value context copy, and keeps diagnostics focused on recovery and save state instead of dumping every workspace detail. |
| M7.A14 | Reduce label-heavy Video controls so the inspectors read cleaner without losing editing clarity | M7.A13 | completed | `/app/video` now uses more compact shared field primitives, removes one useless disabled background control, and shortens obvious toggle/control labels across the main Video inspectors. |
| M7.A15 | Remove leftover context blocks and instruction-heavy copy from the Video page, and justify the Video tabs for cleaner alignment | M7.A14 | completed | `/app/video` now removes the left `Pipeline Context` card, simplifies the Spectrum audio section and stage asset card headings, and justifies the Video-page tabs evenly across the rails. |
| M7.A16 | Fix Spectrum-tab width pressure so the left rail fits without horizontal scrolling and keep template delete semantics honest | M7.A15 | completed | `/app/video` now keeps Spectrum cards shrink-safe inside the left rail, stacks dense layer controls before they overflow, and documents honestly that the removed template-level `Delete` control never mapped to a real destructive template flow. |
| M7.A17 | Restore the Video template delete action as a real end-to-end flow instead of a dead placeholder | M7.A16 | completed | `/app/video` now exposes a confirmed template delete action backed by a real Electron bridge mutation, updates template selection after removal, and keeps focused Video tests green. |
| M7.A18 | Audit the Video preview/runtime against GPU-first, audio-reactive, and preview/export-parity requirements, then document the implementation program in detail | M7.A17 | completed | `docs/video-preview-gpu-reactivity-parity-plan.md` now captures the present/partial/missing matrix, Python ModernGL comparison, GPU-first constraints, non-UI rules, double-shot implementation plan, and verification requirements for the next renderer phases. |
| M7.A19 | Replace live-only preview heuristics with an analyzed audio feature timeline and GPU-fed reactivity pipeline | M7.A18 | completed | `/app/video` now has a shared analyzed audio timeline contract, deterministic sampled preview reactivity, analyzed spectrum-frame playback, a per-frame GPU audio-signal handoff that uploads structured analyzed bands to the renderer, named synthetic material fixtures, Python-style raw-drive and smoothed-trace parity for background/logo/particles, and page-level verification that Spectrum/Background/Logo/Particles edits reach preview immediately without save-gating. Remaining deeper render-parity and GPU-simulation work now belongs to `M7.A20` and `M7.A21`. |
| M7.A20 | Move remaining frame-critical simulation and post-fx work toward GPU ownership and add adaptive performance tiers | M7.A19 | completed | Preview runtime now owns a shared capability/quality policy seam, an explicit post-fx plan seam, a GPU-evaluated particle motion path, a real temporal-history motion-blur pass, a telemetry-driven adaptive fallback loop, named internal stress-scene metadata, explicit 60/120 frame-target verification, page-level responsiveness coverage, focused GPU/performance lock tests, shared preview-audio-signal reuse for spectrum preparation, and a shader-owned spectrum gradient-atlas path; the main remaining architectural gap is now preview/export convergence under `M7.A21`, not raw preview smoothness or GPU ownership gaps inside the live preview runtime. |
| M7.A21 | Converge preview and export onto one renderer contract so preview is a trustworthy 100% final representation | M7.A19, M7.A20 | pending | Preview and export share the same scene/audio/render contracts, parity drift is measured with fixtures, and `/app/video` no longer depends on two visually divergent rendering stacks for preview versus final output. |

Current `M7.A4` / `M7.A5` phase note:
- Phase 50 split the internal GPU runtime under the preview path into `previewGpuDomainPreparation.ts` for spectrum/particle/effects preparation and `previewGpuSubmissionOrchestrator.ts` for execution-plan assembly, submission, and runtime-result packaging. This keeps the coordinator thinner and moves the runtime closer to domain-owned seams.
- Phase 51 moved spectrum and particle GPU preparation contracts into `features/video/domains/spectrum/spectrumGpuContract.ts` and `features/video/domains/particles/particleGpuContract.ts`, so preview orchestration now passes domain-owned `spectrum` and `particles` request packages instead of one flat preview-local prep argument bag.
- Phase 52 moved the actual spectrum and particle GPU prep adapters into `features/video/domains/spectrum/spectrumGpuRuntime.ts` and `features/video/domains/particles/particleGpuRuntime.ts`, so preview orchestration now depends on domain-owned runtime entrypoints while the old preview runtime files stay as thin compatibility wrappers.
- Phase 53 split atmosphere and post-FX shaping so `features/video/domains/atmosphere/atmosphereGpuRuntime.ts` now owns atmosphere-domain GPU shaping entrypoint logic, `previewGpuPostFx.ts` now owns shared preview bloom/post-FX composition, and `previewGpuEffects.ts` remains only as a thin compatibility wrapper.
- Phase 54 split the remaining low-level GPU effect math so `features/video/domains/atmosphere/atmosphereGpuMath.ts` now owns atmosphere math, `previewGpuBloomTuning.ts` now owns bloom/post-FX tuning math, and `sceneStateAdapter.ts` is now only a compatibility export surface.
- Phase 55 collapsed the dead preview-side compatibility wrappers by removing `previewSpectrumGpuRuntime.ts`, `previewParticleGpuRuntime.ts`, `previewGpuEffects.ts`, and `sceneStateAdapter.ts` plus their wrapper-only tests, so the live GPU path now depends directly on the domain/runtime helpers that already owned the real behavior.

### 3.10.1 Narrowed `M7.A2` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A2.1 | Keep domain settings modules as the source of truth and treat `settingsTemplateDraft.ts` only as an aggregate compatibility shim | M7.A2 | completed | Spectrum, Background, Logo, Particles, Text, and Atmosphere each own their settings builders and template patch helpers under `features/video/domains/*` |
| M7.A2.2 | Remove aggregate `TemplateSettingsDraft` usage from preview GPU/runtime contracts | M7.A2.1 | completed | Preview GPU/runtime modules consume domain-owned or preview-owned narrowed contracts instead of importing the aggregate draft type directly; remaining aggregate draft usage is limited to provider/scene assembly pending `M7.A2.3` and `M7.A2.4` |
| M7.A2.3 | Remove aggregate `TemplateSettingsDraft` usage from scene composition and binding helpers | M7.A2.1 | completed | `sceneGraphComposer.ts`, `attachmentService.ts`, `logoSpectrumBindings.ts`, `previewScene.ts`, `usePreviewSceneState.ts`, and related preview scene helpers no longer depend on the aggregate draft type |
| M7.A2.4 | Restrict `settingsTemplateDraft.ts` to workspace hydration/save compatibility only | M7.A2.2, M7.A2.3 | completed | Only workspace entry/save flows import `settingsTemplateDraft.ts`; preview runtime, scene composition, renderer-preview files, and domain runtime files do not |
| M7.A2.5 | Add draft-boundary verification and mark `M7.A2` complete | M7.A2.4 | completed | `videoDraftBoundary.test.ts` and import-audit checks prove the aggregate draft no longer acts as the live runtime contract outside workspace compatibility flows |

### 3.10.2 Narrowed `M7.A3` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A3.1 | Extract shared scene composition services (`sceneGraphComposer.ts`, `attachmentService.ts`) | M7.A3 | completed | Shared scene composition no longer lives inline in page or renderer shells |
| M7.A3.2 | Route intentional logo-to-spectrum coupling through explicit binding helpers only | M7.A3.1 | completed | `logoSpectrumBindings.ts` and `useLogoSpectrumBindings.ts` own the intentional cross-domain edits instead of ad hoc page mutations |
| M7.A3.3 | Move preview/runtime scene assembly onto immutable scene-node inputs | M7.A3.1 | completed | `VideoPreviewScene` now carries immutable runtime node payloads so preview/runtime helpers consume scene-owned inputs instead of rebuilding slice composition from raw draft state |
| M7.A3.4 | Remove remaining direct cross-domain reads outside scene services and binding hooks | M7.A3.3 | completed | Scene composition routes through `sceneGraphComposer.ts`, `attachmentService.ts`, `previewScene.ts`, and explicit binding helpers; domain source files do not import sibling domain internals |
| M7.A3.5 | Add scene-boundary verification and mark `M7.A3` complete | M7.A3.4 | completed | `sceneBoundary.test.ts` and focused runtime tests prove preview consumers do not read `scene.draft` directly and domain files do not cross-import sibling domains |

### 3.10.3 Narrowed `M7.A4` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A4.1 | Extract provider orchestration into `usePreviewProviderState.ts` plus narrowed contracts | M7.A4 | completed | `PreviewProvider.tsx` acts as a thin composition shell over provider state and render contracts |
| M7.A4.2 | Extract runtime/frame execution into dedicated hooks and helpers | M7.A4.1 | completed | RAF scheduling, per-frame orchestration, telemetry/reporting, and DOM presentation are owned by dedicated runtime helpers rather than inline provider/component logic |
| M7.A4.3 | Extract GPU orchestration into preparation, submission, and coordinator seams | M7.A4.2 | completed | The GPU path routes through `previewGpuDomainPreparation.ts`, `previewGpuSubmissionOrchestrator.ts`, and `previewGpuRuntimeCoordinator.ts` with direct domain runtime entrypoints |
| M7.A4.4 | Freeze the final public GPU runtime entry seam | M7.A4.3 | completed | Callers now use `previewGpuRuntimeCoordinator.ts` directly; `previewGpuFrameRenderer.ts` has been removed |
| M7.A4.5 | Remove or explicitly document all remaining compatibility-only runtime adapters and mark `M7.A4` complete | M7.A4.4 | completed | Compatibility-only GPU adapters are deleted, `previewRuntimeBoundary.test.ts` enforces the seam removal, and the surviving runtime shells are intentional composition seams |

### 3.10.4 Narrowed `M7.A5` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A5.1 | Finish Spectrum domain isolation across editor state, schema, runtime, and renderer adapters | M7.A2, M7.A4 | completed | Completed by moving spectrum layer contracts, scene-layer shaping, preview runtime helpers, and WebGPU instance assembly behind spectrum-domain modules; workspace Spectrum editor/preset flows now import those modules directly, and `spectrumDomainBoundary.test.ts` blocks regressions onto settings-owned helpers or the legacy preview adapter path |
| M7.A5.2 | Finish Background domain isolation across editor state, schema, runtime, and renderer adapters | M7.A2, M7.A4 | completed | Background editor/runtime flows now use `backgroundSettings.ts` and `backgroundPreviewRuntime.ts`, and production callers no longer depend on settings-owned options or `sceneGraphComposer.ts` for active background behavior |
| M7.A5.3 | Finish Logo domain isolation across editor state, schema, runtime, and explicit binding seams | M7.A2, M7.A3, M7.A4 | completed | Logo editor/runtime flows now use `logoSettings.ts` and `logoPreviewRuntime.ts`, while the approved `logoSpectrumBindings.ts` seam remains the only intentional cross-domain binding path |
| M7.A5.4 | Finish Particles domain isolation across editor state, schema, runtime, and renderer adapters | M7.A2, M7.A4 | completed | Particle editor/runtime flows now use `particleSettings.ts` and `particleSimulation.ts`, and the preview particle adapter is reduced to a compatibility re-export with no production callers |
| M7.A5.5 | Add cross-domain boundary verification and mark `M7.A5` complete | M7.A5.1, M7.A5.2, M7.A5.3, M7.A5.4 | completed | `spectrumDomainBoundary.test.ts` plus `videoDomainIsolationBoundary.test.ts` prove production callers stay off legacy adapter/composer paths and that domain editors no longer reach through settings-owned helpers |

### 3.10.5 Narrowed `M7.A6` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A6.1 | Define the shared effect-pack manifest contract and per-domain pack payload schemas | M7.A6 | completed | `src/shared/effectPacks/effectPackContracts.ts` now owns the shared manifest plus Spectrum, Background, Logo, and Particles payload contracts and template reference types. |
| M7.A6.2 | Reuse the desktop sample-pack install path for effect-pack download, extract, and local storage layout | M7.A6.1 | completed | `src/main/effectPackRegistry.ts` and the Electron IPC bridge now use one canonical registry/storage model for installed packs, extracted assets, and staged updates. |
| M7.A6.3 | Build a renderer-facing effect-pack registry loader and catalog query seam | M7.A6.1, M7.A6.2 | completed | The preload bridge, desktop API types, and `useEffectPackCatalogQuery.ts` now expose installed pack metadata and status without leaking file-system details into the workspace UI. |
| M7.A6.4 | Add workspace catalog selection and preview application flows for Spectrum, Background, Logo, and Particles | M7.A6.3 | completed | All four inspectors now expose install/apply/clear/enable/activate/remove flows through `EffectPackSelectorCard.tsx` and `useEffectPackManager.ts`, with per-domain preview patching only. |
| M7.A6.5 | Persist pack references in template/workspace state and resolve them through domain-owned runtime adapters | M7.A6.4 | completed | `VideoTemplateDraft`, template patch helpers, and workspace draft slices now persist pack references by domain and resolve them through the existing domain-owned runtime boundaries. |
| M7.A6.6 | Document the effect-pack install/runtime contract and mark `M7.A6` complete | M7.A6.1, M7.A6.2, M7.A6.3, M7.A6.4, M7.A6.5 | completed | Tasks, technical docs, design notes, and the development log now describe the implemented manifest, storage, registry, workspace, and runtime seams. |

### 3.10.6 Narrowed `M7.A7` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A7.1 | Define app-version, domain-version, and manifest compatibility policy for installed packs | M7.A6 | completed | Shared effect-pack version helpers plus `EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS` now define the supported app/domain compatibility policy. |
| M7.A7.2 | Add preinstall validation and fail-closed rejection for malformed or incompatible packs | M7.A7.1 | completed | The registry now validates manifests, rejects unsupported domain contracts before activation, and returns structured failure results instead of partially installing bad packs. |
| M7.A7.3 | Make pack install/update transactional with staging, activation, and rollback | M7.A7.2 | completed | Install/update flows now stage files, switch live versions only after validation, and restore the prior version automatically on activation failure. |
| M7.A7.4 | Add disabled-pack and missing-pack resolution for saved templates | M7.A7.1, M7.A7.2 | completed | Shared runtime helpers resolve missing, disabled, incompatible, and broken selections into explicit status objects so saved templates stay loadable without corrupting unrelated draft state. |
| M7.A7.5 | Add pack health/status surfaces for install failures, quarantined packs, and manual recovery actions | M7.A7.3, M7.A7.4 | completed | The workspace selectors now surface honest pack status and expose install, reload, enable, activate, remove, clear, and retry-adjacent recovery actions through one shared UI seam. |
| M7.A7.6 | Freeze the pack safety model and mark `M7.A7` complete | M7.A7.1, M7.A7.2, M7.A7.3, M7.A7.4, M7.A7.5 | completed | The compatibility, rollback, and recovery behavior is now implemented, documented, and covered by the focused effect-pack verification suite. |

### 3.10.7 Narrowed `M7.A8` Closure Checklist
| ID | Task | Depends On | Status | Done When |
|----|------|------------|--------|-----------|
| M7.A8.1 | Add automated manifest and schema validation tests for all effect-pack domains | M7.A6.1, M7.A7.1 | completed | `effectPackContracts.test.ts` now covers shared manifest parsing across Spectrum, Background, Logo, and Particles payloads. |
| M7.A8.2 | Add registry/installer integration tests for install, update, remove, and discovery flows | M7.A6.2, M7.A6.3, M7.A7.3 | completed | `effectPackRegistry.test.ts` now covers discovery, install, remove, unsupported contract rejection, and rollback-safe activation failure behavior. |
| M7.A8.3 | Add recovery tests for incompatible, missing, disabled, and rolled-back packs | M7.A7.2, M7.A7.4, M7.A7.5 | completed | Shared runtime helper tests and registry tests now lock missing/broken/incompatible selection handling plus rollback recovery behavior. |
| M7.A8.4 | Extend domain-boundary audits so pack loaders and pack-aware editors still respect domain isolation | M7.A5, M7.A6.4 | completed | `effectPackWorkspaceBoundary.test.ts` keeps the new workspace seams off direct video-domain internals, preserving the domain-isolation contract. |
| M7.A8.5 | Add per-domain patch-isolation tests for pack preview/apply flows | M7.A6.4, M7.A6.5 | completed | `effectPackDraftState.test.ts` proves pack preview/apply flows only change the intended domain draft slices and explicitly allowed bindings. |
| M7.A8.6 | Add marketplace-ready verification notes and mark `M7.A8` complete | M7.A8.1, M7.A8.2, M7.A8.3, M7.A8.4, M7.A8.5 | completed | Focused effect-pack suites pass, `npm run check` is clean, and the full Vitest sweep passed after reconciling unrelated stale workspace/onboarding assertions to the live UI contract. |

### 3.10.8 Narrowed `M7.A9` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A9.1 | Move final Video template-save assembly out of `settingsTemplateDraft.ts` and into a Video-owned workspace module | M7.A2.4, M7.A5 | completed | Final save assembly now lives in `features/video/workspace/videoWorkspaceTemplateSave.ts`, while `settingsTemplateDraft.ts` remains a compatibility shim and re-export surface. |
| M7.A9.2 | Split `useVideoWorkspaceCoordinator.ts` into thinner orchestration seams for save/recovery/diagnostics without widening the page contract | M7.A9.1 | completed | The coordinator now composes `useVideoWorkspaceTemplatePersistence.ts` and `useVideoWorkspaceDiagnostics.ts` instead of keeping save assembly and recovery logic inline. |
| M7.A9.3 | Add a Video diagnostics panel that surfaces draft, preview, asset, export, and pipeline truth in one operator-facing card | M7.A9.2 | completed | `VideoWorkspaceDiagnosticsPanel.tsx` now exposes per-domain dirty state, preview/save/export/pipeline status, and key asset/run-path context directly in the left rail. |
| M7.A9.4 | Add Video-only recovery controls for preview remount, workspace refresh, local-draft reset, and diagnostics export | M7.A9.3 | completed | The diagnostics panel now provides real `Remount Preview`, `Refresh Workspace`, `Reset Local Draft`, and `Copy Diagnostics` actions scoped to `/app/video`. |
| M7.A9.5 | Add focused verification for Video diagnostics/recovery flows and mark `M7.A9` complete | M7.A9.1, M7.A9.2, M7.A9.3, M7.A9.4 | completed | Added focused Vitest coverage for save assembly, template persistence, diagnostics, and draft reset, then passed `npm run check` and the full Vitest sweep. |

### 3.10.9 Narrowed `M7.A10` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A10.1 | Define a shared preview lifecycle contract for capability, runtime status, fallback, and recovery state | M7.A9 | completed | `previewLifecycleState.ts` plus the preview provider contract now expose explicit lifecycle truth instead of reducing preview health to `playbackReady`. |
| M7.A10.2 | Extend the WebGPU surface lifecycle to report recovery-aware runtime states, including device-lost handling | M7.A10.1 | completed | `usePreviewSurfaceLifecycle.ts` and `webgpuSpectrumRenderer.ts` now distinguish unsupported, initializing, running, recovering, device-lost, and error states without introducing a second preview path. |
| M7.A10.3 | Surface preview lifecycle state inside the Video stage and diagnostics panel | M7.A10.1, M7.A10.2 | completed | `/app/video` now shows aligned lifecycle truth in `RendererVideoPreviewSurface.tsx`, `VideoWorkspaceStage.tsx`, and `VideoWorkspaceDiagnosticsPanel.tsx`. |
| M7.A10.4 | Add focused lifecycle and diagnostics tests for capability, remount/recovery, and state propagation | M7.A10.2, M7.A10.3 | completed | Added lifecycle-focused coverage for provider, surface, diagnostics, and page seams; `VideoWorkspacePage.test.tsx` now uses a stable desktop API mock and a stubbed renderer preview to keep the route contract test deterministic. |
| M7.A10.5 | Run verification and mark `M7.A10` complete | M7.A10.1, M7.A10.2, M7.A10.3, M7.A10.4 | completed | `npm run check`, targeted `VideoWorkspacePage.test.tsx`, and the full Vitest sweep now pass cleanly. |

### 3.10.10 Narrowed `M7.A11` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A11.1 | Define operator-facing degraded-preview guidance for unsupported, recovering, device-lost, error, and fallback-active states | M7.A10 | completed | `useVideoWorkspaceDiagnostics.ts` now derives one operator guidance model from lifecycle state plus current asset/run-path context. |
| M7.A11.2 | Surface the degraded-preview guidance directly in the stage so fallback/unsupported states are more obvious than status pills alone | M7.A11.1 | completed | `VideoWorkspaceStage.tsx` now shows a visible Preview Guidance callout when the live compositor output is degraded or unavailable. |
| M7.A11.3 | Tighten the diagnostics card so it summarizes lifecycle guidance instead of reading like raw debug output | M7.A11.1 | completed | `VideoWorkspaceDiagnosticsPanel.tsx` now renders guidance-first lifecycle summaries instead of only one generic status paragraph. |
| M7.A11.4 | Add focused tests for the new fallback guidance and mark `M7.A11` complete | M7.A11.2, M7.A11.3 | completed | Added unsupported/fallback guidance coverage in `useVideoWorkspaceDiagnostics.test.tsx`, then passed `npm run check`, targeted Video tests, and the full Vitest sweep. |

### 3.10.11 Narrowed `M7.A12` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A12.1 | Reduce left-rail chrome so template and edit controls stay primary over diagnostics | M7.A11 | completed | `VideoWorkspaceLeftRail.tsx` now moves diagnostics behind a compact `Diagnostics & Recovery` disclosure below the active editor content. |
| M7.A12.2 | Improve the right inspector empty state so no-selection mode feels intentional instead of blank | M7.A11 | completed | `TextPanels.tsx` now renders a stronger no-selection card that explains how to create/select text layers and what the inspector currently owns. |
| M7.A12.3 | Rebalance the three-column shell so the center preview gets slightly more space on large screens | M7.A12.1 | completed | `VideoWorkspaceShell.tsx` now narrows the side rails and gives more width to the center preview column on `xl` and `2xl` screens. |
| M7.A12.4 | Add focused verification for the refined Video shell and mark `M7.A12` complete | M7.A12.1, M7.A12.2, M7.A12.3 | completed | `VideoWorkspacePage.test.tsx`, `npm run check`, and the full Vitest sweep all passed after locking the new shell presentation contract. |

### 3.10.12 Narrowed `M7.A13` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A13.1 | Remove repeated status chips and duplicate labels across the stage and right inspector | M7.A12 | completed | `VideoWorkspaceRightRail.tsx` now drops redundant inspector/export/text-save chips, while `VideoWorkspaceStage.tsx` removes repeated status labels that were already visible elsewhere. |
| M7.A13.2 | Trim low-value context copy and surplus asset/detail text from the stage and diagnostics surfaces | M7.A12 | completed | Left/stage/diagnostics copy is now shorter, the disabled Delete action is gone, and diagnostics summary fields are reduced to the context that actually helps editing or recovery. |
| M7.A13.3 | Simplify preview overlay messaging so the compositor itself is less noisy during normal editing | M7.A13.1, M7.A13.2 | completed | `RendererVideoPreviewSurface.tsx` now stays quiet in healthy mode and reserves heavier overlay messaging for warnings, fallback, or decode errors. |
| M7.A13.4 | Add focused verification for the de-noised Video shell and mark `M7.A13` complete | M7.A13.1, M7.A13.2, M7.A13.3 | completed | `npm run check`, targeted Video page/preview tests, and the full Vitest sweep all passed after the shell cleanup. |

### 3.10.13 Narrowed `M7.A14` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A14.1 | Compact the shared Video field components so selects, colors, and numeric inputs use less label chrome | M7.A13 | completed | `inspectorFields.tsx` and the text inspector `NumberField` now use compact stacked labels instead of a dedicated label column for every control. |
| M7.A14.2 | Remove useless or disabled labeled controls from the Video inspectors | M7.A13 | completed | Removed the disabled `Edit background in preview` control from `BackgroundInspector.tsx`. |
| M7.A14.3 | Shorten obvious toggle and control labels where the surrounding section already provides context | M7.A14.1 | completed | Spectrum, background, logo, and particles controls now use shorter labels like `Spectrum`, `Logo`, `Spin`, `Vignette`, and `Smoke`. |
| M7.A14.4 | Add focused verification for the cleaner control surfaces and mark `M7.A14` complete | M7.A14.1, M7.A14.2, M7.A14.3 | completed | `npm run check`, targeted `VideoWorkspacePage.test.tsx`, and the full Vitest sweep all passed after the control cleanup. |

### 3.10.14 Narrowed `M7.A15` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A15.1 | Remove duplicated context blocks from the left rail and center stage | M7.A14 | completed | Deleted the left `Pipeline Context` card from `VideoWorkspaceLeftRail.tsx` and flattened the center asset card in `VideoWorkspaceStage.tsx` so it no longer announces itself as `Stage Context`. |
| M7.A15.2 | Strip instruction-heavy copy from the Spectrum audio section and similar Video surfaces | M7.A14 | completed | `SpectrumInspector.tsx` now uses a simple `Audio` card with no field-level helper descriptions. |
| M7.A15.3 | Make Video-page tabs justify evenly across their available width | M7.A14 | completed | `CompactTabs` now supports a justified mode and the Video page uses it for the left rail, right rail, and text-panel mode tabs only. |
| M7.A15.4 | Run focused verification and mark `M7.A15` complete | M7.A15.1, M7.A15.2, M7.A15.3 | completed | `npm run check`, targeted `VideoWorkspacePage.test.tsx`, and the full Vitest sweep all passed after the cleanup. |

### 3.10.15 Narrowed `M7.A16` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A16.1 | Confirm the removed template-level `Delete` button did not map to a real destructive template flow | M7.A15 | completed | `VideoWorkspaceLeftRail.tsx` only kept `Save` plus template selection; the earlier removed `Delete` control was a UI placeholder, not a wired delete-template command. |
| M7.A16.2 | Make Spectrum-layer cards shrink correctly within the left rail using `min-w-0` and full-width layout guards | M7.A15 | completed | `SectionCard` and nested Spectrum layer cards now use shrink-safe `min-w-0` / full-width guards so card chrome fits the rail. |
| M7.A16.3 | Let dense Spectrum action/toggle rows stack sooner instead of forcing three fixed columns in a narrow rail | M7.A16.2 | completed | Layer action rows, geometry toggles, and color rows now stack or shrink instead of forcing horizontal squeeze. |
| M7.A16.4 | Run focused verification and mark `M7.A16` complete | M7.A16.1, M7.A16.2, M7.A16.3 | completed | `npm run check` and `npx vitest run src/renderer/src/features/video/VideoWorkspacePage.test.tsx --reporter=verbose` passed after the Spectrum layout fix. |

### 3.10.16 Narrowed `M7.A19` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A19.1 | Define a shared analyzed-audio timeline contract that preview and future export can both consume | M7.A18 | completed | `audioReactiveTimeline.ts` now defines one owned timeline/sample contract for deterministic reactive feature reads instead of keeping preview-only ad hoc shapes inline. |
| M7.A19.2 | Add a reusable audio analysis pipeline that computes bass, mid, treble, broadband energy, onset, beat, transient strength, and related envelopes from the selected preview track | M7.A19.1 | completed | The new analyzed timeline builder now derives deterministic bass/mid/treble/energy/onset/transient/beat/kick/drop features from decoded audio during preview bootstrap. |
| M7.A19.3 | Add true peak-hold support to the analyzed feature model and runtime state | M7.A19.1, M7.A19.2 | in_progress | Aggregate peak-hold is now carried in the analyzed timeline, live spectrum envelopes track per-band peak-hold state, and the shared per-frame GPU signal contract now uploads peak-hold bands to the renderer, while broader shader-side/runtime ownership is still open. |
| M7.A19.4 | Standardize attack, release, smoothing, and domain-reactivity multipliers so signal shaping happens in one owned pipeline instead of being scattered across preview helpers | M7.A19.2 | in_progress | The analyzed timeline now owns its core attack/release and beat heuristics, preview/GPU handoff now reuses one shared per-frame audio signal instead of rebuilding the same sampled spectrum per layer, and background/logo/particle domain drives now route through Python-style bass-plus-kick raw shaping before local smoothing; full consolidation of all remaining preview-side smoothing and domain multipliers is still pending. |
| M7.A19.5 | Add interpolation rules for sampling analyzed features between audio frames so preview reads are deterministic and stable at render time | M7.A19.1, M7.A19.2 | completed | `samplePreviewAudioReactiveFeatureTimeline(...)` now interpolates deterministic timeline features between analysis frames instead of snapping to coarse frame boundaries. |
| M7.A19.6 | Preserve and centralize the existing logarithmic frequency weighting and FFT-bin mapping under the new owned audio-reactivity seam | M7.A19.1, M7.A19.2 | in_progress | The analyzed timeline now derives deterministic log-band spectrum features under the owned audio-reactivity seam, and the new per-frame GPU signal contract keeps those analyzed bands available for renderer upload without recomputing them per layer, while the final runtime closure still remains open. |
| M7.A19.7 | Upload analyzed feature data through a GPU-fed contract so frame-critical preview reads stop depending on repeated CPU-only shaping loops | M7.A19.3, M7.A19.4, M7.A19.5, M7.A19.6 | in_progress | Preview now builds one shared per-frame audio signal payload, reuses it for spectrum-layer value preparation, uploads analyzed energy/transient/onset/peak-hold bands to the WebGPU renderer, and lets the compositor consume audio-driven bloom modulation directly; the remaining work is broader shader/runtime ownership rather than inventing the GPU-fed contract. |
| M7.A19.8 | Replace the current live-only preview reactivity path with the analyzed timeline while preserving immediate editor feedback and avoiding new operator UI chrome | M7.A19.4, M7.A19.5, M7.A19.7 | in_progress | Preview motion now prefers sampled analyzed energy/kick/drop, can build full analyzed spectrum frames from the decoded timeline, and reuses one shared audio signal across the spectrum GPU runtime instead of repeating per-layer spectrum rebuilding; the live FFT path remains only as the fallback until the rest of `M7.A19` lands. |
| M7.A19.9 | Add structured audio-reactivity fixtures for kick-heavy, sustained-bass, vocal-mid-heavy, and high-treble material | M7.A19.2 | completed | `audioReactiveTimeline.test.ts` now includes deterministic named fixtures for kick-heavy pulses, sustained bass beds, vocal-mid phrases, and high-treble percussion so the owned analysis path can be regression-tested against the exact categories called out in the renderer plan. |
| M7.A19.10 | Add deterministic tests for feature extraction, beat/onset timing, interpolation, peak-hold decay, and domain signal mapping | M7.A19.3, M7.A19.4, M7.A19.5, M7.A19.9 | in_progress | Focused timeline, analyzed-spectrum, preview-reactivity, shared GPU-audio-signal, Python-parity raw-drive, Python-parity smoothed-trace modeling, direct background/logo/particle trace comparison, and spectrum-GPU-runtime tests now cover deterministic feature sampling, interpolation, analyzed frame construction, peak-hold behavior, named material fixtures, GPU handoff packaging, and domain signal routing; remaining parity closure is now more about final responsiveness verification and completion judgment than missing trace coverage. |
| M7.A19.11 | Verify preview responsiveness while editing Spectrum, Background, Logo, and Particles with the new signal pipeline in place | M7.A19.8, M7.A19.10 | completed | `VideoWorkspacePage.test.tsx` now verifies that local edits in Spectrum, Background, Logo, and Particles update the preview-facing `templateDraft` immediately, without waiting for save or query refresh, which closes the user requirement that preview editing stays immediate with the new signal pipeline in place. |
| M7.A19.12 | Reconcile the new Electron signal pipeline against the Python ModernGL reference and mark `M7.A19` complete | M7.A19.8, M7.A19.9, M7.A19.10, M7.A19.11 | completed | The runtime now includes Python-style raw-drive and smoothed-trace modeling with direct trace comparisons for background/logo/particles, plus page-level responsiveness verification across the edited video domains; the remaining work is no longer `M7.A19` closure work and instead moves forward under the GPU-simulation and preview/export parity phases. |

### 3.10.17 Narrowed `M7.A20` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A20.1 | Add adapter capability profiling and one runtime-owned quality policy so performance decisions stop being scattered thresholds | M7.A19 | completed | `previewQualityPolicy.ts` now derives one preview capability profile from the WebGPU adapter/device, resolves explicit compatibility/balanced/performance tiers, and the preview runtime now consumes that shared policy for DPR, spectrum-bar density, particle-count capping, and telemetry tagging instead of leaving those limits scattered inline. |
| M7.A20.2 | Move remaining frame-critical spectrum shaping work off repeated CPU hot paths wherever the GPU can own it | M7.A19.7 | completed | `previewReactiveFrameState.ts` now reuses the already-built `PreviewGpuAudioSignalFrame` mirrored render values before falling back to per-layer spectrum rebuilding, and the spectrum GPU runtime now consumes that shared signal path so the live preview no longer repeats equivalent CPU resampling work before draw submission unless the shared signal is unavailable. |
| M7.A20.3 | Extract post-fx into an explicit runtime/domain seam that owns bloom, glow composition, motion blur, and future color shaping | M7.A19 | completed | `previewGpuPostFx.ts` now defines one owned post-fx plan contract with explicit bloom, composite, motion-blur, and color-grade sections, and `previewGpuDomainPreparation.ts` maps that plan into current renderer submission settings instead of leaving post-fx policy spread across unrelated helpers or renderer-side defaults. |
| M7.A20.4 | Replace CPU particle simulation with a GPU-owned simulation path suitable for materially higher counts and smoother preview behavior | M7.A19.7 | completed | Particle motion is no longer CPU-integrated every frame; `particleSimulation.ts` now emits bounded spawn descriptors plus shared reactive envelopes, `particleGpuRuntime.ts` builds one per-frame particle simulation payload, and `webgpuSpectrumRenderer.ts` evaluates particle travel, drift, swirl, fade, and expiry in the particle shader from those spawn descriptors. |
| M7.A20.5 | Move gradient treatment further into shader/runtime ownership so layer coloring is no longer partly limited by CPU-prepared visual shaping | M7.A20.2, M7.A20.3 | completed | `spectrumRendererAdapter.ts` now builds a per-layer gradient atlas plus `gradientU` / `gradientV` coordinates, spectrum preparation/submission contracts thread that atlas through the runtime, and `webgpuSpectrumRenderer.ts` now samples the gradient atlas in the fragment shader instead of relying on CPU-baked per-instance gradient RGB. |
| M7.A20.6 | Add a real motion-blur or history-based temporal pass under the owned post-fx runtime | M7.A20.3 | completed | The owned post-fx plan now maps motion-blur settings into the renderer, and `webgpuSpectrumRenderer.ts` now keeps ping-pong history textures so the post-fx composite pass can blend the current scene against prior resolved output using temporal-history blur instead of a fake spatial substitute. |
| M7.A20.7 | Connect frame telemetry to adaptive quality fallback so the preview preserves smoothness under load instead of degrading into jank | M7.A20.1, M7.A20.3, M7.A20.4, M7.A20.6 | completed | `previewAdaptiveQuality.ts` now owns the adaptive state machine and derived fallback policies, `usePreviewSurfaceLifecycle.ts` keeps base capability policy separate from telemetry-driven adaptive state, and runtime telemetry now feeds that callback through `usePreviewRuntime.ts` so particles, spectrum density, DPR, bloom quality, and motion-blur quality degrade and recover through one shared policy seam without adding UI clutter. |
| M7.A20.8 | Add internal performance scenes for maximum layers, heavy bloom, high particle count, and text-overlay pressure | M7.A20.1 | completed | `previewPerformanceScenes.ts` now classifies live preview scenes into named internal stress cases (`max-layers`, `heavy-bloom`, `high-particles`, `text-overlay-pressure`) from the real scene contract, `previewScene.ts` carries that internal performance node, and frame telemetry now tags reports with the active stress scene so `M7.A20.9` and `M7.A20.11` can measure repeatable heavy-scene behavior without adding operator-facing controls. |
| M7.A20.9 | Add performance verification for 60 FPS broad compatibility and 120 FPS high-tier targets where hardware allows | M7.A20.1, M7.A20.7, M7.A20.8 | completed | `previewPerformanceVerification.ts` now evaluates each telemetry report against the tier-owned target frame rate (`60` for compatibility/balanced tiers, `120` for performance tier), classifies runtime results as `meeting-target`, `near-target`, or `missing-target`, and `usePreviewSurfaceLifecycle.ts` stores that latest verification beside the adaptive quality state so stress-scene and fallback behavior can be judged against honest frame budgets without adding any new operator UI. |
| M7.A20.10 | Verify the GPU-first slice preserves immediate preview edits without requiring new inspector clutter or diagnostic-heavy UI | M7.A20.2, M7.A20.4, M7.A20.7, M7.A20.9 | completed | `VideoWorkspacePage.test.tsx` now extends the immediate-preview regression to cover Spectrum, Background, Logo, Particles, and Text draft edits without save-gating, and `RendererVideoPreviewSurface.test.tsx` proves the newer `performanceVerification` runtime state remains internal in healthy mode instead of adding extra overlay or inspector noise. |
| M7.A20.11 | Add focused GPU/performance tests for particles, motion blur, post-fx ownership, telemetry-driven fallback, and stress-scene behavior | M7.A20.3, M7.A20.4, M7.A20.6, M7.A20.7, M7.A20.8 | completed | Focused tests now lock particle-count capping in `particleGpuRuntime.test.ts`, reduced temporal-history motion-blur policy behavior in `previewGpuPostFx.test.ts`, escalation into the minimal adaptive fallback level in `previewAdaptiveQuality.test.ts`, effective quality-policy particle capping in `previewPerformanceScenes.test.ts`, and frame-target verification against base-policy targets even while live reports reflect adaptive fallback in `previewPerformanceVerification.test.ts`. |
| M7.A20.12 | Close the GPU-first, motion-blur, and adaptive-performance findings and mark `M7.A20` complete | M7.A20.5, M7.A20.9, M7.A20.10, M7.A20.11 | completed | The remaining honest runtime gaps for live preview have been reduced to preview/export convergence work under `M7.A21`: spectrum preparation now reuses the shared GPU-audio signal, gradient shading is shader-owned through a runtime atlas, focused contract tests are updated, and verification passed with targeted Vitest plus `npm run check`. |

### 3.10.18 Narrowed `M7.A21` Closure Checklist

| ID | Task | Depends On | Status | Notes |
|----|------|------------|--------|-------|
| M7.A21.1 | Define a shared render-graph contract that both preview and export execution modes can consume | M7.A19, M7.A20 | pending | Stop treating preview and export as two separate renderer products with only template-schema overlap. |
| M7.A21.2 | Define one shared audio-feature contract for preview and export so both paths render against the same reactive truth | M7.A19 | pending | This closes the current split between Electron live features and Python-side offline analysis. |
| M7.A21.3 | Unify scene-node preparation and GPU submission inputs so preview and export consume the same scene/runtime packages | M7.A21.1, M7.A21.2 | pending | Surface/output ownership may differ, but the visual contracts should not. |
| M7.A21.4 | Unify pass ordering, blend behavior, post-fx tuning, and color treatment between preview and export | M7.A21.1, M7.A20.3 | pending | Eliminate predictable parity drift caused by different pass graphs or tuning defaults. |
| M7.A21.5 | Decide and implement the final convergence seam for export so final output no longer depends on a visually divergent renderer stack | M7.A21.1, M7.A21.3, M7.A21.4 | pending | This is the architectural closure item: preview must become trustworthy as final output truth. |
| M7.A21.6 | Add parity fixtures that render the same template and timestamp through preview and export contracts for comparison | M7.A21.2, M7.A21.3, M7.A21.4 | pending | These fixtures are required to measure parity instead of assuming it. |
| M7.A21.7 | Add snapshot or diff-threshold verification for parity-sensitive cases including heavy bloom, multiple layers, high particle load, and text overlays | M7.A21.6 | pending | Focus on the exact scenes most likely to drift visually. |
| M7.A21.8 | Reconcile or retire any remaining honest mismatch reporting once preview and export truly share the same renderer truth | M7.A21.5, M7.A21.7 | pending | The UI should only report preview/export mismatch if a real mismatch can still happen. |
| M7.A21.9 | Add export correctness checks across multiple timestamps and output resolutions using the unified renderer contracts | M7.A21.5, M7.A21.6 | pending | This guards against parity holding at one frame only. |
| M7.A21.10 | Add shared-contract regression tests so later preview or export work cannot silently fork the rendering model again | M7.A21.1, M7.A21.2, M7.A21.3, M7.A21.4 | pending | Lock the new renderer truth at the contract level. |
| M7.A21.11 | Verify the final convergence slice preserves operator trust without adding unnecessary editor chrome or debug-heavy workflow steps | M7.A21.5, M7.A21.8, M7.A21.9, M7.A21.10 | pending | The user should gain trust in preview fidelity, not more UI complexity. |
| M7.A21.12 | Mark preview/export convergence complete once parity drift is measured, reduced, and documented as closed | M7.A21.6, M7.A21.7, M7.A21.9, M7.A21.10, M7.A21.11 | pending | Completion means preview is a trustworthy 100% final representation within the documented contract. |

## 4. Dependency Map
| Dependency | Affects | Why It Matters |
|------------|---------|----------------|
| Platform auth endpoints | M2, M3 | Core login, register, session restore |
| Profile endpoints | M3, M4, M5 | Onboarding and profile management depend on them |
| Stats/account endpoints | M4 | Dashboard and profile page need real data |
| Progress/job endpoints | M5 | Progress and workflow views depend on reliable status APIs |
| Generation endpoints | M5, M6, M7 | Music, image, and video actions rely on backend orchestration |
| Renderer preview engine | M7 | Required for Option B preview ownership inside the Electron renderer |
| Python visualizer CLI | M7.13, M7.15, M7.18, M7.20 | Still required temporarily for export, merge, and downstream automation even after preview ownership shifts |

## 5. Validation Checklist
- [ ] App boots successfully in development
- [ ] Secure token storage works
- [ ] Startup route never flashes the wrong page
- [ ] Login and register reach real backend endpoints
- [ ] On `401`, user is logged out and routed to auth
- [ ] Onboarding creates a first profile correctly
- [ ] Dashboard shows real stats and `0` for empty numerics
- [ ] Profile page shows account, plan, and credits correctly
- [ ] Music route respects profile allowance gating
- [ ] Music composer supports date-range planning with valid `from` / `to` input rules
- [ ] Music history shows real backend state for recent batches and generated songs
- [ ] Image route uses backend-driven generation only
- [ ] Video route controls update renderer preview correctly
- [ ] Video preview/export mismatch states are surfaced honestly
- [ ] Settings exclude deprecated local AI/provider management
- [ ] Logs route is usable during long sessions

## 6. Testing Checklist
- [ ] Unit tests for auth utilities and adapters
- [ ] Unit tests for form schemas
- [ ] Component tests for auth, onboarding, dashboard, and music profile editor
- [x] Component/integration tests for music composer date validation and history rendering
- [ ] Integration tests for startup routing and `401` behavior
- [x] Integration tests for onboarding completion
- [ ] Integration tests for progress polling and dashboard mapping
- [x] Integration tests for renderer preview lifecycle and fallback behavior
- [ ] Manual QA on common desktop resolutions

## 7. Documentation Checklist
- [ ] Keep `prd.md` updated when scope changes
- [ ] Keep `design.md` updated when UX decisions change
- [ ] Keep `technical.md` updated when architecture or contracts change
- [ ] Record implementation progress in this task file
- [ ] Add change logs after each substantial implementation phase

## 8. Recommended Build Order
1. Foundation
2. Startup
3. Login
4. Register
5. Session restore and route guard
6. Onboarding
7. Main shell
8. Dashboard
9. Profile
10. Settings
11. Logs
12. Progress
13. Workflow
14. Music
15. Image
16. Video with renderer preview
17. Packaging and QA
