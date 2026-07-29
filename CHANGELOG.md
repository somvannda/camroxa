# Changelog — Desktop app (`camxora_python`)

All notable changes to the **Camxora desktop app** (PySide6 client) are documented here.

This is **not** the changelog for user portal, music portal, admin portal, platform API, or website — see [`docs/CHANGELOG_GUIDE.md`](docs/CHANGELOG_GUIDE.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

### Changed

### Fixed

- Spectrum rabbit ears (Inward Bar Growth): stop style-hydrate from forcing gravity back to Outward; picking Inward on a linear layer auto-enables Circle Raise 180°. See `docs/changelog/2026-07-29-spectrum-rabbit-ears-fix.md`.
- Spectrum inspector: restore missing `style` bind in `bind_draft` (fixed Video page crash `NameError: style is not defined`).
- Spectrum: vivid built-in/stacked colors (no white wash), free spectrum position vs logo unless Attach is on, and Audio knobs that actually work on desktop. See `docs/changelog/2026-07-29-spectrum-vivid-position-audio.md`.
- Video templates: unsaved style/draft edits are session-only (reset on restart); Save keeps a restorable `originalTemplate`. See `docs/changelog/2026-07-29-session-only-template-edits.md`.
- Spectrum bar controls: Global Height Gain vs Bar Length are labeled separately (not duplicates); Bar Width reserves a clear gap vs density; density max raised to 192. See `docs/changelog/2026-07-29-spectrum-bar-width-density-separation.md`.
- Spectrum live preview now paints **all** gradient color stops (was first→last only), so multi-stop palettes look rich around circular rings. See `docs/changelog/2026-07-29-spectrum-multi-stop-gradient-preview.md`.
- Spectrum Layers: Up/Down reorder, clearer per-layer vs global labels, Add offsets ring size; curved Bottom (rabbit ears) grows inward. See `docs/changelog/2026-07-29-spectrum-layer-reorder-and-rabbit-ears.md`.
- Spectrum Phase 1: per-layer bar density (16-128), optional peak caps (gap/size/decay/color), solid base band render, and top-to-bottom bar gradient support. See `docs/changelog/2026-07-29-spectrum-phase1-peakcaps-density-solidband.md`.
- Spectrum preview/export fix: `solidBand` now derives color-row count from generated strip geometry, preventing mirrored curved waveform crashes from mismatched array lengths.
- Spectrum Layers: labeled Circle Form (180° / Full Circle 360°), Bar Growth, and Blend Mode; dampen glow wash; wire radial/circular/diagonal gradient directions. See `docs/changelog/2026-07-29-spectrum-circle-form-and-color-wash.md`.
- Spectrum peak caps: slice geometry to bar count when mirrored waveform closes the ring (fixes `113` vs `112` paintGL broadcast crash).
- Login UI: hide “No session found.” error pill when bootstrap detects missing saved session tokens.

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
