# Changelog — Desktop app (`camxora_python`)

All notable changes to the **Camxora desktop app** (PySide6 client) are documented here.

This is **not** the changelog for user portal, music portal, admin portal, platform API, or website — see [`docs/CHANGELOG_GUIDE.md`](docs/CHANGELOG_GUIDE.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **Daemon export cancel:** Cancel Active Export now kills the warm visualizer daemon + ffmpeg process tree (previously only terminated one-shot subprocess jobs, so hung NVENC pipes left “already running” forever)
- **Continue Progress + API recovery:** Progress right-click **Continue Progress** advances the row’s next stage; auto-video clears stale busy/cooldowns and resumes when the API recovers after 502/outage
- **Export context menu:** **Start Export / Force Regenerate MP4 / Rebuild MP4 / Start Merging** appear on right-click of any Progress cell (not only the Export/Merge columns)
- **Export workers setting:** Preferences **Export Workers** (>1) now runs parallel one-shot visualizer subprocesses; the warm daemon stays single-job and is only used when workers=1 (billing/quota unchanged — charged once per batch by track count)
- **Export hang / cancel:** daemon/subprocess exports honor a cancel flag between frames and while blocked on the encode queue; Cancel waits ~2s for soft stop then kills the process tree; auto-video stays paused 45s after a user cancel so the same batch does not instantly restart
- **Stop Exporting:** Progress right-click **Stop Exporting** hard-stops the job and pauses auto-video + pipeline helper until you manually Start Export / Rebuild / Continue Progress / Start Merging on a row
- **Start Merging:** no longer fails with “still loading settings”; queued merge wins over auto-export. Continue Progress prefers merge when local MP4s already exist (Auto Merge still requires Music → Auto Merge). Merge no longer requires the Video catalog template — only exported MP4s in the run folder
- **Rebuild / Force Regenerate MP4:** no longer force `auto_merge=False`; after export they honor Music → **Auto Merge** the same as auto-video (export → merge)

### Added

- **Progress right-click Cancel:** Operational rows context menu includes **Cancel Active Export/Merge** to stop the single local pipeline job (or clear stuck busy state) so another **Start Export** can run
- **Music History filters:** Status (All/Success/Failed/Pending) + Batch dropdown; calendar filter matches planned run date **or** created day; Show all clears status/batch too; fetches up to history window (API max 100)
- **Pipeline Recover failed:** History button scans loaded failures — retry drafts, rewrite→Suno on content-policy rejects, retry other Suno fails
- **Pipeline helper agent (background):** shell coordinator auto-scans history and recovers failed drafts/Suno (cooldown + per-session caps)
- **REQ-2.3 slice 2 bars:** GPU spectrum covers mirror/symmetrical/drift/floating/ignition/neon (plus prior thin/grid); beads + waveforms remain CPU
- **REQ-3.5 NativeEncodeBridge NVENC:** Windows DLL encodes H.264 via runtime `nvEncodeAPI64.dll` (D3D11 + CPU NV12 upload, Annex-B); export path uses it when `CAMXORA_NATIVE_ENCODE=1` then remuxes audio with ffmpeg `-c:v copy`; pipe fallback on failure; `CAMXORA_NATIVE_ENCODE_STUB=1` keeps stub path
- **Export GPU tier helper:** `visualizer/export_gpu_tier.py` classifies NVIDIA GPUs as `low|mid|high` (`CAMXORA_GPU_TIER` override or nvidia-smi); low tier tightens Draft/Fast/Balanced particle caps and prefers yuv420p on `quality` speed (Master uncapped)
- **Shell app thread registry:** track/join background sync + push QThreads on quit (`shared/services/app_thread_registry.py`)
- **Encode throughput (Phase 2b):** fast/very_fast pipe uses planar `yuv420p` (OpenCV I420 + reusable dst) instead of interleaved NV12; CPU readback pool via `Buffer.read_into`; `CAMXORA_EXPORT_PIPE` override (`rgba|nv12|yuv420p`)
- **Encode throughput (Phase 2a):** OpenCV NV12 pack (~10× vs float NumPy), pack-on-writer overlap, deeper encode queue (default 6; `CAMXORA_ENCODE_QUEUE`), NVENC `-tune ll` / `-zerolatency` for fast/very_fast; `CAMXORA_ENCODE_METRICS` reports pack avg
- **REQ-2.3 GPU spectrum (slice 1):** optional export bar path via FFT 1D texture + instanced draw; `CAMXORA_GPU_SPECTRUM=1` enables, default off with CPU fallback
- **REQ-2.5 ExportCoordinator:** unified manual export API (`start_export`, `cancel_export`, `on_progress`) routing in-process GL → daemon → subprocess with `ExportGate` enforcement
- **REQ-2.4 pipelined encode writer:** bounded queue + writer thread between GPU readback and ffmpeg stdin; `CAMXORA_PIPELINED_ENCODE=0` restores sync writes; `CAMXORA_ENCODE_METRICS=1` reports p95 block times
- Manual export billing (`video_manual`) with refunds on technical fail; user stop keeps completed + in-progress, refunds never-started only
- Dashboard remaining card: **X of Y left**, account daily track-export/merge caps; weekly usage soft curves; zero series dimmed in legend

### Changed

- **Native NVENC (pipelined NV12):** API v2 `camxora_eb_submit_nv12` + OpenCV pack on `camxora-native-encode` writer thread; `CAMXORA_NATIVE_ENCODE=1` again selects native export (was gated off for sync RGBA slowness)
- **Dashboard weekly chart:** drop Qt Charts (`QSplineSeries` + animations) for a cached QPainter chart — fixes sticky/laggy dashboard scrolling and shell-wide jank

- **Encode throughput (Phase 2e):** Manual Export billing is async (UI no longer stalls 1–2s); app close mid-export joins export QThreads in `closeEvent`; unset Speed defaults to Fast; Balanced skips spectrum glow (Master unchanged); GPU bar path covers thin-lines / signal-needles / grid-steps / pixel-bars
- **Encode throughput (Phase 2d):** export-only speed-mode tradeoffs for heavy templates — skip/reduce spectrum glow passes and cap particle count/spawn on Draft/Fast/Balanced (Master untouched); Bass Drive-class templates should close the gap vs Beattok without regressing light templates
- **Encode throughput (Phase 2c):** Balanced/draft speed modes use planar `yuv420p` pack-on-writer (same as fast); ffmpeg `-thread_queue_size 64` + one-frame stdin bufsize; drop duplicate per-frame FFT fetch after 60 Hz smooth advance
- Fast exports tag ffmpeg `-color_range tv` for OpenCV BT.601 limited-range YUV (`yuv420p` default; `nv12` override still available); explicit `quality` speed keeps RGBA/`pc`
- KPI labels: Studio Exports, Manual Exports, YouTube Uploads

### Fixed

- **Settings path Open:** `path_row` ignores `QPushButton.clicked(bool)` so Open no longer passes `False` into `_open_path_field` (`'bool' object has no attribute 'text'`)
- **Video template save:** unlinked templates now upsert to the server (first channel profile); link in Settings for pipeline use
- **Music Suno/draft retry:** no longer crashes on `MusicHistoryListResponse.rows` after retry succeeds
- **VideoManualExportWorker quit:** block window close until export cancel/join finishes (no batch chain during teardown); last-resort terminate if still stuck
- **PushNotificationWorker quit:** close active WebSocket on `request_stop` (was blocked up to 65s in `recv`) so mid-export close no longer logs `QThread: Destroyed while thread 'PushNotificationWorker' is still running`
- **Quit mid-export panel refresh:** `any_video_pipeline_threads_running` no longer raises when a `deleteLater`'d `VideoManualExportWorker` wrapper remains in the tracker; untrack before `deleteLater`
- **Empty-name QThread on mid-export quit:** shell sync/push/orchestration workers were unnamed + widget-parented; close now stops coordinators and joins `app_thread_registry` before tearing down the window (export workers were already named)
- **App quit mid-export QThread teardown:** `RootWindow.closeEvent` + named export workers so close no longer logs `QThread: Destroyed while thread '' is still running`
- **Stop Export QThread teardown:** join with timeout + `deleteLater` (detach lingering workers) so cancel no longer logs `QThread: Destroyed while thread is still running`
- **GPU spectrum export:** color texture size/dtype mismatch (`f1` vs RGBA32F) in `register_layer()`; benchmark A no longer crashes with `CAMXORA_GPU_SPECTRUM=1`
- Visualizer daemon argv normalization preserves empty `--logo` values (fixes immediate export exit code 1)
- GPU export async readback uses correct moderngl `ctx.buffer(reserve=…)` allocation

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
