# Package Ownership Map

## Purpose
Define the intended responsibility of each top-level package in `python_app/` so future refactors and new features follow consistent enterprise-grade ownership boundaries.

---

## Ownership Matrix

| Package | Primary Role | May Depend On | Must Not Depend On | Notes |
|---|---|---|---|---|
| `app/` | Application shell, bootstrap, composition, dependency wiring | `views/`, `features/`, `models/`, lightweight app helpers | direct feature business logic, deep DB workflow code, provider-specific service code | `MainWindow` must shrink toward shell-only behavior |
| `views/` | Widget construction, page layout, UI-only behavior | Qt, `models/`, reusable UI helpers, coordinator/host interfaces | `database/`, provider services, complex workflow orchestration | Views may emit intents but should not own use-cases |
| `features/` | Feature ownership boundary, coordinators, feature-facing contracts | `services/`, `database/`, `models/`, `views/` bridges as needed | unrelated feature internals, raw app-shell state mutation | Best place to absorb logic extracted from `MainWindow` |
| `controllers/` | Transitional workflow helpers / orchestration utilities | `services/`, `database/`, `models/` | direct widget construction, broad shell ownership | Can be gradually folded into richer `features/*` coordinators |
| `services/` | External integrations, provider clients, ffmpeg/process helpers | stdlib, third-party libs, `models/`, utility modules | Qt views, page host logic, DB UI policy | Must remain UI-independent |
| `database/` | Persistence, queries, migrations, storage adapters | stdlib, DB libs, `models/` where necessary | Qt, view layer, provider API logic | Prefer feature-specific DB adapters over random cross-module access |
| `models/` | Domain shaping, normalization, defaults, immutable-ish structures | stdlib only where possible | Qt, DB connections, network/service calls | Should stay as pure as possible |
| `visualizer/` | Rendering subsystem, preview/export runtime | stdlib, rendering libs, narrow DTO/config contracts | UI host orchestration, DB access, app-shell state decisions | Treat as subsystem with explicit boundary |
| `tools/` | One-off engineering/refactor utilities | stdlib, repo file access | runtime app imports as execution dependencies | Not part of production runtime |
| `utils/` | Small generic helpers shared safely | stdlib, narrow helper libs | feature-specific policy, UI workflow logic | Keep this small and generic |
| `docs/` | Planning, design, continuity, audit artifacts | none | n/a | Acts as long-term refactor memory |

---

## Package-by-Package Responsibility

### `app/`
Owns:
- bootstrap sequence
- `MainWindow` composition
- dependency wiring
- top-level theme/resources/logging setup
- app-level event bus bootstrapping

Does not own long-term:
- YouTube workflow policy
- template persistence rules
- image/music job orchestration policy
- complex queue retries or polling policies

### `views/`
Owns:
- building widgets and pages
- reusable widget composition
- page-specific layout structure
- local display updates
- lightweight view-only interactions

Does not own:
- DB reads/writes
- OAuth flow decisions
- provider-specific error handling
- background worker lifecycle management

### `features/`
Owns:
- feature coordination
- use-case orchestration
- state transitions for a feature
- validation before delegating to DB/services
- feature-specific contracts and adapters

Current sub-packages and ownership:

| Sub-package | Coordinator | Status | Key Methods |
|---|---|---|---|
| `auto_video/` | `AutoVideoCoordinator` | Active | `resolve_channel_plan`, `build_export_progress_message`, `build_export_complete_message` |
| `merge/` | `MergeWorker` | Active | `merge(ffmpeg, mp4_paths, target_path)` |
| `persistence/` | `PersistenceCoordinator` | Active | DB bootstrap/hydration, settings patch, migrate+reload |
| `profiles/` | `ProfileCoordinator` | Delegated | Profile load/save orchestration delegated from host |
| `progress/` | `ProgressCoordinator` | Active | Progress row refresh, context-menu dispatch, queue actions |
| `templates/` | `VideoTemplateCoordinator` | Delegated | Template save/load/list orchestration delegated from host |
| `video_export/` | `VideoExportCoordinator` | Active | Export workflow, workspace state bridge |
| `youtube/` | `YouTubeCoordinator` | Active | OAuth, queue, upload, playlist, merged-output scan, tick orchestration, cancel-state, credential/metadata/thumbnail resolution, warning/retry logic |
| *(music)* | — | Future | Music generation enqueue, callback handling, batch state |
| *(image)* | — | Future | Image job enqueue, sample selection, generation refresh |

Remaining host-owned seams:
- `_run_one_youtube_upload_job` — ~85 lines of tightly coupled execution (DB calls, bus emissions, cancel checks)
- Profile/template `*_impl` methods — actual behavior still in host, coordinator is delegation boundary
- Deeper progress internals (merge routing, auto-video channel start) — partially extracted via `AutoVideoCoordinator`/`MergeWorker`

### `controllers/`
Current role:
- existing orchestration helpers for music/image flows

Target role:
- temporary bridge while coordination is moved into proper feature/application modules

Long-term expectation:
- either shrink substantially or be replaced by explicit feature coordinators/use-cases

### `services/`
Owns:
- Suno/music/image provider communication
- YouTube OAuth/upload service helpers
- video export helpers
- DPAPI or local secrets-related technical helpers
- process/ffmpeg integration helpers

Should expose reusable non-UI interfaces.

### `database/`
Owns:
- schema migrations
- CRUD/query helpers
- persistence loaders
- job tables / profile tables / template tables / upload tables

Should not become:
- business-rule engine
- UI formatting layer
- app-shell state manager

### `models/`
Owns:
- data defaults
- normalization
- config structure contracts
- reusable payload shaping

These modules should remain safe to use across all layers.

### `visualizer/`
Owns:
- preview rendering internals
- GPU render/export path
- audio-reactive visual logic
- low-level render timing behavior

Should interact through clear DTO/config interfaces rather than app shell internals.

---

## Ownership Rules for New Code

### Rule 1
If code touches Qt widgets directly, it probably belongs in `views/` or the app shell, not `services/` or `database/`.

### Rule 2
If code coordinates multiple dependencies to complete a user action, it belongs in `features/` or a future application layer, not in `MainWindow`.

### Rule 3
If code talks to an external API/tool/provider, it belongs in `services/`.

### Rule 4
If code owns persistence or query logic, it belongs in `database/`.

### Rule 5
If code exists only to normalize or shape data, it belongs in `models/`.

### Rule 6
If code is specific to rendering internals, it belongs in `visualizer/`, not in generic UI pages.

---

## Immediate Ownership Corrections Needed
- Extract profile/template `*_impl` bodies from `MainWindow` into coordinator-owned methods
- Reduce `views/*` reliance on host-implemented business methods
- Consider folding `controllers/` into richer `features/*` coordinators
- Plan music and image feature coordinators for next extraction wave

## Completed Ownership Corrections
- YouTube coordinator now owns OAuth, queue, upload lifecycle, playlist, merged-output, tick, cancel-state, credential/metadata/thumbnail resolution, warning/retry/compute logic
- Auto-video channel resolution extracted into `AutoVideoCoordinator` with `AutoVideoChannelPlan` dataclass
- MP4 merge logic extracted into `MergeWorker` (replaced deleted `_merge_mp4s`)
- Persistence coordinator owns DB bootstrap, hydration, settings patch, migrate+reload
- Progress coordinator owns row refresh, context-menu dispatch, queue action routing
