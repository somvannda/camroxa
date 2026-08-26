# Changelog — Desktop app (`camxora_python`)

All notable changes to the **Camxora desktop app** (PySide6 client) are documented here.

This is **not** the changelog for user portal, music portal, admin portal, platform API, or website — see [`docs/CHANGELOG_GUIDE.md`](docs/CHANGELOG_GUIDE.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Sandbox desktop env now points at `/api/v3` (`camxora_python/.env.sandbox`). See `docs/changelog/2026-08-26-api-v3-cutover-emitted-urls.md`.
- All API calls now target `/api/v3` exclusively. Default base URL, env examples, sandbox/production shortcuts, WebSocket helper, health-URL extractor, and marketplace asset resolver all updated. See `docs/changelog/2026-08-25-clients-api-v3-only.md`.
- Desktop login shows a clear paid-plan message when a Free account tries to sign in (`X-Camxora-Client: desktop`). See `docs/changelog/2026-08-23-desktop-paid-gate-and-website-pricing.md`.
- Desktop Generate chrome is credits-only (no Plan quota label). Website, user portal, and Web Music advertise Starter / Creator / Studio. Dual-channel is a bullet. Unpublished $5/$10 profile packs stay off public pricing.

### Fixed

- Continue Progress no longer retries image jobs that already succeeded, and
  will not start video export until a local background PNG is ready (`long_ready`).
- Sandbox API payload audit: `/api/v3/subscriptions/plans` omitted real `daily_credits` (Free showed 0). See `docs/changelog/2026-08-25-fix-v3-daily-grant-and-likes.md`.

## [1.3.1] - 2026-08-17

Desktop-only production installer `CamxoraSetup-1.3.1.exe` from `main`
(through PR #57). Does **not** include music-web, admin portal, DistroKid,
or a YouTube Done historical backfill.

### Added

- **Dashboard / Profile used/quota:** Usage This Month and Membership show
  used / allowance (for example `200 / 300`) and scale add-on channel caps.
  See `docs/changelog/2026-08-16-desktop-dashboard-used-quota.md`.

### Fixed

- **Video prewarm no longer decodes preview audio** until the Video page is
  opened. Shell startup still builds the page; the last MP3 is analyzed on
  first visit. See `docs/changelog/2026-08-17-progress-p2-prewarm-and-pipeline-latch.md`.

- **Finished albums latch `pipeline_complete`** when Progress sees a local
  `MERGED_*.mp4` or an idle Long completed row that never saved the flag.
  After restart those rows stay frozen without another folder walk.
  See `docs/changelog/2026-08-17-progress-p2-prewarm-and-pipeline-latch.md`.

- **Progress stays responsive on Long completed rows:** idle albums are not
  re-listed or re-stat'd on every poll, and the row context menu no longer
  walks the run folder on the UI thread. Right-click should open immediately.
  Active only hides those idle rows (YouTube/Error stay). Unfinished folders
  reuse a listing while the directory mtime is unchanged.
  See `docs/changelog/2026-08-17-progress-skip-idle-disk-scans.md`.

- **Auto-video no longer redoes Long completed runs** when the user deletes
  per-track MP4s or moves the folder. A known long merge (`pipeline_complete`,
  `MERGED_*.mp4`, or a Long completed / Long merged label) is treated as
  archived, not unfinished. Explicit Rebuild / Repair / Force still regenerate.
  See `docs/changelog/2026-08-17-freeze-auto-video-after-long-completed.md`.

### Changed

- Desktop version stamp **1.3.1** / installer `CamxoraSetup-1.3.1.exe`.
  Publish with **Force update** so **1.3.0** clients upgrade.
  Detail: `docs/changelog/2026-08-17-desktop-1.3.1.md`.

## [1.3.0] - 2026-08-14

Installer rebuilt **2026-08-15** (same **1.3.0** stamp): real Suno MP3 downloads
and Opus-in-MP4 export no longer hang the queue.

### Added

- **Regenerate missing/broken MP4s:** Progress can re-export only tracks whose
  MP4 is missing, tiny, corrupt, or truncated — without restarting music or
  images. **Regenerate one track** targets a specific MP3. Start Merging and
  Continue Progress repair those files first, then concat. Billing charges the
  repaired tracks only. See `docs/changelog/2026-08-14-regenerate-broken-mp4.md`.
- Progress Long `N/N` no longer counts stub MP4s under 50KB as finished.
  Auto-video re-exports only unhealthy tracks; nested run folders are used for
  repair the same way as merge.

### Fixed

- **Suno `.m4a` downloads saved as `.mp3`:** Suno’s CDN often returns
  `{id}.m4a` (Opus) while `{id}.mp3` is the real MPEG file. Downloads now use
  the `.mp3` URL, refuse to save non-MPEG bytes, and retry later instead of
  keeping a fake MP3. See `docs/changelog/2026-08-15-suno-prefer-real-mp3.md`.
- **Opus-in-MP4 named `.mp3` hung the whole export queue:** Some Suno files are
  real audio (Opus in an MP4 container) saved with a `.mp3` name. Windows plays
  them; mpg123/librosa could hang forever and block every other Start Export.
  Export now decodes those files with ffmpeg, retries a track 3 times, then
  skips it and continues the album / next run. See
  `docs/changelog/2026-08-15-opus-mp4-export-hang.md`.
- **Progress Merge wrote no file:** Start Merging could show “Merging…” and finish
  without a `MERGED_*.mp4`. Skip is now a real error, merge-only no longer
  requires today’s export FPS/48 kHz, and a successful merge marks the row
  complete. See `docs/changelog/2026-08-14-progress-merge-no-output.md`.
- **Suno folder reset after installer:** A Preferences Suno directory (for
  example `D:\Suno Generated`) could revert to AppData `Media\Suno` on first
  launch after a new build. Saved device paths are no longer overwritten by
  startup self-heal, and a leftover root `device-workspace-paths.json` is
  merged into the signed-in account folder. See
  `docs/changelog/2026-08-14-suno-dir-reset-on-upgrade.md`.
- **Merge + Suno path hardening:** Merge succeeds only with a real
  `MERGED_*.mp4` on disk, nested run folders are found, stale merged files are
  rebuilt, and a device-path backup recovers a custom Suno folder if the
  primary store was reset. See
  `docs/changelog/2026-08-14-merge-and-suno-path-hardening.md`.
- **Software update gate:** Includes latest `main` fixes so a leftover draft or
  missing installer file does not keep blocking the app after the live release
  is restored. See `docs/changelog/2026-08-13-force-update-draft-restore.md`.

### Changed

- Desktop version stamp **1.3.0** / installer `CamxoraSetup-1.3.0.exe`. Publish
  with **Force update** so **1.2.6** clients upgrade. **1.2.7 was not published.**
  Detail: `docs/changelog/2026-08-14-desktop-1.3.0.md`.

## [1.2.6] - 2026-08-13

### Fixed

- **Force update after draft/delete:** On app open the client rechecks the live
  public release. If that version was moved back to draft, unpublished, or
  deleted, the blocking gate clears (404/non-mandatory live). A network error
  still keeps a persisted required update. See
  `docs/changelog/2026-08-13-force-update-draft-restore.md`.

- **Spectrum ring color seam:** Full-circle gradients melt across the first/last
  stop (no hard cyan|magenta cut at 12-o'clock). Applies to preview, Manual
  Export, and Auto-Video. See
  `docs/changelog/2026-08-13-spectrum-ring-color-melt.md`.
- **Pipeline Auto-Video vs Manual Export:** Saved-template auto-export no longer
  drops multi-bolt lightning / spectrum instances (or silent Draft 720p encode).
  Headless pipeline now builds the same renderer domains as Manual Export and
  uses Standard encode defaults so spectrum glow melt and lightning density
  match. See `docs/changelog/2026-08-12-pipeline-export-wysiwyg.md`.
- **Export Workers on Quality / Best Quality:** Spinning Workers no longer
  fights a hard lock of 1 via publish→rebind→clamp (could crash the app).
  Workers are capped by GPU tier (low=1, mid=3, high=5) and ask for
  confirmation before using more than 1. See
  `docs/changelog/2026-08-12-quality-workers-spin-crash.md`.

### Changed

- Desktop version stamp **1.2.6** / installer `CamxoraSetup-1.2.6.exe`. Publish
  with **Force update** so **1.2.5** clients upgrade. Detail:
  `docs/changelog/2026-08-13-desktop-1.2.6.md`.

## [1.2.5] - 2026-08-11

### Fixed

- **Frozen Manual Export:** `ImportError: numpy._core.multiarray failed to
  import` when SciPy 1.17 loaded in the PyInstaller build (NumPy 1.26’s
  `_core` compat package was omitted). Bundle `numpy`/`scipy` fully and add a
  NumPy-only STFT fallback. See
  `docs/changelog/2026-08-11-frozen-numpy-core-export.md`.

### Changed

- Desktop version stamp **1.2.5** / installer `CamxoraSetup-1.2.5.exe`. Publish
  with **Force update** so **1.2.4** clients upgrade.
- **Software update gate UI:** Simplified centered card with Camxora logo and
  compact Install CTA (no What’s new section). Preview with
  `CAMXORA_PREVIEW_UPDATE_GATE=1`. See
  `docs/changelog/2026-08-11-software-update-gate-ui.md`.
- **Software update copy:** Professional installer-focused wording across gate,
  progress, and failure states.

## [1.2.4] - 2026-08-11

### Fixed

- **Lightning export timing:** Restore per-layer flash floors from the
  preview-export-parity work so each bolt keeps its own strike timing.
  1.2.3’s global floor made all layers visible but synchronized them.
  Visibility still uses the corrected floor math (no double-scale) so
  mid-interval peaks stay drawable. See
  `docs/changelog/2026-08-11-lightning-export-timing.md`.

### Changed

- Desktop version stamp **1.2.4** / installer `CamxoraSetup-1.2.4.exe`.

## [1.2.3] - 2026-08-11

### Fixed

- **Multi-bolt lightning export:** Manual Export again raises all enabled
  lightning layers when any bolt peaks in the encode window (restores pre-1.2.2
  multi-bolt density). Sparse per-layer floors in 1.2.2 often left only one
  bolt visible. Flash floor no longer double-scales sampler peaks. Lightning
  Add/Dup/position updates schedule a live preview refresh. See
  `docs/changelog/2026-08-11-lightning-multibolt-export.md`.

### Changed

- Desktop version stamp **1.2.3** / installer `CamxoraSetup-1.2.3.exe`. Publish
  with **Force update** so **1.2.2** clients upgrade. Detail:
  `docs/changelog/2026-08-11-desktop-1.2.3.md`.

## [1.2.2] - 2026-08-11

### Added

- Manual export hard-gates on live preview vs export renderer JSON (focus keys);
  mismatch blocks the track, notifies, and writes a parity report under client
  logs. Lightning export samples ~60 Hz per-layer peaks so encode FPS timing
  matches preview. See `docs/changelog/2026-08-11-preview-export-parity-gate.md`.
- Music Automation Structure dropdown includes **Suno Structure** (native free section layout) alongside AI Structure and Music Structure templates. Structure Shuffle is locked off for AI/Suno Structure (settings restore and saved `shuffleStructure` cannot resurrect it). See `docs/changelog/2026-08-10-suno-structure-mode.md`.

### Changed

- Desktop version stamp **1.2.2** / installer `CamxoraSetup-1.2.2.exe`. Publish with
  **Force update** (mandatory) in Admin → Software Updates so **1.2.1** clients upgrade.
  Requires matching `platform_api` with `structure_mode=suno`. Detail:
  `docs/changelog/2026-08-11-desktop-1.2.2.md`.
- Sandbox desktop single-instance lock is env-scoped so sandbox can run alongside production; production keeps `Camxora.DesktopStudio.SingleInstance.v1`. See `docs/changelog/2026-08-10-sandbox-dual-instance-lock.md`.
- Lightning layer stack capped at **10 bolts** (Add/Dup disabled at the cap;
  templates normalize to at most 10). Preview and export both keep every layer
  up to that limit. See `docs/changelog/2026-08-09-lightning-max-10-layers.md`.

### Fixed

- Video export Resolution / FPS / Speed / Workers no longer crash with
  `PatchSettingsWorker` destroyed while running; saves are coalesced and also
  mirrored to local prefs. See
  `docs/changelog/2026-08-11-video-export-settings-patch-harden.md`.
- Live preview now applies layer **Raise Scroll** (`frequencyScroll`) and **Row Width**
  (`linearSpan`) from renderer JSON — previously only export honored them.
  See spectrum UI↔JSON audit below.
- Preview FFT envelope now matches export: catch up on seek, and do **not** keep
  re-smoothing the same analysis frame while paused (that made scrubbed 0:24 look
  colder/tighter than export). Shared `fft_to_log_bins` + `smooth_and_mirror`.
- Export spectrum reactivity now uses **60 Hz** audio analysis like live preview
  (was 30 Hz). See `docs/changelog/2026-08-11-export-spectrum-60hz-analysis.md`.
- Fast/Balance export now draws the same dual spectrum **glow** passes as live
  preview (was skipped for speed), so Bass Drive wings match the stage.
  See `docs/changelog/2026-08-11-export-spectrum-glow-wysiwyg.md`.
- Spectrum **Glow Strength / Softness** export used full `ONE,ONE` additive
  blending while preview used alpha-weighted additive — export wings looked
  much larger with glow on. Export now matches preview blend + shared pass
  specs. See `docs/changelog/2026-08-11-spectrum-glow-blend-parity.md`.
- Export no longer injects factory default spectrum rings when an instance has
  empty layers (uses top-level `layers` only). See
  `docs/changelog/2026-08-11-preview-export-parity-gate.md`.

## [1.2.1] - 2026-08-08

### Added

- Image page Background / Thumbnail prompts show a live `current / 5000` counter and hard-cap input at 5000 characters (matches API image prompt gate). See `docs/changelog/2026-08-08-image-prompt-ui-char-cap.md`.

### Changed

- Desktop version stamp **1.2.1** / installer `CamxoraSetup-1.2.1.exe`. Publish with
  **Force update** (mandatory) in Admin → Software Updates so **1.2.0** clients upgrade.
  Detail: `docs/changelog/2026-08-08-desktop-1.2.1.md`.
- **Force update runs only at app open** — before login, relogin, or entering the studio.
  The client reads `GET /public/desktop-release` and blocks with the update gate when the
  published release is newer and mandatory. Mid-session publish shows a green
  **arrow-up-circle** header icon (left of notifications, tooltip “Update available”)
  so users can update when ready — without a blocking overlay. See
  `docs/changelog/2026-08-08-force-update-on-app-open.md`.
- Preferences **Local Paths** keeps FFmpeg + **Suno output dir** only (this PC). Downloads /
  Merged / optional Image output fields removed from the UI (auto-defaults; batch assets
  still land under the Suno tree).

### Fixed

- Image page **Regenerate Background / Thumbnail** now replaces the previous local PNG
  instead of keeping the old file when the server reuses the same output path. See
  `docs/changelog/2026-08-08-image-regenerate-stale-local.md`.
- Startup splash no longer flashes as if Camxora closed/reopened when Video
  workspace prewarm mounts the GPU preview (`QOpenGLWidget` HWND recreate).
  OpenGL is configured before `QApplication` and primed on `RootWindow` before
  the first `show()`. See `docs/changelog/2026-08-08-startup-opengl-window-prime.md`.
- Preferences save no longer overwrites the local Suno root with a stale AppData path from
  account settings. Device store is written from the draft the user saved; absolute media
  roots are not PATCHed to the cloud. Leftover `%LOCALAPPDATA%\...\Media\Suno` folders no
  longer win when Suno output dir is elsewhere (e.g. `E:\SUNO`). See
  `docs/changelog/2026-08-08-suno-device-path-preference-fix.md`.

## [1.2.0] - 2026-08-06

### Added

- Progress right-click **Download missing MP3s (N)** for the selected channel role:
  fetches existing Suno/Backblaze URLs for tracks not present on disk (no re-draft /
  re-Suno). See `docs/changelog/2026-08-06-app-owned-run-paths-and-missing-mp3.md`.
- **Track list Remove:** After Select MP3 Folder, remove songs from TRACK LIST via the × on each row (or Delete/Backspace) without deleting files. Select MP3 Folder again reloads the full folder.

### Changed

- Desktop version stamp **1.2.0** / installer `CamxoraSetup-1.2.0.exe`. Publish with
  **Force update** (mandatory) in Admin → Software Updates. Detail:
  `docs/changelog/2026-08-06-desktop-1.2.0.md`.
- Desktop owns local Suno drop paths: Progress overlays, Open Run Folder, and missing
  MP3 downloads always resolve API absolute `run_dir` values under this PC's Suno root
  via the relative `channel/date_album` key.
- Desktop no longer PATCHes absolute `sunoOutputDir` / media roots into account settings
  (stops cross-machine path thrash). Local device store remains the drop-root authority.
- Progress **Done / Completed / YouTube** rows hide Continue / Stop / Cancel / Start
  Export / Merge / retries; keep Open Run Folder, Change Run Folder, and explicit
  Force Regenerate / Rebuild MP4.
- Change Run Folder sets `persist_batch_run_dir` so the API rewrites that role's
  batch run key; background Progress sync and missing-MP3 download do not.
- Progress Music **% / X/Y** use landed role MP3 files on disk when the run folder
  is present — not API `downloaded_ok` / `downloaded_alt` flags (those can flip
  before files exist).
- **Manual export Resolution:** Actions panel replaces Tier (Draft/Standard/Master) with **Resolution**, using the same `OUTPUT_RESOLUTION_OPTIONS` list as the preview Output resolution (no custom/Master). Selection syncs `outputResolution` so batch exports and Auto merge stay on one WxH.
- **Export Speed Quality:** Actions Speed adds **Quality** (preview-parity: full-color pipe + spectrum glow; slower encode).
- **Export Speed Best Quality:** Speed order is Best Quality → Quality → Balance → Fast → Very Fast. Best Quality uses a slower/higher-fidelity encode (NVENC p7) and always keeps the full-color pipe.
- **Export Recommended bitrate:** Encode switches from CQ/constqp to CapCut-inspired VBR bitrate scaled by Resolution × FPS × Speed (2K@30 Quality ≈ 12 Mbps). Per-track export + lossless merge unchanged.
- **Export worker safety:** Quality / Best Quality force 1 worker; QHD+ Balance caps at 2. Waiting on a full export gate shows status / times out instead of hanging at 0%.
- Background/Thumbnail source UI shows only **Category** and **Prompt only**;
  **User reference** is hidden until portal personal refs (P2). Saved
  `personal_reference` coerces to Category. See
  `docs/changelog/2026-08-06-connect-error-and-null-sample-path.md`.

### Fixed

- Release ConnectError / API-unreachable banners no longer leak `uvicorn` / port 8000
  (local/dev builds still show the start hint). See
  `docs/changelog/2026-08-06-connect-error-and-null-sample-path.md`.
- Progress filters: Active only and Stage now apply **before** Limit (after desktop overlays). Active only + Limit 10 means up to 10 active rows. See `docs/changelog/2026-08-06-progress-filters-composition.md`.
- **Manual export merge path:** Manual batch outputs now use `{stem}.mp4` (and pass `--output` to the visualizer) so Auto merge finds the files that were actually written, instead of looking for missing `*_CAMXORA_*` stamps.
- **Pipeline merge quality gate:** Export skip/success and merge inputs require a usable MP4 (video stream + duration, and not truncated vs source audio when ffprobe is available). Incomplete or broken exports are no longer treated as merge-ready just because they are larger than 50KB.
- **Merge input rebuild:** Merge rebuilds its file list from verified on-disk outputs (with a run-folder scan fallback) and keeps the Auto merge toggle after merge completes.
- **Merge encode parity:** Merge is **lossless stream-copy only** (same quality as exports). Before join, inputs are probed for matching resolution/FPS/codec/color_range/audio; mismatches fail with a clear error instead of re-encoding. New exports force AAC 48 kHz stereo so audio layout stays concat-safe. Early-skip rejects stale leftovers that don't match the current batch specs.
- **Export usable-MP4 false negative:** ffprobe success (`returncode == 0`) was treated as failure (`0 or 1`), so valid exports were marked failed and Auto merge never ran.
- **Merge progress percent:** Merge status uses a determinate 0–100% bar (FFmpeg `-progress`) instead of an indeterminate busy spinner.
- **Export Speed Quality CLI:** Visualizer `--speedMode` accepts `quality` / `master` (UI was sending `quality`, argparse only allowed `balanced|fast|very_fast`).

### Notes

- Includes **1.1.1** image prompt modes / Manual Generation and **1.1.0** ship-safe preview.
- Production API for album-lock, Alt CDN heal, relative run keys, and null sample-path
  guard is already deployed — no extra API ship required for this installer.
- Not in this release: theme categories (P1), personal reference library (P2), Progress
  Replace/Export (P3), DistroKid.

## [1.1.1] - 2026-08-05

### Added

- **Image source modes (P0):** Under Preferences → AI Generated, Background and Thumbnail each choose **Category**, **User reference**, or **Prompt only**. Overlay UI is hidden. User Provided media hides those source controls. Prompt only generates from your prompts with no Category sample image.
- **Image page controls:** Source-mode combos above Background/Thumbnail previews (synced with Preferences), **Manual Generation** under each prompt, clearer **Retry** vs **Regenerate** (force) menus, and credit/quota-aware error messaging.
- **Manual Generation queue rows:** With no song selected, Manual Generation creates a today-dated Image queue row labeled **Not available**, selects it, and runs the normal billed image-job path (Background and/or Thumbnail).
- **Quieter Image poll:** Background refresh (~12s) no longer resets source/prompt controls, flashes status chrome, or reloads previews unless the selected job output actually changed.
- **Queue regenerate:** Image queue supports **Regenerate Background + Thumbnail** (force reset of successful jobs).

### Changed

- Desktop version stamp **1.1.1** / installer `CamxoraSetup-1.1.1.exe`.
- Deselected Manual Generation no longer uses the preview-only `/generation/image` playground; it always creates or selects a queue row.
- Requires matching **production API** (prompt-only modes, force regenerate, `POST /image-jobs/manual-generate`, migration `082`) and restarted image workers after API deploy.

### Notes

- Includes prior **1.1.0** ship-safe preview (HDR bloom off by default) and windowed click hit-test fix.
- Not in this release: theme categories (P1), personal reference library (P2), Progress Replace/Export (P3).
- Detail: `docs/changelog/2026-08-05-desktop-1.1.1-image-prompt-modes.md`.

## [1.2.0-interim] - 2026-08-04

Historical short-lived stamp (window click hit-test) later folded into the **1.1.0** /
**1.1.1** line. Superseded by production **[1.2.0] - 2026-08-06** above.

### Fixed

- **Windowed shell clicks land on the painted control again.** Dropped
  translucent HWND + setMask() rounding that offset hit-testing on some
  Windows DPI setups (maximized already worked). Rounded look kept via DWM +
  QSS on the opaque surface (REQ-P3.2). See
  docs/changelog/2026-08-04-window-chrome-click-hit-test.md.

### Changed

- Interim desktop stamp **1.2.0** / CamxoraSetup-1.2.0.exe (Aug 4). Includes
  everything from **1.1.0** (HDR bloom, export WYSIWYG, preview P0–P4.3 stack).

## [1.1.0] - 2026-08-05

### Changed

- **Ship-safe installer:** Preview HDR bloom is **off by default** (legacy glow).
  Set `CAMXORA_PREVIEW_HDR_BLOOM=1` to opt in. Default-on bloom wiped particles/
  logo and stacked spectrum/lightning haze. See
  `docs/changelog/2026-08-05-desktop-1.1.0-hdr-off-ship.md`.
- Installer: `CamxoraSetup-1.1.0.exe` (includes windowed click hit-test fix).

### Added

- **HDR bloom path (opt-in).** Preview and export can use HDR bloom/tonemap when
  `CAMXORA_PREVIEW_HDR_BLOOM=1`. See
  `docs/changelog/2026-08-04-desktop-1.1.0.md`.
- **Export HDR bloom parity.** Same bloom/tonemap path as live preview. See
  `docs/changelog/2026-08-04-preview-p4-export-parity.md`.
- **Preview HDR bloom path.** Offscreen threshold / blur pyramid / tonemap into
  the Qt preview FBO with opaque alpha. See
  `docs/changelog/2026-08-04-preview-p4-hdr-bloom.md`.

### Fixed

- **Export not WYSIWYG vs Video preview.** Spectrum instances (style/position/
  attach), live draft style tweaks, and lightning flash undersampling now flow
  into export; Logo **Reset Center** restored. See
  `docs/changelog/2026-08-04-export-wysiwyg-spectrum-logo-parity.md`.
- **Black live Video preview after P0 Alpha_Lock.** End-of-frame alpha force used
  `moderngl.Context.clear` with a color mask; ModernGL ignores the mask and wiped
  RGB to black every frame (textures still uploaded). Now uses raw GL
  `glColorMask`+`glClear`. See
  `docs/changelog/2026-08-04-preview-black-moderngl-alpha-clear.md`.
- **Video export GLSL `noise2` crash on some GPUs.** Smoke shader helper renamed
  to `smoke_hash_noise2` so driver-reserved `noise2` overloads no longer abort
  compile. Failed-export refunds clamp `reason` to 500 chars (desktop + API) so
  traceback dumps no longer block allowance restore. Music preflight skips the
  API when From/To dates are inverted. See
  `docs/changelog/2026-08-04-export-glsl-noise2-and-refund-clamp.md`.
- **Preview see-through on some GPUs.** Soft glow / additive spectrum, particle,
  and lightning draws no longer punch alpha holes in the Qt OpenGL framebuffer
  under the frameless translucent window. Standalone Alpha_Lock hotfix — playlist
  glass is **not** included. See
  `docs/changelog/2026-08-04-preview-opaque-alpha-p0.md`.
- **Preview GL diagnostics were invisible on user machines.** OpenGL init /
  background / logo upload breadcrumbs now write to
  `%LOCALAPPDATA%\Camxora\logs\preview-gl-diag.log` and important lines also
  appear in the daily `camxora-*.log` as `[preview-gl]`. Copy Diagnostics
  includes `glReady` / `lastGlError` / GPU info. Init/FBO failures show an
  opaque error panel (no desktop hole). See
  `docs/changelog/2026-08-03-preview-gl-diag-logging.md` and
  `docs/changelog/2026-08-04-preview-p1-diag-failure-ux.md`.
- **Video inspector scrub felt laggy with live preview.** Allowlisted glow /
  opacity / barWidth / particle size-opacity updates patch the live preview
  template without a full normalize each tick; scrub runs at 20 FPS and
  canonical-flushes when idle. See
  `docs/changelog/2026-08-04-preview-p2-interactive-perf.md`.
- **Frameless rounded chrome keeps `WA_TranslucentBackground` by design.**
  Audit confirms `#window_surface` is the opaque backplate; preview
  see-through is handled by P0 Alpha_Lock, not by removing window
  translucency. Safer DWM-only corners deferred. See
  `docs/changelog/2026-08-04-preview-p3-chrome-audit.md`.

## [1.0.20] - 2026-08-04

### Fixed

- **GPU export crashed with `NameError: scroll_spectrum_heights is not defined`.**
  The 1.0.19 ship-cut dropped the Raise Scroll import while leaving call sites.
  Import restored; regression test + P5 ship-safety gate added so P0–P4 merges
  cannot lose it again. See
  `docs/changelog/2026-08-04-scroll-spectrum-heights-import.md`.

## [1.0.19] - 2026-08-04

### Fixed

- **Export crashed on older NVIDIA drivers.** Bundled FFmpeg NVENC needs driver
  570+ (API 13.0). When the installed driver is older, export now probes NVENC
  first and falls back to software encode (libx264) instead of failing with
  `BrokenPipeError` / “nvenc API version”. See
  `docs/changelog/2026-08-04-export-nvenc-driver-fallback.md`.

### Changed

- Ship cut: **DistroKid / WAV automation** and **playlist glass polish** are
  excluded from this installer (not ready). Same per-device path + spectrum
  fixes as 1.0.18. See `docs/changelog/2026-08-04-desktop-1.0.19-ship-cut.md`.

## [1.0.18] - 2026-08-04

### Fixed

- **MP3 downloads / Progress / Auto-Video no longer need an app restart** after
  per-device Suno path setup. Download polls hydrate and push this PC's Suno
  root mid-session; Progress and Auto-Video disk checks use the remapped local
  run folder instead of a stale cloud AppData path. See
  `docs/changelog/2026-08-03-per-device-workspace-paths.md`.
- Includes everything from **1.0.17** (per-device media folder roots + Spectrum
  Save / Row Width / Raise Scroll + 1.0.16 force-update).

## [1.0.17] - 2026-08-03

### Fixed

- **Same account on two PCs keeps separate media folder roots.**
  `sunoOutputDir`, `downloadsDir`, `mergedDir`, and image sample/output dirs are
  stored per-machine under
  `%LOCALAPPDATA%\Camxora\users\{userId}\device-workspace-paths.json` and win
  over stale cloud paths on login. The active desktop still pushes its roots so
  server run-dir planning matches this PC. Pending Suno MP3 downloads planned
  under another machine's path are remapped onto the local Suno root
  (`channel/date_album` preserved). See
  `docs/changelog/2026-08-03-per-device-workspace-paths.md`.
- Spectrum Save overwrite no longer reloads the stale Orbit Spikes / original look; live `spectrumInstances` are flushed into the save patch (existing + new templates).
- Linear spectrum **Row Width** restored (full preview span at 1.0); geometry no longer hard-capped at 80% frame width.
- Spectrum **Raise Scroll** helpers/UI restored (`frequencyScroll`) so preview/export imports stay consistent.
- Includes everything from **1.0.16** (force-update visible Setup progress +
  mid-install reopen handling).

## [1.0.16] - 2026-08-03

### Fixed

- **Force update looked finished when Setup was still installing.** After
  download, Camxora claimed “Install ready” and quit while Inno could still
  take minutes. Reopening the desktop icon mid-install showed the old
  version (e.g. 1.0.14). Force update now launches Setup with a **visible
  progress window** (`/SILENT`, not `/VERYSILENT`), tells users to wait for
  that window, verifies `app-version.txt` before relaunch, and persists a
  mandatory update so a mid-Setup reopen shows “Finishing update…” / Try
  again instead of a silent old build. See
  `docs/changelog/2026-08-03-force-update-visible-install.md`.

## [1.0.15] - 2026-08-03

### Fixed

- **Same account on two Windows machines no longer floods
  `PermissionError` for the other PC's profile paths.** Account-synced
  folders like `C:\Users\<other>\AppData\Local\Camxora\...` are rejected
  *before* any `mkdir` (workspace defaults, filesystem helpers, pending
  music downloads), replaced with this machine's local defaults, and logged
  once as a quiet warning. Shared drives (`D:\`, `E:\SUNO`, etc.) stay as-is
  when usable. See `docs/changelog/2026-08-03-cross-machine-path-locality.md`.
- **Flaky pydantic import crash on startup could exhaust a single retry.**
  Launcher now retries up to 4 times with growing backoff, clears partial
  imports between attempts, writes a recovery line when a later attempt
  succeeds, and falls back to extra crash-log locations if `%LOCALAPPDATA%`
  is unwritable.
- **Spectrum / logo / lightning preview drag left a ~6% gap at the top and
  bottom.** Drag clamp `margin_frac` was still `0.06` on the release line;
  the flush-edge fix (`0.0`) from `feat/lightning-layers` never landed here.
  Centers can now sit flush on the preview edges. See
  `docs/changelog/2026-08-03-preview-drag-flush-edges.md`.
- Includes everything from **1.0.14** (Continue → Merge no longer re-gated
  on export background PNG / catalog template).

## [1.0.14] - 2026-08-02

### Fixed

- **Continue → Merge re-gated on export readiness** (background PNG + catalog
  template), so merge failed with a vague “missing MP4s, image assets, or a
  catalog template” even when MP4s were ready. Merge now uses a merge-only
  candidate (run folder + branch). Export still reports the specific readiness
  failure; API-recovery toasts no longer claim “resuming” when nothing starts.
  See `docs/changelog/2026-08-02-merge-skip-export-readiness.md`.

## [1.0.13] - 2026-08-01

### Fixed

- **Login screen always showed a "Production API"/"Sandbox API"/etc. badge,
  even in production installers.** The main app shell already hid this badge
  for production builds, but the login screen had its own fallback label that
  unconditionally displayed the resolved environment — including the literal
  text "Production API" — to every end user. The login footer badge is now
  hidden outright for production builds (matching the rest of the app) and is
  only shown for sandbox/dev/local builds, for internal testers. See
  `docs/changelog/2026-08-01-hide-login-env-badge-production.md`.

## [1.0.12] - 2026-08-01

### Fixed

- **"Change Run Folder & Resume" wrote files flat into the picked folder
  instead of recreating the channel/date-album structure.** The picked
  folder is now treated as a base directory: the row's existing
  `{channel}/{date}_{album}` subfolder names are recreated underneath it
  before any MP3s or images are re-downloaded, matching exactly what the
  normal Generate pipeline creates for a new batch. See
  `docs/changelog/2026-08-01-run-folder-recovery-missing-subfolders.md`.

## [1.0.11] - 2026-08-01

### Fixed

- **"Change Run Folder & Resume" left already-submitted songs stuck retrying
  the old (full) folder forever.** Any song already sent to Suno before the
  folder change kept its original snapshotted download path even after the
  row was moved, so the background download sync spammed
  `Not enough free disk space to download MP3, skipping: <old path>` every
  ~5 seconds indefinitely — once per still-pending song in that album, on
  every poll — with no new folder or files ever created for those songs at
  the new location. The recovery flow now repoints each song's tracked
  download state (`output_dir`/`downloaded`) to the new folder as part of
  the move, whether its own re-download succeeded or failed, so the
  background sync stops targeting the dead path. See
  `docs/changelog/2026-08-01-run-folder-recovery-stale-output-dir.md`.

## [1.0.10] - 2026-08-01

Rebuild of 1.0.9 with no desktop code changes — pairs the client with a
same-day **backend** hotfix (`platform_api`) for a production incident: with
2 API workers, every worker independently ran `alembic upgrade heads` on
startup, racing DDL against the other worker's connections and causing a
~30 minute burst of `500` errors across nearly every screen right after a
deploy. Fixed server-side with a Postgres advisory lock serializing startup
migrations across workers; already deployed to sandbox and production. See
`docs/changelog/2026-08-01-migration-worker-race-incident.md` (platform API
repo). Desktop version bumped for release tracking/support purposes only.

## [1.0.9] - 2026-08-01

### Added

- **Change Run Folder & Resume**: right-click a Progress row → "Change Run
  Folder & Resume…" to move a batch/channel to a new folder (e.g. off a
  full/bad drive) and re-download already-successful MP3s (Suno URL first,
  Backblaze fallback) and images there, without re-drafting lyrics/title/album
  or re-requesting Suno generation. Auto-continues the pipeline from where it
  left off after the move completes.
- Disk-space guard (`shared/lib/disk_space.py`, 200MB floor): workspace path
  defaults self-heal off a low-space drive, and MP3 downloads pre-check free
  space, verify written file size against content length, and clean up 0-byte
  leftovers instead of silently producing empty files.
- Async `ProfileMediaCacheWorker` for Settings profile-media downloads —
  removed UI-blocking synchronous network calls that could hang the Settings
  page.
- Bounded one-attempt retry on `PlatformClient.request_bytes()` GET requests
  for transport-level errors ("peer closed connection", timeouts).

### Fixed

- Cross-machine `PermissionError`/`FileNotFoundError`: account-level settings
  no longer propagate one machine's absolute local paths to another — invalid
  synced paths self-heal to the current machine's own defaults.
  `ensure_directory()` caches known-uncreatable paths to avoid repeated
  blocking syscalls on the UI thread (previously caused Settings-page hangs).
- Startup hardening: global exception hooks and a bounded import-retry (with
  module cache clearing) for transient `TypeError: 'NoneType' object is not
  subscriptable`-style failures during early boot.
- Redundant "Saving music defaults..." status flashing fixed to a single
  message per save cycle.

### Changed

- Ported the visualizer/spectrum GPU-rendering overhaul (session presets,
  particle styles, encode pipeline hardening for low-VRAM GPUs) onto the
  current release line.

## [1.0.0] - 2026-07-26

First official production release of the Camxora desktop studio.

### Added

- Music workspace: batch automation (drafts, Suno, album images), History, and Progress export/merge pipeline
- Video studio with GPU visualizer export for long and reel outputs
- Preferences, diagnostics sync, and software-update support
- Production API endpoint (`https://api.camxora.com/api/v1`) and portal (`https://app.camxora.com`)

### Notes

- Sandbox builds remain separate; this installer does not talk to sandbox
- GPU export audio-analysis hardening for low-VRAM / dual-Xeon PCs is documented under `docs/FOLLOWUPS_DESKTOP_GPU_EXPORT.md` (validation held)

## [0.4.3] - 2026-07-25

### Fixed

- **Export stuck on Analyzing audio (1050 Ti / dual Xeon):** cap OpenBLAS/MKL threads during librosa analysis, analyze at 22.05 kHz, reuse onset envelope for beat detection, and emit Loading/Spectrum/Onset/Beats progress so the UI moves
- **Low-GPU parallel export:** GTX 1050 Ti-class (`low` tier) forces pipeline Export workers to 1 even if Preferences is higher

## [0.4.2] - 2026-07-25

### Added

- **Export failure diagnostics:** pipeline/manual export failures persist renderer crash tails (traceback / OpenGL / ffmpeg) into the app log ring buffer so Settings → Send diagnostics captures the real exit-code-1 cause, not only the short summary
- **Export milestone logging:** analyzing audio / cache / encoder stage messages are written to `[export]` logs to diagnose hangs on low-VRAM GPUs (e.g. GTX 1050 Ti)

## [0.4.1] - 2026-07-25

### Changed

- **Force update install + restart:** after download, the same update dialog shows install progress, then Camxora quits so a background helper can finish the silent Setup and relaunch the app (fixes installers dying with the old process / Setup.exe being deleted too early)
- **Update dialog progress:** transparent track + brand purple gradient fill (`#7466F1` → `#A259FF`) instead of cyan on a dark bar

## [0.4.0] - 2026-07-25

### Added

- **Music Mood:** Automation Mood dropdown + Shuffle (persists `defaultMoodId` / `shuffleMood`); batch create sends `mood_id` / `shuffle_mood`; History Mood column; Settings → Moods library (Camxora + user-owned prompts)
- **History Rewrite album 1 / album 2 / title:** right-click regenerates Primary/Secondary album or a song title even after Suno success (bills one album/title draft slot; does not change lyrics or song status). On `suno_failed` / `draft_ready`, **Rewrite title** auto-queues Suno with the new title
- **History batch Rewrite lyrics:** right-click **Rewrite lyrics (N songs)** runs polish→Suno for failed songs with usable lyrics (skips corrupt); optional **Rewrite this song**
- **History status multi-select:** Status filter is a checkable menu (Success / Failed / Pending); pick any combination (OR). Empty selection = All statuses
- **Delete failed batch:** History right-click **Delete failed batch** removes eligible batches (no Suno success/pending audio) after confirm so you can recreate with the correct description
- **Progress right-click Cancel:** Operational rows context menu includes **Cancel Active Export/Merge** to stop the single local pipeline job (or clear stuck busy state) so another **Start Export** can run
- **Music History filters:** Status + Batch dropdown; calendar filter; Show all; fetches up to history window (API max 100)
- **Pipeline Recover failed:** History button scans loaded failures — retry drafts, rewrite→Suno on content-policy rejects, retry other Suno fails
- **Pipeline helper agent (background):** shell coordinator auto-scans history and recovers failed drafts/Suno (cooldown + per-session caps)
- **REQ-2.3 / 2.4 / 2.5 / 3.5 export stack:** GPU spectrum bars, pipelined encode writer, ExportCoordinator, NativeEncodeBridge NVENC, GPU tier helper, shell app thread registry, encode throughput Phase 2a–2e
- Manual export billing (`video_manual`) with refunds on technical fail; Dashboard remaining card + weekly usage chart

### Changed

- **Native NVENC (pipelined NV12):** API v2 `camxora_eb_submit_nv12` + OpenCV pack on writer thread; `CAMXORA_NATIVE_ENCODE=1` selects native export
- **Dashboard weekly chart:** QPainter chart (replaces Qt Charts) for smoother scrolling
- Encode throughput Phase 2c–2e speed-mode tradeoffs; KPI labels: Studio Exports, Manual Exports, YouTube Uploads
- **Rebuild / Force Regenerate MP4:** honor Music → **Auto Merge** after export (same as auto-video)

### Fixed

- **Music plan Image total overcount:** album image estimate is per batch/channel (BG+TH), not N jobs × every song
- **Music plan summary UI:** compact framed estimate under Generate
- **Quit disconnect warnings / quit-safe auto-video:** coordinators disconnect cleanly; no empty-name QThread destroy on close
- **History date filter:** inverted From>To auto-swaps; client-side filter; strict planned-run or created day (no `updated_at` reopen); Last batch ignores date range
- **Calendar arrow changing month:** shell date pickers open calendar popup only (no month step)
- **Lyric rewrite quality gate + mood align:** trim corrupt tails; mood+title+structure context; pipeline helper smart recovery
- **History scroll jump:** poll refresh no longer jumps selection
- **Daemon export cancel / hang / Stop Exporting / Start Merging queue:** cancel kills daemon+ffmpeg tree; cooperative cancel; Stop pauses auto until manual start; Start Merging queues over settings/auto-export; Continue Progress prefers merge when MP4s exist
- **Settings path Open:** `path_row` ignores `clicked(bool)` so Open no longer passes False
- **Video template save / Music Suno retry / export quit teardown / GPU spectrum / visualizer daemon argv** (see prior unreleased notes)

## [0.3.0] - 2026-07-19

### Added

- **Phase 1 export performance:** audio analysis disk cache, warm visualizer daemon, export quality tiers (Draft / Standard / Master), NV12 pipe for fast exports, async double-buffered framebuffer readback
- Export footer shows active codec (NVENC vs CPU x264) and pipe format during encode
- **Tier** control on Video export panel; pipeline auto-export defaults to **Draft** (720p, very fast)

### Changed

- Pipeline and export defaults use **fast** speed mode; manual single export skips spawn throttle
- Export path removes redundant FFmpeg CPU vflip and disables MSAA on export (preview unchanged)

### Fixed

- GPU export progress is monotonic through init (no reset after encoder start)
- Second export of the same MP3 reuses cached STFT analysis instead of re-running librosa

## [0.2.5] - 2026-07-19

### Fixed

- GPU video export progress no longer sits at 0% with a frozen "Initializing GPU renderer..." message; the Progress workspace shows live status (OpenGL, assets, audio analysis, encoder prep) and overall percent advances during multi-track exports

## [0.2.4] - 2026-07-19

### Fixed

- Progress table no longer shows stale text in empty rows after refresh (clearContents + 
emoveCellWidget in operational rows card)
- Packaged builds read `resources/app-version.txt` when frozen so the footer version badge matches the installer (not stale metadata)
## [0.2.3] - 2026-07-19

### Added

- Footer version badge (`v0.2.3`) next to the Sandbox API badge so testers can confirm which build is running
- Bidirectional progress sync: local run-folder truth for export start + background push to `POST /progress/sync-local` after images/export
- Progress export readiness checklist in the footer (run folder PNGs, MP3s, profile template, catalog, auth, `/progress` load)
- **Start Export** button on pending export rows (same path as Rebuild MP4)
- MP3 on-disk naming helpers (`_OK.mp3` / `_Alt.mp3`) in validation messages

### Fixed

- Stale video export state no longer blocks Force Regenerate / Rebuild MP4 with “pipeline already running” when no worker is alive
- Auto-video uses local disk readiness instead of stale API metadata; orchestration poll failures surface in the footer

## [0.2.2] - 2026-07-19

### Added

- Suno sanitize metadata on history, learned-term cache, and online lyrics scan merge
- Desktop distribution: public release API, website `/download` + `/changelog`, admin installer upload

### Fixed

- Progress page Stage / Progress % / Export / Merge alignment when merged MP4s exist on disk (incl. long-only beattok runs) and when export workspace state is stale
- Stuck `suno_pending` reconciliation and one-pass auto-sanitize / auto-retry on sensitive Suno failures

### Changed

- Progress pipeline vocabulary standardized to Not started, Pending, In Progress, Completed; stage label **Converter → Export**, **Merger → Merge**
- Video pipeline automation / channel asset path handling improvements

## [0.2.1] - 2026-07-19

### Added

- Daily quota bank and credit-bypass billing controls (API + admin)
- Suno lyrics blocklist registry with admin UI and client highlighting
- Music genre catalog support for descriptions / streaming metadata
- Desktop single-instance guard (second launch focuses the existing window)
- Diagnostics opt-in sync from Settings (Log page hidden by default)
- First-launch install date for setup notifications
- Website home / features / services copy aligned to the desktop product

### Fixed

- Video template preview background now persists across save/reload
- Music preview duration shows correctly on first play
- Progress page no longer shows the Desktop Download Queue card
- Workflow / Progress polling quieter by default (manual refresh still logs)
- SpinBox up/down arrows visible again in the deep-blue theme
- Sample-pack URL import and streaming metadata sync for admin catalog
- SLAI gpt-5.6 text models and sandbox lyric probing

### Changed

- Channel pricing / plan-tier cost estimates and pricing keys
- Desktop packaging still ships FFmpeg + VC++ via Inno Setup

## [0.2.0] - 2026-07-16

### Added

- Initial sandbox desktop installer pipeline (PyInstaller + Inno Setup)
- Bundled FFmpeg and Visual C++ redistributable bootstrap
