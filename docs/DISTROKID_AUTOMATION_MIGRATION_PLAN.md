# DistroKid Auto-Upload Migration Plan (AutoDistroKid → camxora_python)

**Date:** 2026-07-27  
**Status:** draft — awaiting agreement before implementation  
**Source project:** `D:\Development\Projects\AutoDistroKid`  
**Target:** `camxora_python` DistroKid feature (already scaffolded: sidebar, Music checkbox, `$5/mo` entitlement)

---

## 1. Goal

Migrate **only DistroKid auto-upload automation** from AutoDistroKid into CAMXORA desktop (`camxora_python`), so that:

1. User has DistroKid add-on entitlement (`distrokid_active`).
2. Music page **DistroKid** checkbox is on (or DistroKid page starts uploads).
3. After the studio pipeline reaches DistroKid (see §8.1), CAMXORA downloads Suno `.wav` files to the desktop/run folder (with retries), opens DistroKid in a persistent browser for login if needed, then uploads album name, track titles, WAVs, and **thumbnail image** as cover.
4. Duplicate album/title/WAV fingerprints are checked against platform_api history; user is alerted and blocked from silent reupload.

**Out of scope (do not migrate):**

| Area | Paths / modules | Why |
|------|-----------------|-----|
| Audio enhancement | `src/audio/enhancer.py`, `maximizer.py`, `optimizer.py`, `processing_chain.py`, `stem_*`, `multiband_eq.py`, `stereo_imager.py`, `lufs_meter.py`, `mastering_engine.py` | Explicitly excluded |
| AI / Demucs / CREPE | `ai_analyzer.py`, `ai_pipeline.py`, `demucs_engine.py`, `crepe_engine.py`, `model_manager.py` | Explicitly excluded |
| Local MP3 → WAV convert | `src/audio/converter.py` (and any pydub/ffmpeg format convert for DistroKid) | Explicitly excluded — **always obtain WAV from Suno** (`suno/wav` convert + download), with retries; never fall back to local convert or raw MP3 upload |
| AutoTune UI | `ui/autotune_tab.py`, `autotune_worker.py`, `eq_widget.py`, `maximizer_widget.py`, `stereo_imager_widget.py`, `waveform_widget.py` (enhancement), `settings_bridge.py`, `model_status_*` | Enhancement-only |
| Audio/optimizer config | `AudioSettings`, `OptimizerSettings`, Settings Audio/Optimizer tabs | Not needed for DistroKid |
| Raw MP3 DistroKid upload | `upload_settings.raw_mp3_upload` | WAV-only policy |

---

## 2. How AutoDistroKid works today (upload only)

### 2.1 High-level architecture

```text
DirectoryPanel / loaded folders
        │
        ▼
core/scanner.py  →  Album + Track models
        │
        ▼
UploadHandler.upload_albums / upload_album
        │
        ├─ BrowserAutomation.launch()   (Playwright persistent profile)
        ├─ DistroKidAutomation.login()  (Google Sign-In + session reuse)
        ├─ DistroKidAutomation.navigate_to_upload()
        ├─ FormAutomator.automate_questionnaire(album)
        │       ├─ ElementResolver (multi-strategy DOM find)
        │       └─ TrackUploader.upload_track(...) per track
        ├─ DistroKidAutomation.submit_upload()   (if auto_submit)
        └─ UploadHistory.record_success(...)
```

### 2.2 Auth model (important)

- **No stored DistroKid password / no keyring in the upload path.**
- First run: user completes **Google Sign-In + 2FA** manually in a Playwright window.
- Session persists under `~/.autodistrokid/browser_profile` via `launch_persistent_context`.
- Later runs: detect “already logged in” by URL / dashboard / upload-page reachability.

### 2.3 End-to-end upload sequence

1. Scan folders → albums/tracks + optional cover art.
2. Reject albums with **duplicate track titles**.
3. Launch browser (Chrome → Edge → Playwright Chromium).
4. Login / restore session.
5. Navigate to DistroKid new-release upload page (`/new/`).
6. Disable Social Media Pack auto-modal via JS override.
7. Dismiss cookie banner if present.
8. Fill questionnaire sections (see §3).
9. Upload artwork (optional crop/resize to square).
10. Upload each track file + per-track answers.
11. Fill Apple Music / producer credits (copy-to-all).
12. Tick mandatory checkboxes.
13. If `auto_submit`: click continue, wait for processing, choose **“Use my originals”** on Mixea/Enhance page, wait for `/new/done/`.
14. Record success in local upload history; optional delay before next album.

---

## 3. DistroKid form logic (what gets filled)

### 3.1 Album / release sections (`FormAutomator`)

| Step | Method | Behavior |
|------|--------|----------|
| Song count | `_select_song_count` | `#howManySongsOnThisAlbum` — `"1 song (a single)"` or `"{N} songs"` |
| Social Media Pack | JS override + `_dismiss_social_media_pack` | Force unchecked; dismiss modal |
| Previously released | `_answer_previously_released` | From `UploadFormConfig.previously_released` |
| Upgrade prompt | `_dismiss_upgrade_prompt` | Click “No thanks” if shown |
| Instagram | `_answer_instagram` | From `artist_on_instagram` |
| Facebook | `_answer_facebook` | From `artist_on_facebook` |
| Release date | `_set_release_date` | Only if `release_date_mode == "custom"` |
| Language | `_select_language` | `#language` |
| Genre | `_select_genre` | Primary / subgenre / optional secondary; case-insensitive + partial match |
| Artwork | `_upload_artwork` / `_prepare_artwork` | File input; optional PIL square resize (~3000×3000) |
| Album title | `_fill_album_title` | **Skipped for singles** (1 track) |
| Tracks | `_upload_tracks` → `TrackUploader` | Per track |
| Apple Music credits | `_fill_apple_music_credits` | Role listbox + name + copy-to-all |
| Producer credits | `_fill_producer_credits` | Same pattern |
| Extras | `_handle_extras_section` | Leave optional extras unchecked |
| Mandatory | `_handle_mandatory_checkboxes` | Check all visible `input.areyousure` |

### 3.2 Per-track sections (`TrackUploader`)

| Step | Method | Default / config |
|------|--------|------------------|
| Upload file | `_upload_audio_file` | `#js-track-upload-N` → `input.trackupload_N` → generic audio input |
| Track title | `_set_track_name` | From track title / filename cleanup |
| Featured artist | `_answer_featured_artist` | “No, don't show any other artists” |
| Version | `_answer_version_info` | “No, this is the normal version” |
| Dolby Atmos | `_answer_dolby_atmos` | “No” |
| Songwriter | `_answer_songwriter_question` + `_fill_songwriter_details` | “I wrote this song” + first/last/role + copy-to-all |
| Explicit | `_answer_explicit_lyrics` | `explicit_lyrics` |
| Radio edit | `_answer_radio_edit` | `radio_edit` |
| Instrumental | `_answer_instrumental` | `instrumental` (config default often `true`) |
| AI generated | `_answer_ai_generated` | `ai_generated` (config default often `true`) |
| Preview clip | `_set_preview_clip` | e.g. “Let streaming services decide” |

### 3.3 Submit (`DistroKidAutomation.submit_upload`)

1. Click done / continue (`#doneButton` and fallbacks).
2. Wait for server-side upload processing.
3. Handle SweetAlert validation popups.
4. On Mixea / Enhance page: select **Use my originals** (do not use DistroKid enhancement).
5. Wait for success URL containing `/new/done/`.

---

## 4. Module inventory (migrate / adapt / skip)

### 4.1 Core automation — **MIGRATE** (high priority)

| Source module | Classes / functions | Role in CAMXORA |
|---------------|---------------------|-----------------|
| `automation/browser.py` | `BrowserAutomation`, `BrowserError`, `launch`, navigate/click/fill/upload helpers, `_detect_browser_channel` | Persistent Playwright browser service |
| `automation/element_resolver.py` | `ElementResolver`, `ElementNotFoundError`, resolve strategies | Robust DOM lookup |
| `automation/form_automator.py` | `FormAutomator`, `FormProgress`, `SessionExpiredError`, `PageLoadError`, all `_select_*` / `_answer_*` / `_fill_*` / `_upload_*` / `_handle_*`, `_with_retry` | Questionnaire engine |
| `automation/track_uploader.py` | `TrackUploader` + all per-track methods | Track file + metadata |
| `automation/report.py` | `AutomationIssue`, `AutomationReport`, `AutomationReporter` | Diagnostics JSON per run |
| `automation/distrokid.py` | URLs/SELECTORS, exceptions, `login`, `navigate_to_upload`, `submit_upload`, success helpers | DistroKid session + submit |

### 4.2 Orchestration / models / ingest — **ADAPT**

| Source module | What to keep | How to adapt |
|---------------|--------------|--------------|
| `automation/upload_handler.py` | `upload_albums`, `upload_album`, callbacks, delays, duplicate-title guard | Strip `convert_albums` / enhancement pipeline; wire CAMXORA entitlement + music settings |
| `core/models.py` | `Track`, `Album`, statuses | Map onto CAMXORA run-dir / album / song models where possible |
| `core/config.py` | `UploadSettings`, `CleanupSettings`, `UploadFormConfig`, `CreditEntry`, `GenreSettings` | Store in CAMXORA settings / DistroKid page (not AutoDistroKid `config.json`) |
| `core/scanner.py` | `scan_*`, `clean_*`, `find_thumbnail`, `validate_album_directory`, duplicate detection | Prefer scanning CAMXORA channel run folders (`downloads/suno/...`) |
| `core/history.py` | `UploadHistory` semantics | Prefer local + optional platform history; avoid only `~/.autodistrokid` |
| `core/file_ops.py` | WAV path helpers / cleanup | Use CAMXORA paths + DistroKid WAV quota (Suno-downloaded WAVs only) |

### 4.3 UI — **ADAPT / rewrite into CAMXORA design system**

| Source | Migrate idea | Target in CAMXORA |
|--------|--------------|-------------------|
| DistroKid form settings tab | Questionnaire defaults editor | DistroKid page + Settings section |
| Account tab (Google Sign-In instructions) | Login helper copy | DistroKid page “Connect DistroKid” |
| Upload tab (`auto_submit`, delete WAV, keep browser open) | Same toggles (no `raw_mp3_upload`) | DistroKid settings |
| Directory / album list | Optional album picker | Prefer Music History / run-dir selection |
| History tab | Uploaded albums list | DistroKid page history |
| Main window worker | Background QThread | CAMXORA worker pattern (`_ui_invoke`, daemon threads) |

### 4.4 Explicitly **SKIP**

- Entire `src/audio/` including `converter.py` (no local MP3→WAV).
- `settings_bridge.py`, AutoTune / EQ / maximizer / imager widgets.
- Legacy `DistroKidAutomation.upload_album` / `upload_track` older paths superseded by FormAutomator + TrackUploader.
- `logout()` stub.
- Audio/optimizer settings tabs and config sections.
- `raw_mp3_upload` and any DistroKid upload path that accepts MP3.

---

## 5. Detailed function catalogue (upload-critical)

### 5.1 `BrowserAutomation` (`browser.py`)

| Function | Inputs | Outputs / effects |
|----------|--------|-------------------|
| `__init__(headless, profile_dir)` | flags, profile path | Holds Playwright context |
| `launch()` | — | Persistent context; Chrome→Edge→Chromium; spoof `navigator.webdriver` |
| `_detect_browser_channel()` | — | Installed browser path |
| `navigate / click / fill / type_text / select_option` | selectors, values | DOM actions |
| `upload_file(s)` | selector, path(s) | Set file input |
| `is_visible / wait_for_selector / evaluate / screenshot` | — | Probe / debug |
| `close()` | — | Tear down browser |

### 5.2 `ElementResolver` (`element_resolver.py`)

| Function | Purpose |
|----------|---------|
| `resolve(...)` | Multi-strategy find (exact text, label, ARIA, near text, CSS, partial) |
| `resolve_radio_option(question, option)` | Radio by question + option text |
| `resolve_checkbox(label)` | Checkbox by label |
| `resolve_dropdown(label)` | Select by label |
| `resolve_file_input(accept_type)` | File input by accept hint |
| `wait_for_section(section_text)` | Wait until section text appears |
| `_try_*` helpers | Individual strategies |

### 5.3 `FormAutomator` (`form_automator.py`)

| Function | Purpose |
|----------|---------|
| `automate_questionnaire(album)` | Full ordered questionnaire |
| `_run_section(name, fn)` | Progress + error capture wrapper |
| `_with_retry(name, fn)` | Exponential backoff (`retry_count`) |
| `_check_page_state()` | Detect login redirect → `SessionExpiredError` |
| Section methods | See §3.1 |
| `_click_swal_confirm()` | Confirm SweetAlert dialogs |

### 5.4 `TrackUploader` (`track_uploader.py`)

| Function | Purpose |
|----------|---------|
| `upload_track(track, index)` | Orchestrate one track |
| `_upload_audio_file` | File input with stuck/hidden recovery + `change` event |
| Per-track answer methods | See §3.2 |

### 5.5 `DistroKidAutomation` (`distrokid.py`) — keep these

| Function | Purpose |
|----------|---------|
| `login()` | Session restore or manual Google Sign-In wait (≤10 min) |
| `_check_login_success()` | URL + element heuristics |
| `navigate_to_upload()` | Go to `/new/`, retry if redirected |
| `submit_upload()` | Submit + Mixea “use originals” + done page |
| `_check_upload_success` / `_get_upload_error` | Post-submit checks |

### 5.6 `UploadHandler` (`upload_handler.py`) — keep upload path only

| Function | Decision |
|----------|----------|
| `set_callbacks`, `_log`, `_update_progress` | MIGRATE |
| `upload_albums`, `upload_album` | MIGRATE / ADAPT |
| `start_processing` (if mixed convert+upload) | ADAPT — upload-only entrypoint |
| `stop_processing` | MIGRATE |
| `convert_albums`, `process_album` (enhancement) | SKIP |
| `cleanup_output` | ADAPT |

### 5.7 Scanner / history

| Function | Purpose |
|----------|---------|
| `clean_album_name`, `clean_track_title`, `extract_track_number` | Normalize titles for DistroKid |
| `find_thumbnail` | Cover art discovery |
| `scan_directory_for_albums`, `parse_directory_as_album`, `scan_multiple_directories` | Folder → Album |
| `is_duplicate_or_alternate` | Skip alt filenames |
| `validate_album_directory` | Preflight errors |
| `UploadHistory.record_success / is_uploaded / get_all / clear` | Duplicate prevention |

---

## 6. Config schema to migrate (upload-related only)

```text
upload_settings:
  auto_submit: bool
  cover_art_required: bool
  # raw_mp3_upload: DO NOT MIGRATE — WAV-only; always retry Suno WAV download

cleanup:
  delete_wav_after_upload: bool
  keep_browser_open: bool

upload_form:                    # DistroKid questionnaire defaults
  previously_released: bool
  artist_on_instagram: bool
  artist_on_facebook: bool
  social_media_pack: bool       # keep false; JS blocks auto-check
  language: str
  primary_genre / subgenre / secondary_genre: str
  songwriter_first_name / last_name / role: str
  explicit_lyrics / radio_edit / instrumental / ai_generated: bool
  preview_clip_preference: str
  apple_music_performers: [{role, name}, ...]
  producer_credits: [{role, name}, ...]
  retry_count: int
  element_timeout: int          # seconds
  delay_between_albums: int     # seconds
  max_albums_per_session: int
  release_date_mode: "default" | "custom"
  custom_release_date: str

artist_name: str                # map from CAMXORA channel profile when possible
```

**Do not migrate:** `audio_settings`, `optimizer_settings`.

---

## 7. External dependencies

| Package | Needed for upload? | Notes |
|---------|--------------------|-------|
| `playwright` | **Yes** | Core automation |
| System Chrome or Edge | **Preferred** | Persistent profile |
| `Pillow` | Optional | Artwork square prep |
| `pydub` / local MP3→WAV | **No** | Out of scope — Suno WAV only |
| `keyring` | No (unused in upload path) | Skip |
| `tinytag` | No (unused in reviewed upload path) | Skip |
| librosa / scipy / demucs / etc. | No | Enhancement stack — skip |

WAV files always come from Suno convert/download (`suno/wav`), with retries until success or hard fail (block DistroKid upload for that track/album).

---

## 8. Fit into existing CAMXORA DistroKid scaffold

Already present:

| Piece | Location |
|-------|----------|
| `$5/mo` entitlement | `platform_api` DistroKid add-on |
| Music checkbox | `automation_card.py` → `autoDistroKid` |
| Sidebar page | `features/distrokid/views/distrokid_view.py` |
| WAV pricing seed | `suno` / `wav` credit pricing |
| Channel metadata | profiles (artist, genre, etc.) |

---

## 8.1 Full intended Music → DistroKid pipeline

**Canonical order (agreed):**

```text
1. Draft lyrics
2. Suno MP3
3. Background image (BG)
4. Thumbnail image (TH)
5. Generate long MP4 (16:9 video template, full track)
6. Merged video          ← merge applies to LONG videos only
7. Generate Short video  ← bass-drop detect + ~30s trim; same MP3;
                           Short template (9:16); ONE FILE PER TRACK
                           (NEVER merge Short / former “Reel” outputs)
8. Download .wav from Suno (retry until success)
9. Upload to DistroKid   ← LAST
     uses: .wav + thumbnail image + album name + track titles from pipeline
```

**Checkbox / stage rules:**

| Stage | Merge? | Notes |
|-------|--------|-------|
| Long MP4 | Yes, when **Merge** is on | Existing long-video merge |
| Short | **No — never** | Leave each Short as an individual `*_SHORT.mp4` (or equivalent). Remove any “merge Short / merge Reel” behavior from product intent and from future automation. |
| DistroKid | N/A | Uses WAV + thumbnail, not the Short MP4 |

**DistroKid start gate:**

1. Entitlement: `distrokid_active`.
2. Music setting: `autoDistroKid` checked.
3. Suno MP3 success; BG/TH as required by cover policy.
4. Long MP4 done (if Video on); long Merge done (if Merge on).
5. Short done (if Short on) — individual files only; DistroKid does **not** wait on a Short merge (there is none).
6. For each track: Suno WAV convert + download to desktop/run folder (retry); hard-fail if WAV never arrives.
7. Duplicate fingerprint check (platform_api) → alert/block if match.
8. Open DistroKid browser automation.

**Runtime DistroKid payload:**

| DistroKid field | Source |
|-----------------|--------|
| Album name | Pipeline album title |
| Track titles | Pipeline song titles (Primary / Secondary) |
| Audio files | Local `.wav` from Suno download (desktop/run folder) |
| Cover | **Thumbnail image** from pipeline (TH) |
| Artist / genre / credits | DistroKid settings (± channel profile mapping) |

**Browser / login:** persistent Playwright profile; user signs in once; then fill album/tracks/WAV/cover and optional submit.

**Implementation note (current vs intended Short):**

- Today’s Music **Short** checkbox is still a **label rename** of former Auto Reel: full-track 9:16 via `reel_template_id`, and the existing video stack can still merge `reel` branch outputs.
- **Intended product:** Short = bass-drop ~30s clip, individual files only; **strip reel/short merge** from automation when Short is rebuilt. DistroKid migration must not depend on merged Short files.

---

## 8.2 Progress page & Workflow — recommendation

**Recommendation: include DistroKid as a visible pipeline stage, but keep it a soft/optional stage (not a hard blocker for “music/video success”).**

| Surface | Include DistroKid? | How |
|---------|--------------------|-----|
| **Progress** row / stage chips | **Yes** | Add a DistroKid stage: `pending` → `wav_downloading` → `uploading` → `success` / `failed` / `skipped_duplicate` / `skipped_no_entitlement` |
| **Workflow** timeline | **Yes (lightweight)** | DistroKid node after Short (or after long Merge if Short off) |
| **Batch “completed” for video** | **No hard dependency** | Long Video/Merge/Short can succeed even if DistroKid fails or is off |
| **Music Generate gate** | Unchanged | DistroKid does not block draft/Suno start |

**Why include it in Progress/Workflow**

- Users need to see “browser login waiting”, WAV retries, upload success/fail.
- Duplicate blocks should surface as an explicit status, not a silent skip.
- Matches the mental model: DistroKid is the last automation checkbox on Music.

**Why not make it a hard pipeline failure for the whole run**

- DistroKid needs interactive browser auth and is flaky vs DistroKid DOM.
- Users may still want MP3/video/merge outputs when DistroKid fails.
- Add-on entitlement / quota / duplicate guards are DistroKid-specific.

**Progress status vocabulary (proposed):**

| Status | Meaning |
|--------|---------|
| `distrokid_pending` | Checkbox on; waiting for prior stages |
| `distrokid_wav` | Requesting / downloading Suno WAVs |
| `distrokid_awaiting_login` | Browser open; user must sign in |
| `distrokid_uploading` | Form automation running |
| `distrokid_success` | Submitted / recorded |
| `distrokid_failed` | Hard fail (WAV, form, submit) |
| `distrokid_duplicate_blocked` | Guard matched history; user alerted |
| `distrokid_skipped` | Checkbox off or no entitlement |

---

## 8.3 Duplicate guard / history (desktop + platform_api)

**Problem:** Re-uploading the same album/tracks to DistroKid wastes time and risks DistroKid duplicates.

**Recommendation: dual store — local cache for fast UX + `platform_api` as source of truth.**

### Fingerprints to store (per successful or attempted upload)

| Field | Purpose |
|-------|---------|
| `user_id` / `license_id` | Account scope |
| `profile_id` / channel | Which CAMXORA channel |
| `batch_id` / `run_dir` | Pipeline identity |
| `album_name` (normalized) | DistroKid album title used |
| `track_title` (normalized) | Each song title |
| `wav_byte_size` | File size of uploaded WAV |
| `wav_sha256` (optional but recommended) | Stronger than size alone |
| `suno_audio_id` / `task_id` | Link to Suno clip |
| `cover_path` or cover hash (optional) | Cover used |
| `status` | `success` / `failed` / `blocked_duplicate` |
| `uploaded_at` | Timestamp |
| `distrokid_report_id` (optional) | Link to automation report |

### Guard behavior (before opening DistroKid form for an album)

1. Normalize album name + each track title (trim, case-fold, collapse whitespace).
2. Query platform_api: any prior **success** with same account + album name + overlapping track titles, **or** same `wav_sha256` / same `(title + wav_byte_size)` combo.
3. If match:
   - **Do not upload** that album (or matching tracks).
   - Alert user in UI (toast / Progress status `distrokid_duplicate_blocked`) with what matched.
   - Offer explicit **“Force upload anyway”** only behind a confirm dialog (optional Phase 2+).
4. After successful DistroKid submit: write history to platform_api **and** mirror locally for offline display.

### Why platform_api (not local-only)

- Survives machine reinstall / new PC.
- Same subscription can warn across devices.
- Admin/support can inspect DistroKid delivery history.
- Aligns with DistroKid add-on + WAV quota metering.

### Proposed API sketch (implement later)

```text
GET  /api/v1/distrokid/upload-history?limit=...
POST /api/v1/distrokid/upload-history/check   # body: album + tracks fingerprints → { ok | duplicates[] }
POST /api/v1/distrokid/upload-history         # record success/failure after run
```

Desktop still keeps a small local cache for Progress/history UI when offline, but **check** should prefer platform_api when online.

---

## 8.4 Proposed wiring (updated)

```text
Draft → MP3 → BG → TH → long MP4 → long Merge (if on)
  → Short per track (bass drop; NO short merge) [if Short on]
  → DistroKid checkbox ON + distrokid_active
        │
        ▼
Duplicate check (platform_api + local) → alert / block if match
        │
        ▼
For each track: Suno WAV convert + download to desktop run folder (retry)
        │
        ▼
DistroKidCoordinator / UploadWorker
  open browser → user login if needed
  album name + track titles + .wav paths + thumbnail (TH) cover
        │
        ▼
FormAutomator + TrackUploader + optional submit
        │
        ▼
Record history (platform_api + local) + WAV meter consume
  Update Progress/Workflow DistroKid stage
```

**Enforcement rules:**

1. Server/desktop must refuse upload start if `distrokid_active` is false.
2. Every DistroKid upload track **must** have a Suno-sourced `.wav`. If convert/download fails, **retry**; after max retries, fail that track/album — do **not** fall back to MP3 or local convert.
3. Suno WAV convert consumes DistroKid WAV quota (600/mo intent).
4. Duplicate fingerprint match → block + alert (unless user explicitly force-confirms, if we add that later).
5. Browser automation stays **desktop-local** (Playwright); platform_api stores history/quota/entitlement only — it does not drive DistroKid UI.
6. DistroKid runs only after prior enabled stages finish: long Video, long Merge, and Short (individual). DistroKid never waits for a Short/Reel merge.
7. **Never merge Short outputs** — remove merge-Short / merge-Reel from intended automation.

---

## 9. Proposed target file map (`camxora_python`)

```text
camxora_python/features/distrokid/
  views/distrokid_view.py              # expand: settings, connect, history, start
  services/
    browser_automation.py              # from AutoDistroKid browser.py
    element_resolver.py
    form_automator.py
    track_uploader.py
    distrokid_session.py               # login / navigate / submit
    upload_orchestrator.py             # from upload_handler (upload-only)
    automation_report.py
    album_scanner.py                   # from scanner (adapted to run-dirs)
    upload_history.py                  # local cache + API client
  models/
    distrokid_models.py                # Track/Album/FormConfig DTOs
  workers/
    distrokid_upload_worker.py         # background worker after merge
  lib/
    distrokid_settings.py              # UploadFormConfig persistence

platform_api/ (later)
  routers/distrokid_history.py         # check + record upload fingerprints
  migrations/..._distrokid_upload_history.py
```

Music page: keep checkbox; video automation chain schedules DistroKid **after** merge/export when `autoDistroKid` is on.

---

## 10. Phased implementation plan (after agreement)

### Phase 0 — Agreement / decisions

Agreed / remaining:

1. **WAV source (agreed):** Always Suno WAV convert + download to desktop, with retries. No local MP3→WAV, no raw MP3 DistroKid upload.
2. **Full pipeline (agreed):** Draft → MP3 → BG → TH → long MP4 → long Merge → Short (bass drop, individual files, **no Short merge**) → WAV → DistroKid (WAV + thumbnail).
3. **Progress/Workflow (recommended):** Soft DistroKid stage visible; does not fail whole music/video run.
4. **Duplicate history (recommended):** Fingerprints in **platform_api** + local cache; alert and block reupload.
5. **Album source:** Prefer CAMXORA run folders / pipeline albums (not free folder picker). _(confirm)_
6. **Submit mode:** default `auto_submit` true/false. _(pending)_
7. **Credits defaults:** map from channel profile vs DistroKid settings form. _(pending)_
8. **Artwork for DistroKid:** **thumbnail image (TH)** from pipeline. _(agreed intent)_
9. **Force upload despite duplicate?** _(pending — recommend confirm dialog later)_
10. **Short merge:** **Agreed — never.** Remove merge Short/Reel from product intent.

### Phase 1 — Library port (no full UI)

- Port browser + resolver + form automator + track uploader + session/submit.
- Unit tests with mocked Playwright page where practical.
- Manual smoke: login once + one album dry-run (keep browser open).

### Phase 2 — CAMXORA orchestration

- `upload_orchestrator` + worker chained **after** long merge + Short (individual) when DistroKid is on.
- Gate on `distrokid_active` + prior-stage completion.
- Wire Music DistroKid checkbox.
- Suno WAV download-to-desktop with retries.
- Duplicate-title + platform_api fingerprint check + user alert.
- Ensure Short path does **not** call merge for short/reel outputs (when Short bass-drop work lands).

### Phase 3 — Settings + history UX + Progress/Workflow

- DistroKid settings UI (form questionnaire defaults).
- Connect DistroKid (open browser for Google Sign-In).
- History list (local + API).
- Progress DistroKid stage + Workflow node.

### Phase 4 — WAV + quota

- Require DistroKid WAV convert path (`suno/wav`) before each upload.
- Retry convert/download on failure; hard-fail album/track if WAV never arrives.
- Enforce 600/mo meter.
- No local convert / no MP3 upload path.

### Phase 5 — Hardening

- Selector registry + report artifacts under CAMXORA diagnostics.
- Session-expired recovery UX.
- Rate limits (`delay_between_albums`, `max_albums_per_session`).
- Optional “Force upload anyway” confirm for duplicates.

---

## 11. Risks

| Risk | Mitigation |
|------|------------|
| DistroKid DOM changes break selectors | Keep `ElementResolver` + reports; version selector packs |
| Google Sign-In / 2FA friction | Persistent profile; clear “Connect once” UX; Progress `awaiting_login` |
| Playwright packaging in desktop installer | Prefer system Chrome/Edge; document Chromium install fallback |
| Legal / ToS of automating DistroKid | Product/legal review before production enable |
| Accidental Mixea enhancement | Keep submit path that chooses **Use my originals** |
| Suno WAV convert/download flaky | Retry with backoff; block DistroKid upload until WAV exists |
| Quota abuse | Enforce DistroKid add-on + WAV meter |
| Duplicate DistroKid releases | platform_api fingerprint history + pre-upload alert/block |
| DistroKid fails after long video/merge | Soft Progress stage — do not rewind video success |

---

## 12. Acceptance criteria (when we implement)

1. With DistroKid add-on active, user can connect DistroKid once and reuse session.
2. With DistroKid checkbox on, upload starts only **after** prior enabled stages complete: long Video, long Merge, Short (individual files).
3. Progress (and Workflow) show a DistroKid stage without failing the whole run on DistroKid errors.
4. Every uploaded file is a **Suno-downloaded `.wav`** on the user desktop/run folder; failed WAV fetch is retried, then hard-fails (no MP3 / no local convert).
5. Album name and track titles come from the CAMXORA pipeline; DistroKid cover is the **thumbnail image**.
6. Short outputs are never merged; each Short remains its own file.
7. Pre-upload duplicate guard checks album name / track title / WAV size (and ideally hash) via platform_api; user is alerted and upload is blocked on match.
8. Successful uploads are recorded in platform_api history (and local cache).
9. Form answers match DistroKid settings (genre, songwriter, AI/instrumental flags, credits).
10. Singles skip album title; multi-track fill album title.
11. Submit path does not use DistroKid audio enhancement (Use my originals).
12. Without entitlement, DistroKid checkbox stays disabled and upload start is blocked.
13. No code from AutoDistroKid enhancement/AI/local converter stack is imported.

---

## 13. Decision log (fill when agreed)

| # | Question | Decision | Date |
|---|----------|----------|------|
| 1 | WAV source | **Agreed:** always Suno WAV convert/download with retries; no local convert; no raw MP3 | 2026-07-27 |
| 2 | Album source | **Recommended:** CAMXORA pipeline/run-dir only | 2026-07-27 |
| 3 | Default auto_submit | _pending_ | |
| 4 | History storage | **Recommended:** platform_api source of truth + local cache | 2026-07-27 |
| 5 | DistroKid cover | **Agreed intent:** thumbnail image (TH) | 2026-07-27 |
| 6 | Allow raw MP3 upload? | **Agreed: no** | 2026-07-27 |
| 7 | Map artist/genre from channel profile automatically? | _pending_ | |
| 8 | Full pipeline order | **Agreed:** Draft→MP3→BG→TH→long MP4→long Merge→Short (bass drop, individual)→WAV→DistroKid | 2026-07-27 |
| 9 | Progress/Workflow | **Recommended:** soft DistroKid stage; do not fail whole run | 2026-07-27 |
| 10 | Duplicate guard fingerprints | **Recommended:** album name + track title + wav size (+ sha256); block + alert | 2026-07-27 |
| 11 | Force upload despite duplicate? | _pending_ | |
| 12 | Merge Short / former Reel? | **Agreed: never** — Short files stay individual; remove short/reel merge from intent | 2026-07-27 |

---

## 14. Note on Music “Short” (current vs intended)

| | Today (shipped UI) | Intended product (this plan) |
|--|--------------------|------------------------------|
| Checkbox label | **Short** (renamed from Auto Reel) | **Short** |
| Setting key | `autoReelAfterVideo` | may rename later (`autoShortAfterVideo`) |
| Behavior | Full-track 9:16 via `reel_template_id` | Bass-drop detect + ~30s trim; Short template; **same MP3** |
| Merge | Code still can merge `reel` branch | **Never merge Short** — leave individual files |
| DistroKid | Not wired | After Short + WAV download; DistroKid uses WAV + TH, not Short MP4 |

Bass-drop Short + removing short/reel merge are **separate implementation work** from DistroKid browser automation, but the DistroKid plan assumes that intended pipeline order.

---

## 15. References

- Source: `D:\Development\Projects\AutoDistroKid\src\automation\*.py`, `src\core\{scanner,config,models,history,file_ops}.py`
- CAMXORA scaffold: `docs/changelog/2026-07-27-distrokid-addon-scaffold.md`
- CAMXORA UI: `camxora_python/features/distrokid/`, Music `autoDistroKid` setting
- Video chain: `camxora_python/features/video/lib/desktop_video_automation.py`

**Next step:** confirm §13 recommendations (especially Progress soft-stage, platform_api history, force-upload policy), then approve Phase 1 library port. No DistroKid automation implementation until agreement.
