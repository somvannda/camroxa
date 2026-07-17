## 1. Design Intent
CAMXORA Electron should feel like a professional desktop studio application rather than a generic web app placed inside a desktop shell.

- Visual direction: dark creative workstation, precise micro-spacing, dense information layout, premium gradient emphasis only on truly primary actions
- UX direction: minimize surprises, keep flows deterministic, surface backend state clearly, and preserve the current creator workflow order from the Python app
- Product priority: function-first polish; every control must have real behavior, real state feedback, and a clear visual hierarchy

## 2. Experience Principles
1. **Parity Before Reinvention**: replicate the current Python app flow first, then improve ergonomics without changing business rules unexpectedly.
2. **Desktop-Native Feel**: use compact layouts, keyboard-friendly controls, persistent side navigation, and fast route switching.
3. **Clear System Status**: always show loading, syncing, success, error, empty, and plan-gated states.
4. **No Fake Configuration**: only surface settings that are truly editable by the end user.
5. **Renderer-Owned Preview Strategy**: for Video, React owns the full workstation UI and a WebGPU-only preview engine mounted directly in the center pane; Python export remains temporary until parity is migrated, Canvas2D is no longer part of the intended live preview path, and the active implementation now composites background, smoke, vignette, logo, text, and spectrum into one GPU-owned preview surface instead of stacking DOM overlays around a GPU spectrum layer.

## 3. Information Architecture

### 3.1 Window Model
1. **Primary Window**
   - Electron-framed application window
   - Hosts all React routes
   - Owns auth, onboarding, and main app shell

2. **Renderer Preview Surface**
   - A renderer-hosted preview canvas lives directly inside the Video workspace center pane
   - Electron remains the sole owner of buttons/forms/controls and now also owns preview presentation through one WebGPU compositor surface
   - Python export remains available temporarily for final render/merge flows until the renderer pipeline is ready to replace it

### 3.2 Route Structure
| Route Group | Routes | Notes |
|-------------|--------|-------|
| Public | `/startup`, `/auth/login`, `/auth/register` | Session bootstrap and unauthenticated flows |
| First-run | `/onboarding/*` | Wizard shown only when profiles do not exist |
| Authenticated Shell | `/app/home`, `/app/profile`, `/app/workflow`, `/app/progress`, `/app/music`, `/app/image`, `/app/video`, `/app/merger`, `/app/settings`, `/app/log` | Main desktop workspace |

## 4. Visual Design System

### 4.1 Color Direction
- App background: deep navy/ink surfaces inspired by the current desktop dark theme
- Primary action: controlled purple gradient for main CTA only
- Secondary action: dark neutral surface with clear hover border
- Destructive action: dark red/danger styling
- Text: high-contrast white/near-white with disciplined secondary and muted tiers
- Status colors:
  - success: green
  - warning: orange
  - error: red
  - info: blue/cyan

### 4.2 Typography
- Use a readable modern sans for UI body text and forms
- Keep heading scale tight and desktop-appropriate rather than oversized marketing typography
- Form labels must remain compact and semantically grouped with inputs
- Numeric/stat values must use a clear, aligned metric style for dashboard and profile areas

### 4.3 Iconography
- Use Lucide icons everywhere
- Maintain semantic icon mapping from the current app where useful:
  - `user-round` for identity
  - `image` for images and cover assets
  - `video` for video controls
  - `save` for save
  - `trash-2` for delete
  - `settings` for app settings
- Do not mix icon families

### 4.4 Surfaces
- Base shell surface: dark matte background
- Cards: slightly elevated darker panels with subtle border separation
- Tables and editors: compact panel sections with strong row rhythm
- Dialogs/drawers: elevated, focused, slightly brighter than page surfaces

## 5. Core Interaction Patterns

### 5.1 Form Behavior
- Use `react-hook-form` + schema validation
- Validate inline where practical
- Disable destructive or submit actions during in-flight operations
- Show server errors in context, not as vague global failures only
- Preserve unsaved changes awareness on complex workspaces later in the roadmap

### 5.2 Loading States
- Splash: staged progress with status copy
- Auth and onboarding: inline button loading + section-level blocking
- Dashboard: skeleton cards and chart placeholders
- Tables: skeleton rows first, empty state second
- Generator pages: operation banners and progress surfaces

### 5.3 Error States
- Inline validation errors for form issues
- Banner or section alert for backend/API failures
- Retry actions where re-fetch is safe
- Authentication expiration always routes back to auth

### 5.4 Empty States
- Dashboard: show `0` instead of dashes for numeric empties
- Progress: empty table state with explanation and primary next action
- Music profiles: guided empty state prompting first profile creation when allowed
- Media galleries: explain why nothing is present and what action produces results

## 6. Page-by-Page UX Specification

### 6.1 Startup Page
**Purpose**
- Hide bootstrap complexity while tokens, session, and profile state are evaluated

**Layout**
- Centered brand mark
- Progress bar or segmented loader
- One current status line
- Subtle footer version/build text

**Behavior**
- Never linger unnecessarily after bootstrap completion
- Never flash login before auto-session finishes
- If bootstrap fails hard, route to auth with a recoverable message

### 6.2 Login Page
**Purpose**
- Fast return for existing users

**Layout**
- Split-panel or centered auth card depending on implementation preference
- Brand side with short value proposition
- Form side with email, password, show/hide password, remember session if supported

**Behavior**
- Enter submits the form
- Show loading inside CTA
- Preserve backend error messaging where safe
- Provide direct switch to register

### 6.3 Register Page
**Purpose**
- Create a new account and immediately guide the user into onboarding

**Layout**
- Same shell as login for continuity
- Fields: name, email, password, confirm password if required by backend policy
- Password guidance and validation hints

**Behavior**
- Clear duplicate-email handling
- Successful registration routes into onboarding or verification-required state

### 6.4 Onboarding
**Purpose**
- Create the user’s first usable profile with guided assistance

**Structure**
1. Welcome / explanation
2. Identity basics
3. Genre and creative settings
4. Logo/cover/media helpers
5. Overview / description / keywords / tags generation
6. Final review and create

**Layout**
- Shared desktop header must stay visible, using the same frameless chrome as auth and app shell
- Verification entry screen uses a centered professional card with:
  - clear title and guidance
  - six separate digit boxes for the code
  - resend timer/status
  - prominent verify CTA
- Wizard shell with large main content card
- Optional right-side contextual tips or asset preview
- Sticky footer with Back / Next / Generate / Finish actions
- Logout action must remain accessible during onboarding without cluttering the main wizard card

**Behavior**
- Preserve progress when moving between steps
- Preserve filled onboarding data when revisiting completed steps and when the Electron renderer reloads for the same signed-in account
- Each generation helper has its own loading state
- Logo cards must support both AI generation and a manual local upload option, matching the current Python onboarding behavior
- Manual logo upload should feel desktop-native: choose a local image, validate it, preview it immediately, and use it for final profile creation without introducing a separate backend upload endpoint
- Cover cards must support Python-parity local upload and local save actions in addition to AI generation
- The final onboarding step should be labeled `Overview` and behave like the Python summary/editor step:
  - show both channel profiles in a summary card
  - reuse the same backend generation endpoints for description, keywords, and tags
  - treat the generated SEO content as shared across both profiles
  - allow copy actions for description, keywords, and tags before final creation
- Final create action must clearly confirm success and transition into app shell
- Verified users must not be forced back through confirm-code on restart
- If email is already confirmed and no profiles exist, bootstrap should resume directly into the wizard
- Onboarding draft recovery must be account-safe: restore the saved draft only for the same signed-in email and clear it when a different user signs in
- Resend verification should be explicit and user-triggered, not silently fired on every mount

### 6.5 Main Shell
**Purpose**
- Provide stable desktop navigation and shared context

**Layout**
- Left sidebar: primary routes, compact account area, logout
- Top route header: page title, optional subtitle, contextual actions
- Main content outlet: full-height scroll container
- Global toaster, dialog host, command overlays later if needed

### 6.X Settings → Profiles (Image Mode)
**Purpose**
- Let users control whether the pipeline creates Background + Thumbnail jobs, Background-only, or Thumbnail-only for each channel profile.

**UI**
- Add an `Image Mode` select in the Profile editor area (Settings → Profiles):
  - `BG + TH` (default): generates both
  - `BG Only`: generates only background
  - `TH Only`: generates only thumbnail
- Persist to `profile.image_config.mode` so the backend uses the selection during job creation.

**Behavior**
- Changing image mode must not create jobs immediately; it only affects future batches.
- Mode must be visible in both profile summary and batch/workflow status views.

### 6.X Image Workspace (User-Provided Assets Mode)
**Goal**
- Reduce AI image generation by allowing users to supply background/thumbnail images ahead of time while the pipeline continues (Draft → Suno → Video).

**UX Model**
- Add a user-facing setting (Preferences) named `Image Source Mode`:
  - `AI Generated` (current default)
  - `User Provided` (bypass image AI jobs)
- When `User Provided` is selected:
  - The system pre-creates deterministic batch/profile/role output folders as soon as the batch is created, so the user can prepare assets before the image/video steps need them.
  - The Image workspace stays a monitor (queue + previews), but shows “Expected asset filenames” and an “Open Folder” action for the scoped batch/profile/role output directory.
  - If user-provided assets exist, the UI should reflect “Satisfied (User)” instead of “Pending”.
  - AI image requests are skipped when the required user files are present and valid.

**Asset Expectations**
- Background images should support both aspect ratios:
  - 16:9 for long video
  - 9:16 for reel
- The system detects image dimensions and picks the correct pipeline branch (long vs reel) automatically.

**Empty / Error States**
- If assets are missing, show a clear checklist (“Missing BG 16:9”, “Missing TH 9:16”) without blocking Music generation.
- If assets are invalid (wrong size / unreadable), show a blocking error for the downstream step only (e.g., video conversion), not a vague global failure.

**Progress / Workflow Recommendation**
- `Progress` should be the actionable operational page.
  - Show missing-manual-asset alerts per batch/profile/role.
  - Show ready/validated state once user files are detected.
  - Expose the “Continue Pipeline” action after required assets are present.
  - The action must perform a real backend sync of the manual assets into the batch image state; it must not be a visual-only acknowledgement.
- `Workflow` should remain the high-level visual timeline.
  - It summarizes stage progression (Music → Image/Manual Asset Check → Convert → Merge → Upload).
  - It should not become the primary file-management or troubleshooting surface.

**Sidebar Notes**
- Support active state with strong contrast and controlled accent treatment
- Show plan and credit summary where it adds value without clutter

### 6.6 Dashboard / Home
**Purpose**
- High-level operational summary

**Layout**
- KPI row
- Usage chart
- Recent activity table/list
- Quick actions area if useful

**Behavior**
- Use real backend stats
- Show `0` for missing values
- Keep refresh states smooth and non-jarring

### 6.7 Profile Page
**Purpose**
- Account-centered summary page

**Layout**
- Account card
- Plan/credits card
- Usage and profile allowance card
- Profile list summary or recent profile overview

**Behavior**
- Data should refresh when the route receives focus
- Trial and paid plan states must be visually explicit

### 6.8 Workflow Page
**Purpose**
- Visual pipeline overview for one selected run at a time

**Layout**
- A visually rich single-run board:
  - one compact top rail with:
    - date filters
    - `Active only`
    - refresh
    - compact run-count chips
  - left run-selector lane list for the current filtered rows
  - right selected-run surface with:
    - selected-run hero header
    - stage/status chips
    - compact summary metrics for songs/images/export/merge
    - prominent stage visualization for `Music -> Image -> Converter -> Merger -> YouTube`
- Avoid repeating the route title inside the page body when the app shell already provides the page header
- When no rows match, show one centered empty-state board instead of rendering both an empty run rail and an empty timeline panel
- Keep this page lighter than Progress and avoid row-level recovery controls here

**Behavior**
- Clear disabled states when prerequisites are missing
- Clear status badges for running, waiting, failed, completed
- Use the same canonical row model as Progress, but present only one selected run in visual form
- Keep `Workflow` focused on understanding:
  - what stage each run is at
  - which run needs attention next
  - what the selected run is waiting on
- The selected run should feel like a hero object, not just one more card in a grid:
  - show channel, role, stage, status, run date, and a concise current summary together
  - keep notes/details below that hero instead of splitting understanding across multiple same-weight cards
- Avoid duplicating dense row actions from Progress; instead, point users to Progress for recovery and operational tasks
- In Manual image mode, Workflow should show a non-blocking stage like `Waiting For User Assets`, but direct file actions should route the user to Progress / folder actions instead of duplicating controls here.

### 6.9 Progress Page
**Purpose**
- Detailed operational monitoring and recovery workspace

**Layout**
- One compact operational command strip with:
  - date filters
  - stage/limit filters
  - `Active only`
  - refresh
  - compact KPI cards/chips
- Dense job table with stage-aware filtering and recovery actions
- Keep supporting panels for:
  - desktop download queue only when it has active items
  - manual-asset readiness
  - failure/recovery affordances

**Behavior**
- Continuous refresh by polling or stream
- Row actions for open/log/retry where supported
- Empty state must be clean and informative
- This page is the action surface, not the visual storytelling page:
  - continue pipeline
  - open folders
  - inspect notes/errors
  - recover from failed/mid-pipeline states
- In Manual image mode, Progress becomes the handoff surface:
  - show which manual assets are expected for each run
  - show whether BG/TH 16:9 and 9:16 are present/valid
  - show an alert when the pipeline is waiting on the user
  - allow the user to continue/resume the downstream pipeline once the assets are ready
  - if assets are ready, the resume action should move the row out of `Image` waiting and into the next real stage (`Converter`) by syncing the manual artifacts on the backend
  - Progress metadata should separately surface `Long Ready` and `Reel Ready` so downstream desktop video work can route `16:9` and `9:16` independently instead of treating image readiness as a single boolean
- The downstream stage order should explicitly be:
  - `Music`
  - `Image`
  - `Converter`
  - `Merger`
  - `YouTube`
  - `Done`
  - `Error`
- `Converter` should represent per-track long/reel export readiness and runtime.
- `Merger` should represent final long-video merge and reel merge readiness/runtime separately from converter/export.

### 6.9.1 Workflow vs Progress Split
- `Workflow` = visual, high-level, one selected run, easy to understand at a glance.
- `Progress` = dense, operational, multi-run, action-heavy recovery surface.
- They must share the same canonical underlying row model so stage truth stays consistent.
- They must not share the same UX density:
  - if a control is operational or failure-recovery focused, it belongs in `Progress`
  - if a control is for understanding the current pipeline state visually, it belongs in `Workflow`
- Both pages should reuse the same themed control language:
  - shadcn/Radix select popovers
  - shared date-picker field
  - shared inline toggle
  - no native Windows-styled browser dropdowns or checkboxes in these workspaces
- `Workflow` should look like a monitor wall, not an operator console:
  - fewer top-level boxes
  - stronger selected-run emphasis
  - more visual hierarchy than `Progress`

### 6.10 Music Page
**Purpose**
- Main music generation workspace with strict Python-parity composition for composer and history

**Layout**
- Dense one-screen Python-style workspace:
  - top session strip:
    - From
    - To
    - Language
    - Creativity
    - Unique opening
    - Strict
    - History
    - Count
  - four-card composer row:
    - Song description
    - Song structure
    - OK channels
    - ALT channels
  - automation strip:
    - Auto-Gen Image
    - Auto-GSuno
    - Auto-Video
    - Auto Merge
    - Auto Reel
    - Auto-Upload
    - credit-cost/status note
    - Generate action
  - bottom workspace row:
    - left Song card with effect preview, title/album, copy actions, polish slider, lyrics editor
    - right History table with Python-faithful headers and compact status cells
- Keep `Music` and `Settings` as separate primary routes, matching the verified Python ownership in `init_orchestrator.py`
- Keep `Song description` and `Song structure` as dropdown-only selectors in Electron:
  - do not restore large freeform text editors from the Python page
  - selected prompt names can still drive the real generation flow behind the scenes
  - parity work should target behavior and orchestration, not reintroduce the older Python editor surface

**Behavior**
- Composer actions must remain wired to real contracts where they already exist:
  - draft generation
  - lyrics polish
  - batch creation
  - batch polling summary
- Session and automation controls should load from and persist to user settings where supported.
- Description and structure `Load` actions should use Admin Portal-backed prompt-name sources already exposed through the public prompt endpoints.
- Description and structure selection should remain dropdown-based in Electron even when Python parity logic is cloned behind the scenes:
  - load saved prompt choices from the existing prompt-name sources
  - do not expose direct text editing for these two inputs on the Music page
- History should visually match the Python table layout as closely as possible.
- History channel columns should keep Python-style folder-open affordances:
  - show the stored OK/ALT channel names only
  - use per-row folder buttons to open the recorded OK/ALT output directories when available
- The automation card should surface user-safe credit cost notes resolved from backend pricing:
  - show draft cost using the routed `lyric` operation because title, album, and lyric drafting are one LLM action
  - show polish cost using the same routed `lyric` operation
  - show revisions as a non-AI no-credit action until a real revision-generation flow exists
  - show Suno and image costs from the same admin-configured pricing table
  - show the `Generate` button label with the current total batch credit estimate for the selected pair count, planned day count, and song count, matching the backend batch precheck formula
  - only include Suno credits in that estimate when `Auto-GSuno` is enabled for the planned run
  - include image-generation credits in that total when `Auto-Gen Image` is enabled for the run
  - show a small helper note under `Generate` explaining the current planned batch count and when image credits are included
  - show plan totals in the automation card for the current selection so users can see draft, Suno, image, and combined batch credits before starting generation
  - persist `Auto-GSuno` on each batch request so the backend can keep the selected run intent instead of inferring Suno from UI defaults later
  - `Generate` should keep the current desktop UX, but each `POST /batches` call should now immediately start backend execution in the background so users are not left with a created batch that never actually runs
  - when `Auto-GSuno` is off, a generated batch should stop after draft generation and show draft progress only
  - when `Auto-GSuno` is on, successful drafts should auto-submit to Suno using the user’s current Suno default version setting
  - Suno callback completion should continue the batch lifecycle by updating the song state and creating image jobs only when the persisted batch has `auto_gen_image` enabled
  - When `auto_gen_image` is enabled, the system should also start running the newly created image jobs automatically (Python-style automation) so users do not need to press `Run pending` manually
  - when `Auto-Video` is enabled and the row is ready in Electron desktop:
    - the app should start long export automatically using the canonical long branch inputs and the profile long template
    - if `Auto Reel` is enabled, reel export should start only after standard long outputs exist, matching Python’s long-first sequencing
    - if `Auto Merge` is enabled, merge should use the existing branch-aware desktop merge runtime rather than a fake UI state
  - `Auto-Upload` must stay disabled until long-merged-output YouTube runtime parity is fully verified from the Electron shell
  - the platform now owns both the long-merge enqueue contract and a real background upload worker/runtime, and the Electron shell now has the first long-merge auto-enqueue/run hook as well
  - honest enablement still requires signed-in desktop validation that the full shell -> enqueue -> worker -> Progress feedback loop works end to end without duplicate uploads
- Primary and secondary channel sections should behave like Python `OK channels` and `ALT channels`, not as single-value selectors:
  - support multiple checked channel rows
  - preserve pair alignment between OK and ALT selections
  - prevent mismatched counts before generation
  - treat each selected calendar day as its own batch run; a 3-day range with 2 channel pairs should create 6 planned batch runs
- Generation should follow the verified Python seed-and-polish workflow:
  - reserve title, album, and optionally opening content from the pools
  - use those seeds as inspiration inputs for the LLM draft request rather than publishing them unchanged
  - generate a polished title/album/lyrics result on top of the reserved pool material
  - keep metadata that the final draft was derived from reserved pool seeds for later traceability/debugging
- History row selection should hydrate the editor with the same core fields Python restores:
  - description
  - structure
  - lyrics
  - title
  - album
- Hidden prompt behavior must stay server-owned:
  - Electron selectors show only prompt names
  - direct draft requests send selected ids so the backend can resolve hidden prompt content

## 6.X Video Parity Policy

### 6.X.1 Keep Vs Port Rule
- Keep the current Electron workstation UX where it is already better:
  - integrated center preview
  - denser inspector flow
  - smoother local editing
  - unlimited text-layer workflow
  - explicit spectrum-to-logo attachment controls
- Port Python behavior where it affects:
  - final visual semantics
  - export truth
  - missing functional controls
  - source-of-truth business logic

### 6.X.2 Spectrum First
- Spectrum is the highest-priority parity slice because it is the most visually important part of the native Python experience.
- The order for spectrum parity should be:
  1. audio-analysis semantics
  2. preset identity parity
  3. glow/composite/render-backend parity
  4. final preset art tuning
- The first parity slice is now implemented in the Electron preview engine:
  - Python-like 64-bin log-frequency analysis
  - fixed smoothing over the log bins
  - mirrored derivation applied per renderer layer
  - bass/kick-reactive energy used to drive the surrounding preview response
- The second parity slice is now implemented in the Electron preview renderer contract:
  - Python-native style names can remain distinct internally even when the Electron UI still shows curated families
  - native looks such as `thin-lines`, `symmetrical-bars`, `pixel-bars`, `floating-blocks`, `mountain`, `liquid`, and `neon-pulse` no longer have to collapse into the same few renderer branches
- The third parity slice is now implemented in the Electron preview renderer contract:
  - spectrum layers render through Python-inspired multi-pass glow plus body passes instead of only one shadow-based pass
  - additive blend behavior is now used more intentionally for glow and additive-style spectrum layers so dense halos and luminous mass read closer to native

### 6.X.3 Do Not Regress Approved Electron Improvements
- Do not reintroduce Python limitations just for parity.
- Do not revert to Python-owned live preview UX.
- Do not reduce the current text workflow back to a fixed small overlay model.
- Do not remove the current Electron attachment/gap workflow unless Python export has first been upgraded to match it.

### 6.X.4 Functional Parity Priorities After Spectrum
- Export tab honest controls:
  - thumbnail generation
  - speed/workers wiring
  - auto-merge/reel controls
  - merge stop behavior
  - manual MP3-folder workflow where still needed
- Preview/export consistency:
  - any Electron-only visual rule that affects final output must either be ported into Python export or clearly marked as preview-only
  - batch orchestration must resolve stored song `description_id` and `structure_id` back to hidden Admin prompt content before generating drafts
- Unsupported Python actions must still appear honestly where needed for parity, but stay disabled/limited instead of faked:
  - folder-open actions
  - Suno retry
  - destructive hide/delete actions
  - full row backfill when required fields are not yet returned by the backend history contract

### 6.11 Image Page
**Purpose**
- Provide the Python-style image workflow as a queue-first execution page: filter by date range, generate and inspect background/thumbnail jobs in one view, and let users understand the two-stage image process clearly.
- Keep the system honest: the Image page should reflect real job-queue execution status, not only “single prompt generation”.

**Layout**
- Top section uses a `2/3 + 1/3` layout.
- Left area:
  - date range filter (`From` / `To`)
  - `Reload` and queue maintenance actions only (no manual generation CTA)
  - queue list/table near the top of the card (primary surface)
  - `Background Prompt` textarea below the queue list
  - `Thumbnail Prompt` textarea below the queue list
  - queue summary stats for the selected date range
- Right area:
  - stacked `Background Preview` and `Thumbnail Preview`
  - preview labels should make it obvious which stage the user is seeing
  - selecting a queue row updates both previews immediately
- The queue must stay visible beside the previews rather than below them so users can click items and compare outputs without scrolling between list and preview.

**Behavior**
- Queue behavior mirrors Python:
  - date filters map to hidden matching batch IDs from music history
  - jobs are created by automation (Suno callback + batch flags) rather than manual user-triggered generation
  - image jobs are stored in the shared `image_jobs` table (background + thumbnail)
  - queue table shows BG + TH statuses per channel role
  - failed jobs can be retried
  - successful jobs show a preview and can open the output folder
- Prompt behavior must become explicit and two-stage:
  - `Background Prompt` guides the creation of a new background image from the background sample library
  - `Thumbnail Prompt` guides thumbnail generation using the generated background image plus thumbnail style guidance
  - the UI must not imply that one generic prompt is enough for both stages
- Queue selection behavior:
  - single click selects a row and pins both previews
  - output previews should remain stable while the user reviews another row
  - queue rows need dense desktop spacing and must prioritize scanability
- Sample-library behavior:
  - background sample images come from a managed background sample library
  - thumbnail sample images are style references, primarily for text/style direction rather than completely replacing the generated background composition
  - unselected images remain available as fallback for random selection unless the future execution rules intentionally restrict them
- Sample delivery behavior:
  - users should not receive large sample packs bundled inside the app
  - the app should offer separate `Background` and `Thumbnail` download pickers
  - each picker shows a list of admin-managed pack names so users can choose the correct library before downloading
  - downloads come from admin-managed external pack links, then extract into local sample-library folders automatically
  - once extraction finishes, the user library refreshes without requiring manual path repair
- Admin behavior:
  - Boss manages sample-pack sources in Admin Portal, not inside the user app
  - Admin Portal manages multiple named pack-link entries per category:
    - `background`
    - `thumbnail`
  - each entry should support add, update, remove, and reorder/list management
  - the user app should only expose the entry names plus download actions, not raw URLs
  - future pack versioning should be possible without changing the desktop UX
- UX constraints:
  - use compact controls (shadcn/Radix selects, internal scrolling lists)
  - avoid freeform “fake” settings that are not wired to the backend pipeline
  - clearly label which actions incur credits when applicable
  - clearly distinguish between:
    - sample-library assets
    - generated background output
    - thumbnail style references
    - user-written prompts

### 6.12 Video Page
**Purpose**
- Control video template editing, preview, and export workflow from one workstation while migrating preview ownership into the Electron renderer

**Recommended Layout**
- Rebuild the page to match the Python Video workspace arrangement exactly:
  - same three-pane order as `python_app/views/video_view.py`
  - same section order inside each pane
  - same action grouping and operator reading flow
  - same fixed rail widths unless an Electron-only technical reason requires otherwise
- The parity target is arrangement parity first, not just general style similarity:
  - left settings rail fixed to the Python baseline
  - center workspace with preview toolbar, large preview host, playback, then export queue
  - right-side inspector rail fixed to the Python baseline
- React/Electron should own:
  - the full UI shell and controls
  - the in-workstation preview surface
  - preview playback/time scrubbing state
  - preview capability/fallback messaging
- Python should temporarily continue to own:
  - final render/export implementation
  - existing merge/output tooling already wired into the desktop pipeline

**Preview Model**
- The center pane must host a real renderer canvas, not a native child window.
- The preview shell remains the same workstation shape:
  - preview title row
  - output resolution control
  - playback row
  - large preview viewport
  - text layer strip below
  - export controls in the right rail
- The renderer preview should now follow a WebGPU-only path for the whole live compositor:
  - use one WebGPU surface as the live preview output inside the workstation
  - build spectrum from a linear bar foundation first, then use `Curve 180` and `Mirror 360` to form half-ring and full-ring motion
  - move background, logo, smoke, vignette, and text presentation into that same GPU-owned output path instead of keeping them as DOM overlays
  - never silently fall back to Canvas2D for spectrum rendering or reintroduce a second visible renderer path
- While the asset pipeline is still temporarily hybrid, the visible background/logo fallback shell must remain behaviorally truthful:
  - background motion, brightness, and smoothing must read the same as the compositor path
  - logo scale, pulse, opacity, masking, and spin must read the same as the compositor path
  - temporary fallback rendering should add premium polish rather than dropping the user into a flatter or less reactive look
- Engine-first delivery order inside the live preview should now prioritize renderer capability over workstation polish:
  - restore particles as a native GPU pass first
  - then move atmosphere/post-FX work deeper into native compositor passes
  - defer non-blocking inspector polish unless it is required to validate those engine slices
- Preview must feel immediate and trustworthy:
  - background/logo changes reflect instantly
-  - spectrum/effects stay on one GPU renderer path instead of mixing GPU results with DOM/CSS presentation
-  - text and asset layers remain synchronized because they are composed into the same renderer-owned output surface
  - unsupported parity gaps are labeled honestly instead of being faked

**Behavior**
- Template-setting changes persist through the Electron bridge into the selected local Python template source
- Control changes from React should drive the renderer preview directly from the same draft/template state used by the existing controls
- Preview reflects changes with low latency without depending on Python preview IPC
- The app should remember renderer capability state, active fallback mode, and preview health
- The page should also show canonical pipeline inputs for the selected run:
  - user selects a recent run from Progress data
  - user switches between `Long (16:9)` and `Reel (9:16)`
  - background + thumbnail paths resolve from `batch_channel_assets`
  - the UI surfaces the recommended profile template for that branch before full converter/export parity exists
- The page continues to own the current real desktop export controls for those canonical inputs:
  - `Start Long Export` / `Start Reel Export` launch the Python visualizer CLI from the selected run dir and branch background
  - `Stop Export` cancels the active desktop export worker set
  - export status remains visible in the route with completed count and last output path after the run ends
- The new preview phases should extend the same page with:
  - renderer-side audio analysis
  - renderer-side spectrum, particles, and text animation
  - preview effects/compositing that approximate current export behavior
  - explicit mismatch notes where preview and Python export are not yet 1:1
- The current parity audit confirms the most important live mismatch notes the product must treat honestly until closed:
  - Python export now consumes the same persisted spectrum-to-logo attachment fields and visible-alpha radius logic as a first-pass parity slice, but still needs visual QA against Electron preview for exact attachment feel
  - Electron preview now honors `startSec`, `durationSec`, and the current animation timing families for DOM text overlays, but still remains an approximation of Python’s native text renderer rather than a 1:1 rendering backend
  - Python export now understands the curated Electron spectrum families and multi-stop gradient ramps as a first-pass parity slice, but still needs visual QA/tuning so final output identity matches the Electron preview more closely
- Long-term direction:
  - preview ownership moves permanently to the renderer
  - export can stay on Python temporarily
  - later phases define whether the renderer engine also becomes the export source

**Spectrum Presets And Layers**
- The Video spectrum workflow should use one consolidated `Spectrum Preset` control rather than separate `Style Preset` and `Stacked Ring Preset` controls.
- The preset list should stay intentionally small and curated rather than offering many near-duplicate looks.
- A preset should always represent a complete visual recipe:
  - simple presets create a one-layer recipe
  - stacked presets create a multi-layer recipe
- The renderer must treat each curated family as a genuinely different visual system, not as the same bar geometry with different numbers:
  - `Straight Bars` = disciplined premium linear bars with clean body/tip separation
  - `Flying Glow` = top-arc wing lift with brighter tips and stronger forward emission
  - `Dot Matrix` = segmented luminous dot field, not short rectangular bars
  - `Wave Ribbon` = continuous ribbon-like waveform mass with smooth continuity between samples
  - `Liquid Mass` = filled reactive body with cohesive mass and softer edge energy
  - `Halo Stack` = layered premium halo composition with distinct inner/core/outer identities
- Current curated direction:
  - `Straight Bars`
  - `Flying Glow`
  - `Orbital Bars`
  - `Dot Matrix`
  - `Wave Ribbon`
  - `Liquid Mass`
  - `Halo Stack`
- `Orbital Bars` should cover the rounded circular-equalizer reference:
  - full-circle rounded bars around the logo
  - general music should distribute motion around the whole ring rather than building a wing silhouette
  - colors should read clean and luminous around the circle, closer to a classic orbit equalizer than a blob or ribbon
- Curated presets should all start from the same disciplined linear line-bar foundation unless Boss later asks for a ring-first family again:
  - presets differ through rendering family, shading, blend behavior, color story, and motion character
  - presets should not silently switch the user into a different curved/ring geometry just because a different preset was chosen
- `Flying Glow` should visually read closer to a winged/neon lift effect:
  - brighter tips than bases
  - stronger upward luminous travel
  - a premium forward-lift line family instead of collapsing into a generic neon ring
  - default to curved + mirrored geometry so the preset starts as an arc/ring-ready look rather than a flat bar strip
  - use a wing envelope with stronger shoulder/ear flare and a softer center dip, closer to cat-ear or flying-wing silhouettes seen in tools like Vizzy
  - react to bass hits through a quick flare that clears fast, so the wing “opens” and “falls” smoothly instead of holding a fat blob
  - the visible wing should read as a near-solid continuous surface with very little negative space between bars, so the result feels smooth rather than ribbed
  - at rest, the ring should stay evenly rounded around the logo rather than already looking deformed into a wing
- Audio-reactivity controls should remain non-duplicated and semantically clear:
  - `Input Gain` = upstream audio drive into the equalizer engine
  - `Band Contrast` = separation between stronger and weaker frequency bands
  - `Transient Focus` = how strongly local hits and short accents rise above the sustained bed
  - `Kick Impact` = kick/drop helper for larger low-end transient flare
  - `Motion Smoothing` = temporal softness / persistence of the spectrum motion
  - the spectrum UI can change names and layout freely as long as these controls stay semantically distinct and only affect spectrum behavior
- Cross-family audio-reactivity target:
  - no curated spectrum family should read like the whole ring or bar field is moving as one averaged block
  - different instruments and frequency bands should create clearer local spike separation so the visualizer feels alive
  - normal music beds can stay smooth, but the engine must still surface local peaks and transient contrast instead of flattening them away
  - the equalizer should be built from standard audio features first, then interpreted visually by each preset family
  - sustain/energy should remain the main bed, while per-band onset delta should act as a secondary local-spike helper instead of replacing the whole spectrum with one shared beat pulse
  - changing presets should change how the same music is drawn, not secretly replace the underlying audio analysis model
  - the post-analysis output must still use enough vertical range so bars do not look permanently short at normal editing values
  - `Spike Height` must remain a visibly strong geometry control with enough headroom to produce tall bars when Boss pushes it high
  - the `Audio Engine` controls must create clearly visible differences in the preview, not only small internal math changes:
    - `Input Gain` should noticeably increase or calm the spectrum body
    - `Band Contrast` should visibly separate hot bins from weaker neighbors
    - `Transient Focus` should make short hits pop more clearly
    - `Kick Impact` should create visible low-end flare across all curated families, not just update hidden reactive helpers
- Wing-family motion target:
  - `Flying Glow` should not stay permanently open once a kick hits
  - the wing should open quickly on impact, then collapse back down quickly and smoothly toward its lower resting state before the next hit
  - the effect should read like repeated flight beats rather than a continuously inflated ring
  - kick onset should be the primary height driver for the wing, while the rest of the spectrum only adds light internal texture instead of keeping the wing open
  - non-kick music should still animate the ring subtly, but the large wing silhouette should be reserved for kick starts and bass-drop moments
  - the subtle “music is playing” reaction should appear as a small full-circle waveform bed around the logo, not as an already-open wing
  - `Flying Glow` must never look visually dead while music is playing:
    - the resting circular bed should breathe enough to read as live motion
    - kick/drop moments should extend that bed into a clear shoulder-wing flare
    - the rest-ring floor must not dominate so strongly that ordinary music appears frozen
    - the wing should also collapse back down quickly enough that repeated kicks read as separate beats rather than one long inflated halo
    - wing flare timing should follow beat strength directly, so harder hits can open longer/deeper while smaller hits open less and fall sooner
    - when the music relaxes, `Flying Glow` should return to a smaller breathing ring rather than leaving a visible idle wing silhouette hanging open
    - low beat-drive moments should visually read as ring-first, while the shoulder-wing silhouette should only become obvious when the fast beat-drive rises
    - the biggest wing silhouette should be reserved for clearly stronger beats so Boss can read stronger/weaker hits instead of seeing one similar held-open shape
    - ring motion and wing motion must feel like different jobs: the ring can stay musically alive, but the wing silhouette must disappear when beat drive is not strong enough
    - the wing should behave as a real beat envelope:
      - each beat opens it
      - it must fall back down between beats
      - faster beat patterns should create faster close/reopen cycles
      - slower beat spacing can allow a longer visible flare before collapse
    - Boss should be able to tune that collapse feel directly for `Flying Glow`:
      - lower `Flying Glow Wing Release` = quicker close after each beat
      - higher `Flying Glow Wing Release` = slower close after each beat
      - this control must not remove the beat-following close/reopen rhythm
    - `Flying Glow Wing Release` must have enough headroom to feel obvious in the live preview, not just as a tiny timing difference
    - the wing should be able to catch bass phrasing more naturally, not only the sharpest kick/drop spikes
    - bass support must not make the wing snap closed unnaturally fast after a hit; it should help the wing linger musically instead of shortening the visible tail
    - bass support also must not behave like a fake new kick; the wing should only visibly reopen on a real trigger pulse, not simply because low-end support is still present
    - on very fast repeated `beb beb beb` beats, the wing should not keep refreshing while it is still obviously open; it must fall enough to read a real close before the next reopen
    - the visible wing should read as a smoother solid form:
      - less square-toothed edge breakup
      - more continuous shoulder/body flow
      - keep some texture, but prioritize a clean flying-wing silhouette
- The spectrum workflow stays consolidated:
  - preset = starting look
  - layer controls = custom tuning of geometry, blend, glow, gap, and ring behavior
  - the layer controls live inside the `Spectrum` tab (no separate `Layer` tab)
- The color engine inside the Spectrum layer editor should make both `Solid Color` and `Gradient` explicit:
  - a solid wing look should be just as discoverable as the gradient workflow
  - the UI label should describe color styling clearly, not force Boss to infer that `Mode` means color mode
- Spectrum editing should behave like a local workstation session instead of a form that saves every mouse movement:
  - changing spectrum controls should update the preview immediately
  - same-template query refreshes or route remounts in the same app session must preserve the current local spectrum draft
  - the saved template should update only when Boss clicks an explicit spectrum save action
  - discarding should restore the currently saved template spectrum state
- Default preset behavior:
  - each curated spectrum preset should start with one layer only
  - stacked/multi-layer looks should be user-authored from the Spectrum layer panel through `Add` or `Duplicate`, not silently pre-seeded by the preset itself
- Layer edits must remain authoritative after a preset is applied; later audio-reactivity or position updates must not silently overwrite the current layer stack.
- Presets must feel visually distinct in the renderer, not only numerically different in forms:
  - dots vs lines vs waveform vs filled mass vs floating blocks
  - half-ring vs full-ring behavior
  - additive/screen vs normal compositing
  - filled core vs hollow ring behavior
- Gradient behavior must feel premium and continuous:
  - multi-stop gradients should interpolate smoothly instead of stepping between hard color bands
  - circular/radial direction choices should materially change the look
  - glow color and body color should remain visually related instead of collapsing into one flat wash
- Blend behavior must remain honest:
  - `normal`, `screen`, and `add` style layers must not all resolve to the same additive-looking output
  - the engine should preserve enough separation between body energy and glow energy so premium presets do not turn into one oversaturated neon block
- Audio-reactive motion must read clearly:
  - neighboring bars should not react almost equally across the whole band
  - quiet bins should stay visibly lower instead of being artificially floored too high
  - renderer softness/blur should stay controlled so the spectrum remains crisp before glow is added
- Final premium-family tuning goals:
  - `Straight Bars` should act as the flagship linear preset: crisp bar body, restrained side glow, brighter tip energy, and disciplined spacing rhythm
  - `Wave Ribbon` should feel like one continuous illuminated waveform band with softer internal motion and less generic bar behavior
  - `Liquid Mass` should show stronger body-versus-highlight separation so the mass reads dense first and glossy second
  - `Halo Stack` should feel like layered inner-core, mid-light, and outer aura hierarchy even when the preset begins as one user-editable layer
  - bloom should support these families instead of flattening them into the same glowing wash across bright songs and dark backgrounds
- Preset UX should stay minimal and honest:
  - one preset dropdown is enough
  - selecting a preset should directly apply that recipe instead of requiring a second ambiguous “pick preset” step
  - selecting a preset should directly apply that recipe instead of requiring a second ambiguous “pick preset” step
- Preview background behavior must stay truthful:
  - if the selected pipeline branch already resolves a background image, the center preview should use it unless a manual preview background overrides it
  - the route should not report loaded background context while the visible preview still falls back to a black/default engine scene

**Text Overlays (CapCut-style)**
- The Text workspace should behave like a mini “text layer editor” that is always visible under Preview + Playback:
  - unlimited text layers (not hard-capped to 4/5)
  - clear selected layer, reorder, and enable/disable behavior
  - presets to create common styles quickly without manual re-entry
- Recommended layout:
  - render a compact text-layer manager under the center Preview + Playback stack (so the center stays focused on what exists on canvas)
  - keep the center Preview + Playback fixed; scroll starts below for Text only (Export Queue lives in the right rail)
  - compact toolbar row (Add, Presets, Duplicate, Delete, Reorder)
  - scrollable “Text Layers” list (each row shows enabled state + name + timing)
  - move the selected layer controls into the right rail with tabs:
    - `Text`: content, size, color, alignment, style presets
    - `Animation`: timing, anchor, motion preset, transform offsets
    - `Export`: queue/actions/status
- Text interactions should update the renderer preview immediately and make layer selection visually obvious on-canvas where feasible.

**Video Workstation Shell Revamp**
- The Video route should now behave as a preview-first workstation instead of a form-first settings page.
- Recommended shell:
-  - left rail = template/session context plus the active visual-system controls (`Spectrum`, `Background`, `Logo`, `Particles`)
  - center stage = preview canvas first, transport second, quick asset context third, text-layer manager fourth
  - right rail = contextual inspector for `Text`, `Animation`, and `Export`
- The next enterprise-hardening slice for the Video page should add a dedicated diagnostics and recovery surface without breaking the three-pane workstation shape:
  - keep diagnostics scoped to `/app/video` only
  - surface operator truth already present in the runtime instead of inventing a second state model
  - recovery controls must be explicit buttons, not hidden auto-repair logic
- Recommended diagnostics panel contents:
  - current template id/name
  - dirty state by domain (`Spectrum`, `Background`, `Logo`, `Particles`, `Text`)
  - preview runtime health (`playing`, `loading`, `ready`, fallback-scene/runtime remount status)
  - selected pipeline branch/run and resolved asset readiness
  - active background/logo/track/run-dir paths
  - last save/export status
- Recommended recovery actions:
  - `Remount Preview`
  - `Refresh Workspace`
  - `Reset Local Draft`
  - `Copy Diagnostics`
- Placement rule:
  - diagnostics should read like an operator support card, not a developer-only hidden debug drawer
  - keep it visible within the Video workstation, but separate it from the normal edit-inspector controls so Boss can inspect health without confusing it for spectrum/background/logo settings
- Implemented result:
  - the left rail now carries a visible diagnostics card for the active Video workstation
  - the diagnostics card surfaces per-domain dirty state, preview/save/export/pipeline status, and key asset/run-path truth
  - recovery controls now include `Remount Preview`, `Refresh Workspace`, `Reset Local Draft`, and `Copy Diagnostics`
- The next Video-only hardening slice should make preview lifecycle state explicit and operator-visible:
  - distinguish `unsupported`, `initializing`, `running`, `recovering`, `device lost`, and `fallback active`
  - keep these states visible in the stage and diagnostics card
  - recovery messaging must be honest when the preview can render only a fallback scene or when WebGPU is unavailable
- Lifecycle UX rules:
  - `Remount Preview` should move the preview into a visible recovery state, not silently restart without feedback
  - the stage badges and diagnostics card should agree on the same lifecycle truth
  - the preview surface should continue to explain missing background/logo assets separately from engine capability or runtime failure
- The next Video-only UX hardening slice should make degraded preview states easier to trust at a glance:
  - unsupported or device-lost states should read as operator guidance, not generic status text
  - fallback-active should be treated as a degraded-but-editable mode, not the same as a hard preview failure
  - the center stage should explain what Boss can do next without forcing a trip into the diagnostics rail
  - diagnostics should summarize the same lifecycle guidance in a denser operator card, not as a developer-style dump
- Implemented `M7.A11` result:
  - the center stage now shows a visible `Preview Guidance` callout whenever live output is unavailable, recovering, or degraded into fallback mode
  - the diagnostics card now switches from one generic lifecycle paragraph to guidance-first recovery copy when attention is required
  - fallback mode messaging now explains that the workspace remains editable even when the default engine scene is still standing in for real asset context
- The next Video-only layout refinement slice should focus on hierarchy rather than new behavior:
  - the left rail should prioritize template selection and the active editor tab over the diagnostics surface
  - diagnostics should stay reachable, but collapse behind a compact support section unless Boss needs recovery actions
  - the right inspector should show a purposeful empty state when no text layer is selected
  - the three-column shell should give the center preview slightly more room so the page feels less like three equally loud sidebars
- Implemented `M7.A12` result:
  - diagnostics now sit behind a compact `Diagnostics & Recovery` disclosure below the active editor content instead of occupying the fixed top-left stack
  - the right inspector now explains how to create or select text layers when nothing is selected, so no-selection mode reads as intentional
  - the center preview gets slightly more width on larger screens, improving the page hierarchy without changing the editing flow
- The next Video-only polish slice should remove duplicated and low-signal information:
  - avoid repeating the same export/lifecycle/text-save status in multiple rails
  - remove explanatory copy that does not change the next action Boss can take
  - keep the preview overlay clean in healthy mode and reserve heavy copy for degraded or warning states only
- Implemented `M7.A13` result:
  - the right inspector no longer repeats export/text-save status that is already obvious elsewhere
  - the left rail and stage now use shorter labels and less explanatory filler
  - the preview overlay now stays quiet in healthy mode and only surfaces warning/degradation details when something actually needs attention
- The next Video-only polish slice should reduce label chrome inside the inspector controls themselves:
  - avoid spending a full left column on every select or color field
  - remove disabled controls that only communicate “not available”
  - shorten obvious toggle labels when the surrounding section already names the feature
- Implemented `M7.A14` result:
  - select, color, and numeric controls now read more like compact workstation controls instead of labeled form rows
  - one disabled background control was removed entirely
  - toggle labels are shorter where the surrounding card already provides enough context
- The next Video-only cleanup slice should remove the remaining structural noise:
  - drop `Pipeline Context` and `Stage Context` style headings where the surrounding layout already makes the purpose obvious
  - strip instructional helper copy from the Spectrum audio section unless it changes the next action
  - justify the Video-page tabs so the rails look balanced instead of left-packed
- Implemented `M7.A15` result:
  - the left rail no longer shows a separate `Pipeline Context` block
  - the center asset card no longer announces itself as `Stage Context`
  - the Spectrum audio section is now plain and compact
  - Video-page tabs now distribute evenly across their rails for cleaner alignment
- The next Video-only cleanup slice should keep the Spectrum tab honest in a narrow rail:
  - no horizontal scrolling for the Spectrum cards
  - dense control rows should stack before they overflow
  - destructive template actions should not appear unless they map to a real deletion flow
- Implemented `M7.A16` result:
  - Spectrum layer cards now stretch and shrink within the left rail instead of relying on horizontal squeeze
  - dense action/toggle/color rows stack or shrink before they cause overflow
  - the removed template-level `Delete` control stays out because it never had a real destructive workflow behind it
- Current implementation status:
  - the text-layer manager is now delivered through extracted workspace panels
  - the right-rail export inspector is now delivered through a dedicated export panel module
  - the visible shell/interaction model stays the same while implementation ownership is moved out of `VideoWorkspacePage.tsx`
  - the active visual-domain inspectors now consume explicit draft slices instead of one shared page-wide draft contract
  - workspace draft hydration/restoration now runs through a dedicated coordinator hook instead of page-local effects and refs
  - shell-side tab selection, preview transport state, and template/background staging now run through a dedicated workspace shell hook
  - bridge-side actions such as template switching, export start/stop, preview audio selection, and background selection now run through a dedicated workspace command hook
  - the center preview/export/text stage now runs through a dedicated stage component and the intentional logo↔spectrum editor seam now runs through a dedicated binding hook
  - the left template/context shell now runs through `VideoWorkspaceLeftRail.tsx`
  - the right inspector shell now runs through `VideoWorkspaceRightRail.tsx`, keeping text/export inspection outside the page file
  - the remaining three-column workspace composition now runs through `VideoWorkspaceShell.tsx`, so the page no longer assembles left/stage/right presentation inline
  - the page-to-shell workstation presentation contract now runs through `useVideoWorkspaceViewModel.ts`, so `VideoWorkspacePage.tsx` no longer maps the shell prop surface inline
  - the page-level workspace query/orchestration flow now runs through `useVideoWorkspaceCoordinator.ts`, so the route file is reduced to error gating plus shell mount
  - preview audio transport and playback-state snapshots now run through `audioFeatureBus.ts` and `transportClock.ts`, so `RendererVideoPreview.tsx` no longer owns the full audio runtime lifecycle inline
  - preview background/logo asset decode, load status, and logo visible-radius analysis now run through `usePreviewAssetManager.ts`, so `RendererVideoPreview.tsx` no longer owns those asset lifecycle effects inline
  - preview frame production now runs through `usePreviewRuntime.ts`, `previewAnimationLoop.ts`, and `previewFrameRunner.ts`, so `RendererVideoPreview.tsx` no longer owns the RAF loop and per-frame render orchestration inline
  - preview scene assembly now runs through `previewScene.ts`, so the frame coordinator and preview shell consume one immutable scene payload instead of ad hoc raw draft/workspace inputs
  - preview provider wiring now runs through `PreviewProvider.tsx`, while `RendererVideoPreviewSurface.tsx` owns the stage presentation shell for DOM layers and preview status messaging
  - `RendererVideoPreview.tsx` is now reduced to the thin compatibility wrapper that composes the provider path and preserves the existing exported helper surface for tests and dependent code
  - preview asset source resolution plus decode-state ownership now enter the provider through `usePreviewAssetService.ts`, so the provider consumes one asset-facing service contract instead of stitching lower-level hooks together inline
  - preview surface lifecycle now enters the provider through `usePreviewSurfaceLifecycle.ts`, so container sizing and WebGPU startup/shutdown no longer live inline beside scene and transport orchestration
  - preview transport and audio coordination now enter the provider through `usePreviewTransportCoordinator.ts`, so playback status reporting, audio bootstrap, volume updates, and playback commands no longer live inline beside scene and frame orchestration
  - preview scene assembly now enters the provider through `usePreviewSceneState.ts`, while provider-to-runtime option shaping now enters through `usePreviewProviderState.ts`, `usePreviewRuntime.ts`, and `previewFrameContract.ts`, so the provider mostly composes explicit runtime services instead of carrying large inline derivation blocks
  - background/logo DOM presentation now runs through `previewDomPresentation.ts` while fallback backdrop/overlay compositing runs through `previewCanvasCompositor.ts`, leaving `previewDomFrameRenderer.ts` as a thin DOM-side composition seam instead of one mixed renderer
  - analysed-frame resolution, reactive-energy derivation, and motion-state updates now run through `previewReactiveFrameState.ts`, so the RAF coordinator is more focused on frame timing and render-side orchestration than on reactive signal derivation
  - spectrum instance assembly now runs through `features/video/domains/spectrum/spectrumGpuRuntime.ts` and particle simulation now runs through `features/video/domains/particles/particleGpuRuntime.ts`, while the final caller-facing GPU seam is now `previewGpuRuntimeCoordinator.ts` instead of a separate compatibility wrapper
  - frame-timing accumulation and debug-report emission now run through `previewFrameTelemetry.ts`, so the RAF coordinator is more focused on lifecycle and helper orchestration than on inline diagnostics bookkeeping
  - shared debug event transport now runs through `videoDiagnostics.ts`, so the preview runtime and workspace orchestration no longer duplicate raw debug-server `fetch(...)` calls inline
  - frame layout/DPR resolution, anchor-to-center geometry, delta timing, and playback-report cadence now run through `previewFrameState.ts`, so the RAF coordinator is more focused on loop ownership and helper delegation than on inline frame-state math
  - requestAnimationFrame scheduling and previous-timestamp handoff now run through `previewAnimationLoop.ts`, so the coordinator is more focused on effect-level orchestration than on low-level RAF chaining
  - per-frame runtime orchestration now runs through `previewFrameRunner.ts`, so the coordinator is reduced to diagnostics setup, loop wiring, and runner delegation rather than embedding the full frame body inline
  - preview frame telemetry wiring and debug event emission now run through `previewRuntimeDiagnostics.ts`, so the runtime hook is reduced to the effect boundary rather than any diagnostics setup work
  - `PreviewProvider.tsx` now composes `usePreviewRuntime.ts` directly, so the preview runtime no longer routes through thin bridge/coordinator layers that only forwarded the same option surface
  - `PreviewProvider.tsx` now delegates provider-side orchestration to `usePreviewProviderState.ts`, so the component stays focused on the render contract instead of owning asset/surface/transport/scene/runtime composition inline
  - preview provider contract types now live in `previewProviderContract.ts` while runtime/frame contract types live in `previewFrameContract.ts`, so the preview path no longer routes provider and per-frame ownership through one shared aggregate module
  - playback-report cadence application and transport snapshot reporting now run through `previewPlaybackReporter.ts`, so `previewFrameRunner.ts` is more focused on scene orchestration than on transport policy
  - frame telemetry timing application and report payload shaping now run through `previewFrameReporter.ts`, so `previewFrameRunner.ts` no longer owns the preview debug report schema inline
  - atmosphere shaping now runs through `features/video/domains/atmosphere/atmosphereGpuRuntime.ts`, shared post-FX composition now runs through `previewGpuPostFx.ts`, final execution-plan assembly now runs through `previewGpuExecutionPlan.ts`, GPU timing/result packaging now runs through `previewGpuRuntimeResult.ts`, final WebGPU submission runs through `previewGpuSubmission.ts`, GPU domain preparation now runs through `previewGpuDomainPreparation.ts`, shared submission orchestration now runs through `previewGpuSubmissionOrchestrator.ts`, and the top GPU orchestration now runs directly through `previewGpuRuntimeCoordinator.ts` after the compatibility wrapper was removed
  - fallback-scene submission, spectrum-instance submission, and atmosphere eligibility now live in the immutable `previewScene.ts` GPU policy node, while spectrum, particles, and atmosphere enter the preview runtime through domain-owned runtime entrypoints, bloom/post-FX tuning math is isolated behind its own preview helpers, and the older preview-side compatibility wrappers are removed from the live path
  - the next Video-only hardening slice should reduce the remaining workspace hotspots by:
    - moving final template-save assembly out of `settingsTemplateDraft.ts`
    - splitting `useVideoWorkspaceCoordinator.ts` into thinner save/recovery/diagnostics seams
    - surfacing the existing preview/workspace health signals inside a visible diagnostics card with explicit recovery controls
- The center stage should always answer the production questions before the user opens deeper controls:
  - which run is active
  - which branch is active (`Long` or `Reel`)
  - which background/logo/track are currently driving the preview
  - whether the current branch is export-ready
- The shell should feel like one integrated studio surface:
  - preview and transport are visually primary
  - editor controls are grouped into smaller workstation cards instead of one long generic form column
  - export context should remain visible without forcing the user to leave preview-focused work
- Text-layer management should stay directly under the preview so the user can think in canvas/layer order instead of losing text editing inside the left settings rail.
- The revamp should preserve the current patch/mutation semantics and should not invent a second state system just to change layout.

### 6.12.1 Delivery Closure Rules For `M7.A2` To `M7.A5`
- `M7.A2` closes only when the aggregate draft stops acting as the live preview/runtime contract.
- `M7.A3` closes only when cross-domain composition is explicit and limited to approved scene/binding seams.
- `M7.A4` closes only when the preview runtime public seams are frozen and remaining compatibility adapters are intentional, not accidental.
- `M7.A5` closes only when Spectrum, Background, Logo, and Particles each own their editor/runtime boundaries and cross-domain tests prove isolation.

Current progress note:
- `M7.A2.2` is now complete for the preview GPU/runtime path: the aggregate draft is adapted at the runtime edge and the deeper preview helpers consume narrowed domain/layout slices instead of the shared draft type.
- `M7.A2.3` to `M7.A2.5` are now complete: scene/binding helpers use narrowed contracts, renderer-preview files use the shared video draft contract instead of the workspace shim, and a source-boundary test prevents non-workspace imports of `settingsTemplateDraft.ts`.
- `M7.A3.3` to `M7.A3.5` are now complete: the immutable preview scene carries runtime-ready node inputs, the frame runner no longer reconstructs composition from `scene.draft`, and a scene-boundary audit prevents direct draft reads or sibling-domain imports from creeping back in.
- `M7.A5.1` is now complete: the live Spectrum editor/runtime/renderer path reads from spectrum-domain modules for preset/template logic, layer contracts, WebGPU instance assembly, and preview runtime helpers, while a dedicated boundary audit blocks production callers from slipping back onto the legacy preview adapter path.
- `M7.A5.2` to `M7.A5.5` are now complete: Background, Logo, and Particles each own their live editor/runtime paths, compatibility shells are reduced to explicit legacy re-exports only, and the final domain-isolation audits prove production callers no longer route through preview-owned adapter files or settings-owned domain helpers.
- `M7.A6` to `M7.A8` are now complete: installable effect packs reuse the shared desktop registry/install model, appear as first-class catalog items in the workspace inspectors, fail closed on compatibility errors, expose recovery actions honestly, and are locked by focused manifest/registry/recovery/isolation tests.

Marketplace narrowing note:
- `M7.A6` should ship as one coherent user flow:
  - discover available packs
  - install/download safely
  - browse by domain
  - preview/apply without touching unrelated domains
  - save pack references into templates
- `M7.A7` should ship as one coherent recovery flow:
  - reject malformed packs before activation
  - stage updates before live activation
  - roll back automatically on failure
  - show disabled/missing/incompatible states honestly
  - let Boss retry, disable, remove, or fall back intentionally
- `M7.A8` should lock the marketplace UX with tests that match the real user risk:
  - install/update/remove registry behavior
  - missing/disabled pack recovery
  - per-domain preview/apply isolation
  - cross-domain boundary protection

Implemented marketplace UX result:
- Spectrum, Background, Logo, and Particles each expose the same pack-management surface for install, reload, apply, clear, enable, activate, and remove actions.
- Pack preview/apply stays scoped to the selected domain instead of rewriting unrelated draft fields.
- Saved templates retain pack references by id/version, while the workspace resolves missing, incompatible, broken, or disabled selections into honest status messaging.
- Registry safety is transactional, so failed updates restore the previously active version instead of leaving the workspace in a half-installed state.

### 6.13 Settings Page
**Purpose**
- Clone the Python primary settings workspace inside the Electron Settings route

**Layout**
- Start directly with a compact one-row tab rail:
  - YouTube
  - Profiles
  - Publication
  - Settings
  - Descriptions
  - Structures
  - Pools
  - Suno
  - Database
- Avoid extra dashboard-style route summary cards above the tabs
- Each tab should mirror the Python tab content grouping and field labels as closely as the current safe contract allows
- `Profiles` and `Publication` should prefer compact labeled rows with small icons and fewer repeated action bars
- `Publication` should allow direct profile switching from inside the tab and use Python-style scheduled time dropdowns with helper text that the batch date supplies the date portion
- `Preferences` should visually follow the compact `YouTube` tab baseline:
  - smaller labels and buttons
  - tighter row height
  - fewer nested dashboard-style cards
  - compact inline path actions
  - controls that stay information-dense without wasted vertical space
- `Pools` should move out of the user desktop app and into Admin Portal ownership for mutation/generation because:
  - pool content is effectively a shared catalog, not a per-user local preference
  - Admin Portal already owns provider/key pool management and is the right control plane
  - Electron should avoid becoming a second admin surface
- Admin Portal should provide the real content-pool manager:
  - tabbed management for titles, albums, and openings
  - stats and used-count visibility
  - built-in preset generation
  - admin-managed preset packs per pool kind
  - bulk import
  - inline edit/delete
  - admin-confirmed clear flows
- Preset-pack management UX should stay on the same Admin Portal page instead of becoming a separate route:
  - each pool tab should expose the saved preset packs relevant to that kind
  - the generate dialog should allow choosing `Default Mixer` or a saved preset pack
  - preset-pack edit/create should use compact dialogs with line-based inputs for reusable word banks
  - the preset-pack dialog should support a one-click `Generate And Save Massive Pack` action
  - the preset-pack dialog should also support `Generate, Save, And Open` so admins land directly in the pool generation modal with the new pack selected
  - when the admin leaves the name blank, the UI should auto-fill a safe default massive-pack name instead of failing the one-click flow
  - the UI should state clearly that preset packs guide candidate generation but do not guarantee million-scale uniqueness by themselves
  - the generate feedback should report how many candidates were attempted, how many were inserted, and how many were skipped as duplicates so admins can judge when a pool or preset is saturating
  - the generate dialog should keep the latest result visible inline until the pool kind or preset source changes, so the admin can compare repeated runs without depending on transient toast timing
- `Pools` in Electron should become one of:
  - read-only visibility into pool readiness, counts, list rows, and per-entry usage counts
  - batch-facing usage context
  - disabled until the shared backend content-pool service exists
- AI-assisted pool generation should be admin-driven:
  - admins generate or refine reusable presets/themes in Admin Portal
  - the backend expands those presets into validated candidate titles/openings/albums
  - uniqueness must be enforced centrally, not only by prompt text
  - repeated generate runs should use broader random template mixing so the same preset pack explores different combinations over time instead of cycling a narrow fixed pattern list
- Runtime pool consumption should avoid burning entries on failed draft attempts:
  - pool rows should first be claimed with reservation metadata
  - rows should be finalized only after a successful draft actually uses them
  - failed or cancelled attempts should release the reservation so another worker can reuse the row
  - selection should prefer least-used eligible rows instead of pure `ORDER BY random()` to spread reuse more evenly
- Admin Portal should expose reservation health after the runtime claim flow is in place:
  - summary cards should show reserved and stale-reserved counts beside total/unused/used
  - pool row tables should show whether an entry is `available`, `reserved`, or `stale`
  - row-level details should include reservation owner and timestamp when present
- Shared backend claim API should exist alongside the admin surfaces:
  - authenticated generation clients should be able to claim one pool row per kind through Platform API
  - clients should finalize only after successful downstream draft/song persistence
  - clients should release claims on cancellation or failed downstream work
  - the API contract should reuse the same reservation metadata already visible in the admin portal
- Preset-pack authoring should support one-click massive starter banks for admins:
  - the `Create Preset Pack` dialog should expose a generate action with a clear icon/button
  - one click should fill the visible preset fields for the active pool kind
  - the target is 10,000 entries per visible field so admins can quickly seed large vocab banks
  - this autofill should use deterministic built-in generation rather than pretending a single LLM call can reliably return tens of thousands of usable lines
- `Suno` should remain a user-safe settings surface only after its persistence source of truth is clarified
  - if Electron edits `/settings` while Python still uses separate local `app_settings`, parity will remain incomplete
  - the Electron tab can still safely expose shared user-safe keys such as callback URL, retries, merge defaults, and credit-planning values
- `YouTube` in the user app must never expose Google `client_id` or `client_secret`; those belong to the Admin Portal only
- Admin Portal `Settings` should host a dedicated `YouTube OAuth` tab for admin-only OAuth app management
- `YouTube` should present a normal user-facing channel flow:
  - select profile
  - connect in browser
  - wait for callback status
  - choose a returned channel if Google returns more than one
  - disconnect without exposing OAuth app details
- Use a single sticky footer save action with status text instead of repeated refresh/save buttons scattered across tabs
- Unsupported actions should stay visible in their Python-equivalent position but remain disabled or read-only instead of being replaced with new Electron-only sections

**Behavior**
- Reuse real backend contracts for:
  - profiles
  - publication defaults
  - user-safe `/settings` values, including the Python `Settings` and safe `Suno` keys
- `Preferences` should preserve the verified Python settings semantics for:
  - path keys and normalization
  - worker ranges/clamping
  - image defaults and output-resolution precedence
  - honest desktop-only actions such as browse/open path support
- `Profiles` should allow creating a new profile directly inside the Settings detail pane instead of forcing a route jump back into onboarding
- Settings dropdowns should use the shared Tailwind/shadcn visual language rather than native browser menus so Windows styling does not break the desktop theme
- The Admin Portal user detail page should expose the same saved profile metadata the Electron app writes, so admins can verify sync for profile basics, publication defaults, and media-backed assets in one place
- While a new inline draft is selected, show it as a draft state and defer YouTube/publication-only actions until after the profile is created
- Poll in-progress YouTube browser sessions so the user can return to the app and finish channel selection without manually refreshing
- Unsupported admin-only or desktop-only actions must be shown honestly as limited/read-only instead of faked
- Changes with risk should require explicit save or confirmation

### 6.14 Log Page
**Purpose**
- Runtime visibility and support diagnostics

**Layout**
- Filter bar
- Scrollable log list/table
- Copy/export/clear actions as allowed

**Behavior**
- Should support long-running desktop sessions
- Make timestamps and severity visually scan-friendly

## 7. Motion And Feedback
- Use restrained motion
- Route transitions should be subtle, not theatrical
- Important actions may use slight opacity/slide transitions
- Loading indicators must feel fast and informative rather than decorative

## 8. Accessibility And Usability
- Full keyboard navigation for forms and major controls
- Visible focus states
- Adequate contrast on all action buttons and data text
- Click targets suitable for dense desktop use
- Avoid relying on color alone for status interpretation

## 9. Design Risks
1. Overbuilding the Electron UI before backend contracts are finalized
2. Creating a generic SaaS visual language instead of a true desktop studio feel
3. Choosing a preview stack that looks modern on paper but is too brittle or slow to keep trustworthy in day-to-day desktop use
4. Regressing information density by over-simplifying workspaces
5. Letting renderer preview drift too far from Python export without surfacing that mismatch honestly

## 10. Design Decisions To Lock
1. Desktop-first only
2. Dark studio aesthetic
3. Sidebar-based main shell
4. React for all page UI
5. Renderer-owned Video preview inside the center pane
6. Startup/auth/onboarding are the first milestone before main workspace migration

## 11. Video Effect Domain UX Architecture

### 11.1 Product Goal
- The Video workspace must feel like one professional studio surface for Boss, while the underlying implementation stays split into clean effect domains:
  - Spectrum
  - Background
  - Logo
  - Particles
  - Text
  - Atmosphere/PostFX
- Editing one domain should only change that domain unless Boss explicitly uses a shared attachment or layout rule.
- Future marketplace installs must feel native:
  - browse pack
  - install
  - preview
  - apply
  - disable/remove safely

### 11.2 UX Boundaries
- The center preview remains one compositor surface, but the right-rail editing experience should be domain-oriented rather than implementation-oriented.
- Each inspector tab should read from its own editor state contract:
  - `Spectrum`
  - `Background`
  - `Logo`
  - `Particles`
  - `Text`
- Shared behavior must be explicit, never hidden:
  - `Attach Spectrum To Logo`
  - future `Particles Anchor`
  - future scene-wide color or timing automation
- When a control changes another domain by design, the UI should label that relationship directly instead of hiding it in generic settings.

### 11.3 Marketplace UX Contract
- Installed effect packs must appear as first-class catalog items, not as raw JSON or file imports.
- Every pack should expose:
  - name
  - vendor/author
  - version
  - compatible app version
  - preview thumbnail/video
  - supported domain (`spectrum`, `particles`, `background-motion`, `logo-behavior`)
  - install status
- Boss should be able to:
  - install without restarting the whole workspace when safe
  - preview a pack without rewriting unrelated template fields
  - remove or disable a pack without breaking saved projects
- When a saved template references a missing or disabled pack, the UI must show an honest warning and a safe fallback choice.
- Current implementation status:
  - this contract is now live in the video workspace inspectors and the shared effect-pack registry/runtime seams
  - full validation still depends on ongoing desktop QA, but the renderer/test contract is implemented and verified

### 11.4 Design Rules For Isolation
- Domain settings panels must never act like one hidden mega-form.
- Local draft state should remain scoped:
  - Spectrum edits stay in the Spectrum editor/session
  - Background edits stay in the Background editor/session
  - Logo edits stay in the Logo editor/session
  - Particle edits stay in the Particle editor/session
- Save/discard actions can remain unified visually, but the implementation should track dirty state per domain.
- Preset application must stay domain-scoped:
  - applying a spectrum style cannot silently rewrite logo or particle behavior
  - applying a particle effect cannot silently alter spectrum or background motion

### 11.5 Visual Consistency Requirements
- A pack marketplace should still preserve CAMXORA visual discipline:
  - compact desktop density
  - honest status labels
  - no fake previews
  - clear compatibility warnings
  - deterministic install/apply behavior
- Marketplace content should inherit the same workstation language as the rest of the app instead of looking like a separate storefront.

### 11.6 Video Template Delete Contract
- The Video left rail may expose `Delete` only when it maps to a real template-removal workflow.
- Deleting a template must require explicit confirmation and explain that the action cannot be undone.
- After deletion, the workspace should fall back to the next available template automatically instead of leaving the Video page in a broken selected-template state.

### 11.7 Video Runtime Improvement Rules
- The next Video renderer phases should prefer runtime and architecture improvements over new inspector/UI surface area.
- Avoid adding new operator-facing copy, helper text, or diagnostics unless a runtime capability cannot be controlled or verified without it.
- Frame-critical visual work should move toward GPU ownership wherever the platform allows:
  - spectrum shaping
  - peak-hold
  - particle simulation
  - motion blur / post-fx
- Audio reactivity should target professional timing and stability, using a richer analyzed feature timeline instead of relying only on live analyser heuristics.
- Preview and export should converge toward one render truth; the operator should eventually be able to trust the live preview as the exact final look.
