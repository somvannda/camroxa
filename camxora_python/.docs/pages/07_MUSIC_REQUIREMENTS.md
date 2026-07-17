# Music Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-07-MUSIC  
> **Version:** 1.0.0  
> **Status:** Approved for implementation  
> **Phase:** 7  
> **Source of truth:** `camxora/src/renderer/src/features/music/MusicWorkspacePage.tsx`  
> **Supporting sources:** `useMusicWorkspaceQuery.ts`, `useBatchStatusQuery.ts`, `DesktopMusicDownloadCoordinator.tsx`, `MusicWorkspacePage.test.tsx`, `camxora/docs/music-generate-flow.md`  
> **Target:** `camxora_python/features/music/`  
> **Last updated:** 2026-07-07

---

# 1. Document purpose

Complete A→Z requirements for the **Music workspace page** — batch composer, song editor, channel pairing, automation toggles, credit planning, and history table. Must match **100% functional parity** with Electron.

**UI rule (project standard):** Native PySide6 widgets + `shared/themes/deep_blue.py` QSS only. Use `account_card`, `StatCard` where cards are needed, standard `QDateEdit`, `QComboBox`, `QCheckBox`, `QPushButton`, `QSlider`, `QLineEdit`, `QTextEdit`, `data_table`. **No custom workflow-style panels or bespoke QSS blocks.**

**Build rule:** Do not mark Music complete until every item in **§15 Definition of Done** is checked.

---

# 2. Overview

## 2.1 What Music is

The Music page (`/app/music`) is the **batch composer and song editor** for the Camxora pipeline. Users configure generation defaults, draft/polish lyrics, select primary/secondary channel pairs, set automation flags, and click **Generate** to create one batch per planned day × channel pair.

## 2.2 What Music is not

- Not the operational recovery table (that's **Progress**)
- Not the visual lane board (that's **Workflow**)
- Not the image job editor (**Image** phase)
- Not the video export workspace (**Video** phase)

## 2.3 Shell-level companion (same phase)

Electron mounts `DesktopMusicDownloadCoordinator` in `AppShellLayout.tsx` — a **background service**, not visible UI. It polls pending Suno MP3 downloads and saves them locally, then syncs completion back to `platform_api`.

Python must implement an equivalent **app-shell background coordinator** (not embedded in the Music page view).

---

# 3. Entry points & navigation

| Property | Value |
|----------|-------|
| Path | `/app/music` |
| Sidebar key | `music` |
| Label | Music |
| Title | Music |
| Eyebrow | Workspace |
| Description | Music workspace with batch composer, automation strip, song editor, and history. |

**Router:** Replace `PlaceholderPage` for `music` in `app/router.py` with `MusicView`.

---

# 4. Data requirements

## 4.1 Workspace bootstrap (parallel fetch on page activate)

| # | Method | Path | Purpose |
|---|--------|------|---------|
| D-1 | GET | `/users/me` | Account context (optional display) |
| D-2 | GET | `/profiles` | Primary/secondary channel lists |
| D-3 | GET | `/settings` | Music defaults + `imageSourceMode` + output dirs |
| D-4 | GET | `/prompts/descriptions/public` | Description dropdown options |
| D-5 | GET | `/prompts/structures/public` | Structure dropdown options |
| D-6 | GET | `/music/history?limit=8` | History batches + songs |
| D-7 | GET | `/credits/operation-costs` | Draft/Polish/Suno/Image credit labels |

**Python:** Single `MusicWorkspaceWorker` returning `MusicWorkspacePayload` dataclass. Operation costs fetch may fail gracefully → empty list (Electron `.catch(() => ({ items: [] }))`).

## 4.2 Mutations

| # | Method | Path | Trigger |
|---|--------|------|---------|
| M-1 | PATCH | `/settings` | Debounced music settings autosave (400ms) |
| M-2 | POST | `/content-pools/{kind}/claim` | Draft generation — claim title/album/opening seeds |
| M-3 | POST | `/content-pools/{kind}/finalize` | Draft success — finalize claimed seeds |
| M-4 | POST | `/content-pools/{kind}/release` | Draft failure — release claimed seeds |
| M-5 | POST | `/generation/draft` | **Draft** button |
| M-6 | POST | `/generation/polish-lyrics` | **Polish** button |
| M-7 | POST | `/batches` | **Generate** button (one call per planned day × pair) |
| M-8 | GET | `/batches/{batch_id}` | Poll latest batch status after Generate |

## 4.3 Background download coordinator (shell-level)

| # | Method | Path | Purpose |
|---|--------|------|---------|
| B-1 | GET | `/music/downloads/pending?limit=24` | Poll pending Suno MP3 tasks |
| B-2 | POST | `/music/downloads/sync` | Report downloaded primary/secondary files |

**Poll interval:** 4s when pending items exist, 12s when empty (Electron `DesktopMusicDownloadCoordinator`).

---

# 5. Layout structure (standard theme)

```text
[ Error banner — workspace mutation/load failures ]

[ Loading card — "Loading music workspace..." ]

[ Top settings strip — account_card OR plain toolbar row ]
    From | To | Language | Creativity slider | Unique opening | Strict | History | Count | planned-days chip

[ Main grid — 4 columns on wide screens, stacked on narrow ]
    [ Song card — account_card ]
        Header: Song + Draft/Polish buttons
        Effect preview row: Valence, Danceability, Instrumental bars + Polish slider
        Title + Album inputs
        Draft pool seed notice (when present)
        Copy title | Copy lyrics | Copy both | Polish | Revisions (disabled)
        Lyrics textarea

    [ Primary channels card — account_card ]
        Scrollable profile toggle list with selection order numbers

    [ Secondary channels card — account_card ]
        Same as primary

    [ Automation card — account_card ]
        Description + Structure dropdowns
        Auto-Gen Image | Auto-GSuno | Auto-Video | Auto Merge | Auto Reel | Auto-Upload (disabled)
        Automation info subtitle
        Save status + batch status + operation cost lines + plan breakdown
        Generate button + planned batch helper text
        Validation warnings (pair count mismatch, overlap)

[ History card — account_card + data_table ]
    Filters: From | To | Last batch | Show all
    Summary + updated timestamp
    Table: No, Album, Title, Description, Structure, Primary Channel, Secondary Channel, Suno, Generated
    Row click → load song into composer
    Folder buttons on OK/ALT channel columns
```

**Column ratio target:** Song ~1.5fr, Primary ~0.75fr, Secondary ~0.75fr, Automation ~0.95fr (approximate with Qt stretch factors).

---

# 6. State model

## 6.1 ComposerState

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `from_date` | `str` (YYYY-MM-DD) | today | Batch date range start |
| `to_date` | `str` (YYYY-MM-DD) | today | Batch date range end |
| `primary_profile_ids` | `list[str]` | auto first profile | Ordered selection |
| `secondary_profile_ids` | `list[str]` | auto second profile | Ordered selection |
| `description` | `str` | from selected prompt | Synced from description dropdown |
| `structure` | `str` | from selected prompt | Synced from structure dropdown |
| `title` | `str` | `""` | Editable |
| `album` | `str` | `""` | Editable |
| `lyrics` | `str` | `""` | Editable |

## 6.2 MusicSettingsState (persisted via PATCH /settings)

| UI field | Settings key | Default | Range |
|----------|--------------|---------|-------|
| Language | `language` | `en` | en, km, de, es, fr |
| Creativity | `creativity` | 55 | 0–100 |
| Unique opening | `uniqueOpening` | false | bool |
| Strict | `strictLevel` | 3 | 1–5 |
| History | `uniquenessHistoryWindow` | 100 | 50, 100, 200, 500, 1500 |
| Count | `defaultSongCount` | 4 | 1–50 |
| Auto-Gen Image | `autoGenImage` | false | bool |
| Auto-GSuno | `autoGSuno` | false | bool |
| Auto-Video | `autoVideoAfterSuno` | false | bool |
| Auto Merge | `autoMergeAfterVideo` | false | bool |
| Auto Reel | `autoReelAfterVideo` | false | bool |
| Auto-Upload | `autoUploadYouTube` | false | bool (UI disabled) |
| Polish strength | `lyricsPolishStrength` | 60 | 0–100 |

**Autosave:** 400ms debounce after any music setting change. Skip until initial settings loaded from API.

## 6.3 Other UI state

| State | Purpose |
|-------|---------|
| `selected_description_id` | Description dropdown value |
| `selected_structure_id` | Structure dropdown value |
| `selected_history_song_id` | Highlighted history row |
| `draft_pool_seeds` | Show seed notice after successful Draft |
| `latest_batch_id` | Poll batch status after Generate |
| `latest_batch_summary` | User-facing batch creation summary |
| `history_filters` | `{ from_date, to_date, last_batch_only }` |
| `workspace_error` | Inline error message |
| `save_status` | idle \| saving \| saved \| error |

---

# 7. Functional requirements

## FR-1 — Workspace load & error states

| ID | Requirement |
|----|-------------|
| FR-1.1 | On `activate_page()`, fetch workspace payload via background worker |
| FR-1.2 | Loading: show *"Loading music workspace..."* in `account_card` |
| FR-1.3 | Load error: rose-style error banner — *"Unable to load the music workspace from the current backend contracts."* |
| FR-1.4 | Initialize music settings from API once; set persisted snapshot to prevent immediate re-save |
| FR-1.5 | Auto-select first description/structure option when none selected |
| FR-1.6 | Sanitize profile selections when profiles load (fallback to first + second profile) |

## FR-2 — Top settings strip

| ID | Requirement |
|----|-------------|
| FR-2.1 | From/To date pickers bound to composer date range |
| FR-2.2 | Language dropdown: English, Khmer, German, Spanish, French |
| FR-2.3 | Creativity slider 0–100 with live numeric label |
| FR-2.4 | Unique opening checkbox |
| FR-2.5 | Strict dropdown 1–5 |
| FR-2.6 | History window dropdown 50/100/200/500/1500 |
| FR-2.7 | Song count spinbox/input 1–50 |
| FR-2.8 | Planned days chip: *"{n} planned day(s)"* or invalid range message |
| FR-2.9 | Invalid range (to < from): chip shows error tone; Generate disabled |

## FR-3 — Song editor card

| ID | Requirement |
|----|-------------|
| FR-3.1 | **Draft** button disabled when description empty or pending |
| FR-3.2 | **Polish** button disabled when lyrics empty or pending |
| FR-3.3 | Draft credit label from `lyric` operation cost |
| FR-3.4 | Effect preview bars derived from creativity (valence, danceability, instrumentalness formulas — port `effectPreviewFromCreativity`) |
| FR-3.5 | Polish strength slider in effect row |
| FR-3.6 | Title, album, lyrics fields editable |
| FR-3.7 | Draft pool seed notice after successful draft |
| FR-3.8 | Copy title / Copy lyrics / Copy both → system clipboard |
| FR-3.9 | **Revisions** button always disabled, shows 0 credits |
| FR-3.10 | Duplicate Polish button in action row (Electron parity) |

## FR-4 — Draft generation flow

| ID | Requirement |
|----|-------------|
| FR-4.1 | Build avoid lists from history (`buildHistoryAvoidLists`) using history window |
| FR-4.2 | Claim content pool items: titles, albums, openings (openings only if unique opening enabled) |
| FR-4.3 | Build draft description with inspiration suffix from pool seeds |
| FR-4.4 | POST `/generation/draft` with full payload |
| FR-4.5 | On success: finalize all claimed seeds; populate title/album/lyrics; store pool seeds |
| FR-4.6 | On failure: release all claimed seeds; show workspace error |
| FR-4.7 | Reservation token: UUID or fallback `pool-{timestamp}-{random}` |

## FR-5 — Polish lyrics flow

| ID | Requirement |
|----|-------------|
| FR-5.1 | POST `/generation/polish-lyrics` with lyrics + polish strength + primary profile id |
| FR-5.2 | On success: replace composer lyrics |
| FR-5.3 | On failure: show workspace error |

## FR-6 — Channel selection

| ID | Requirement |
|----|-------------|
| FR-6.1 | Primary and Secondary columns list all profiles |
| FR-6.2 | Click toggles selection; show 1-based order index when selected |
| FR-6.3 | Empty profiles: *"No profiles available yet."* |
| FR-6.4 | Selection order preserved for batch pairing by index |

## FR-7 — Automation card

| ID | Requirement |
|----|-------------|
| FR-7.1 | Description + Structure dropdowns sync composer text fields |
| FR-7.2 | Six automation toggles; Auto-Upload disabled |
| FR-7.3 | Info text about active pipeline automation scope |
| FR-7.4 | Save status messages: saving / saved / error / ready |
| FR-7.5 | Batch status line: latest summary + polled batch status |
| FR-7.6 | Operation cost labels: Draft, Polish, Revisions (0), Suno, Image |
| FR-7.7 | Plan breakdown: days × pairs × songs = song jobs |
| FR-7.8 | Draft/Suno/Image/Batch total credit lines |
| FR-7.9 | Generate button label: `Generate ({n} Credits)` or `Generate` when unavailable |
| FR-7.10 | Generate disabled when: pending, no profiles, pair count mismatch, overlap, invalid dates |
| FR-7.11 | Warning when primary/secondary counts differ |
| FR-7.12 | Warning when same profile selected on both sides |

## FR-8 — Generate (batch creation) flow

| ID | Requirement |
|----|-------------|
| FR-8.1 | Expand to `planned_run_dates × primary_pairs` batch calls |
| FR-8.2 | Each payload: ok/alt profile ids, description/structure ids, automation flags, song count, language, creativity, pairing_mode=`match_key`, from_date=to_date=run date |
| FR-8.3 | **Manual image mode:** plan run directories via `planManualAssetRunDirectories`, pass `ok_run_dir`/`alt_run_dir`, create folders after response |
| FR-8.4 | Manual base dir: `sunoOutputDir` or fallback `downloadsDir` from settings |
| FR-8.5 | On success: set latest batch id, summary message, refresh workspace |
| FR-8.6 | On failure: show workspace error |
| FR-8.7 | Summary example: *"Created 3 batch runs across 3 planned days and 1 channel pair."* |

## FR-9 — Credit calculation (must match Electron tests)

Port exactly:
- `getProfileImageJobCount` — bg_only/thumb_only=1, else 2
- `getMusicPlanCostBreakdown`
- `getBatchGenerateTotalCost`
- `formatOperationCostLabel` / `formatButtonCreditLabel`

**Verified test scenarios from `MusicWorkspacePage.test.tsx`:**

| Scenario | Expected Generate label |
|----------|-------------------------|
| Default (1 day, 1 pair, 4 songs, draft only) | 12 credits |
| Auto-Gen Image on | 92 credits |
| Auto-GSuno on | 40 credits |
| Auto-GSuno + 3 days | 120 credits, 3 batch API calls |
| Image costs excluded when `imageSourceMode=manual` | Image total 0 |

## FR-10 — Batch status polling

| ID | Requirement |
|----|-------------|
| FR-10.1 | After Generate, poll `GET /batches/{id}` every 2.5s while page active |
| FR-10.2 | Display status in automation card batch status line |
| FR-10.3 | Stop polling when batch id cleared or page deactivated |

## FR-11 — History table

| ID | Requirement |
|----|-------------|
| FR-11.1 | Flatten batches → songs with row numbers |
| FR-11.2 | Filter by from/to dates and "Last batch only" (first batch in list) |
| FR-11.3 | Columns: No, Album, Title (+ batch index/id subline), Description, Structure, Primary (+ folder btn), Secondary (+ folder btn), Suno status, Generated |
| FR-11.4 | Row click loads title/album/lyrics + description/structure ids into composer |
| FR-11.5 | Row click clears draft pool seeds |
| FR-11.6 | Open folder buttons call `ensure_directory` + `open_path`; error if path missing |
| FR-11.7 | Empty filtered result: *"No history rows match the current filters."* |
| FR-11.8 | Show history summary + updated timestamp from API |

## FR-12 — Settings autosave

| ID | Requirement |
|----|-------------|
| FR-12.1 | Debounce 400ms on music settings changes |
| FR-12.2 | PATCH mapped keys via `buildMusicSettingsPatch` |
| FR-12.3 | Saved state resets to idle after 1.8s |
| FR-12.4 | Do not autosave until initial API settings applied |

---

# 8. Desktop / native services

## FR-13 — Manual run directory planning

Port `planManualAssetRunDirectories` from `manualAssetPaths.ts` to `shared/lib/manual_asset_paths.py`.

Inputs: base dir, ok profile, alt profile, run label (date), existing ok/alt directory entry names.

Outputs: `ok_run_dir`, `alt_run_dir`, `run_folder_name`.

## FR-14 — Desktop music download coordinator (shell-level)

| ID | Requirement |
|----|-------------|
| FR-14.1 | Start when app shell loads authenticated session |
| FR-14.2 | Poll pending downloads (limit 24) |
| FR-14.3 | For each pending item with URL + output_dir + target_path + not downloaded: download MP3 locally |
| FR-14.4 | POST sync with downloaded primary/secondary flags |
| FR-14.5 | Invalidate/refetch progress + music workspace data after sync |
| FR-14.6 | Single-flight guard — no overlapping download runs |

**Implementation note:** Port or reuse download logic from `python_app` if available; use `httpx` + local file write. Mount coordinator in `app/application.py` or equivalent shell root, not inside `MusicView`.

## FR-15 — Clipboard

Use `QApplication.clipboard()` for copy title/lyrics/both actions.

---

# 9. Library ports required

| Python module | Electron source |
|---------------|-----------------|
| `shared/lib/music_settings.py` | `buildMusicSettingsState`, `buildMusicSettingsPatch`, setting readers |
| `shared/lib/music_composer.py` | Date span helpers, history filters, avoid lists, profile sanitization |
| `shared/lib/music_costs.py` | Cost breakdown + button label formatters |
| `shared/lib/manual_asset_paths.py` | Add `plan_manual_asset_run_directories` |
| `shared/lib/formatting.py` | Add `format_datetime_label` if not present |

---

# 10. API & model additions (Python)

Extend `shared/models/platform.py`:

- `PromptNameOption`, `MusicHistorySong`, `MusicHistoryBatch`, `MusicHistoryListResponse`
- `DraftGenerationRequest/Response`, `LyricsPolishRequest/Response`
- `BatchCreateRequest/Response`, `BatchStatusResponse`
- `OperationCostResponse`, `OperationCostsResponse`
- `ClaimContentPoolRequest/Response`, `ClaimedContentPoolItem`, `ReservationActionRequest/Response`
- `MusicDownloadSyncItem`, `MusicDownloadSyncResponse`

Extend `shared/services/platform_api.py` with all endpoints from §4.

Extend `shared/workers/data_workers.py`:

- `MusicWorkspaceWorker`
- `DraftGenerationWorker` (or inline mutation workers)
- `PolishLyricsWorker`
- `CreateBatchWorker` (sequential multi-batch)
- `BatchStatusWorker` / timer-driven poll
- `MusicDownloadCoordinator` (shell service, not QThread page worker)

---

# 11. Test requirements

## Unit tests (pure logic)

| Test file | Covers |
|-----------|--------|
| `tests/test_music_settings.py` | Settings read/build/patch, language normalize |
| `tests/test_music_composer.py` | Date span, history filters, avoid lists, profile sanitize |
| `tests/test_music_costs.py` | All Electron test scenarios for credit totals |
| `tests/test_manual_asset_paths.py` | `plan_manual_asset_run_directories` |

## View smoke tests

| Test | Covers |
|------|--------|
| Loading state | Shows loading message |
| Load error | Error banner visible |
| Invalid date range | Generate disabled, invalid chip text |
| Success bind | History table populated, cost labels visible |
| Draft flow | Mock API — pool claim/finalize, composer populated |
| Generate scaling | 3-day range → 3 batch calls |
| Auto image / Auto-GSuno | Generate credit label updates |

Mirror assertions from `MusicWorkspacePage.test.tsx`.

---

# 12. Out of scope / deferred

| Item | Reason |
|------|--------|
| Auto-Upload YouTube | Electron UI disabled; enable only after E2E QA |
| Revisions button | Electron disabled placeholder |
| Pixel-perfect CSS clone | Native Qt layout acceptable |
| Video/merge automation execution | Settings saved here; runtime owned by Video/Automation phases |
| Content pool admin UI | Not on Music page |

---

# 13. Dependencies on other phases

| Dependency | Needed for |
|------------|------------|
| Profile page (done) | Profile list shape |
| Settings API (partial) | `get_settings` / `patch_settings` — extend for music keys |
| Progress page (done) | Download sync invalidates progress rows |
| Video phase (future) | Auto-Video/Merge/Reel runtime; workspace state for downstream |

---

# 14. Python module plan

```text
features/music/
  views/
    music_view.py              # Main page orchestrator
  widgets/
    settings_strip.py          # Top date/language/creativity strip
    song_editor_card.py        # Draft/polish/lyrics/effects
    channel_selection_card.py  # Primary or secondary profile list
    automation_card.py         # Toggles, costs, generate button
    history_card.py            # Filters + table
    error_banner.py            # Workspace errors

shared/
  lib/music_settings.py
  lib/music_composer.py
  lib/music_costs.py
  services/music_download_coordinator.py   # Shell-level background service
  workers/data_workers.py                  # Music workers appended
```

---

# 15. Definition of Done

### Requirements & API
- [ ] M-1 Requirements doc reviewed and indexed
- [ ] M-2 All §4 API methods implemented in `PlatformApi`
- [ ] M-3 All §9 lib ports with unit tests

### UI (standard theme)
- [ ] M-4 Top settings strip complete
- [ ] M-5 Song editor card complete (draft, polish, copy, effects)
- [ ] M-6 Primary + secondary channel cards complete
- [ ] M-7 Automation card complete (toggles, costs, generate)
- [ ] M-8 History card complete (filters, table, row select, open folder)

### Flows
- [ ] M-9 Draft flow with content pool claim/finalize/release
- [ ] M-10 Polish flow
- [ ] M-11 Generate flow (multi-day × multi-pair, manual run dirs)
- [ ] M-12 Settings autosave debounce
- [ ] M-13 Batch status polling after generate

### Shell service
- [ ] M-14 Desktop music download coordinator running in app shell

### Tests & docs
- [ ] M-15 All §11 tests passing
- [ ] M-16 `02_IMPLEMENTATION_STATUS.md` updated
- [ ] M-17 Manual verify against live `platform_api` (P-10 equivalent)

---

# 16. Reference — Electron test acceptance matrix

Copy these exact expectations into Python tests:

1. Inverted date range → Generate disabled + invalid range message  
2. History table shows all 9 column headers + sample row data  
3. Cost labels: Draft 3, Polish 3, Revisions 0, Suno 7, Image 5  
4. Plan line: `1 day x 1 pair x 4 songs = 4 song jobs`  
5. Default batch total: 12 credits  
6. Auto-Gen Image → Generate 92 credits, image total 80  
7. Auto-GSuno → Generate 40 credits, suno total 28  
8. 3-day + Auto-GSuno → Generate 120 credits, 3× `create_batch` calls with correct dates  
9. Draft → pool inspiration in description + seed notice banner  
10. Auto-Upload button disabled; Auto-Video/Merge/Reel enabled  

---

# 17. Related docs

- [`../02_IMPLEMENTATION_STATUS.md`](../02_IMPLEMENTATION_STATUS.md)
- [`00_PAGE_BY_PAGE_STRATEGY.md`](00_PAGE_BY_PAGE_STRATEGY.md)
- [`06_PROGRESS_REQUIREMENTS.md`](06_PROGRESS_REQUIREMENTS.md)
- Electron flow reference: `camxora/docs/music-generate-flow.md`
