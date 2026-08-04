# Changelog — Desktop app (`camxora_python`)

All notable changes to the **Camxora desktop app** (PySide6 client) are documented here.

This is **not** the changelog for user portal, music portal, admin portal, platform API, or website — see [`docs/CHANGELOG_GUIDE.md`](docs/CHANGELOG_GUIDE.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Preview HDR bloom path (flagged).** Offscreen threshold / blur pyramid /
  tonemap into the Qt preview FBO with opaque alpha. Default off
  (`CAMXORA_PREVIEW_HDR_BLOOM=0`). See
  `docs/changelog/2026-08-04-preview-p4-hdr-bloom.md`.
- **HDR bloom design (preview/export).** Planned float intermediate + bloom +
  tonemap pipeline documented; P4.2 implements preview behind the flag. See
  `docs/PREVIEW_HDR_BLOOM_DESIGN.md`.

### Changed

### Fixed

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
