# WebGPU Export Migration Checklist

## 1. Goal

Replace the current Python-based video render/export path with a desktop-native WebGPU export pipeline while preserving useful orchestration behavior.

This migration must achieve:

- one visual render truth for preview and export
- `Manual Export` = current live preview state (WYSIWYG)
- `Pipeline Export` = saved template styling + runtime pipeline background asset
- no Python dependency in the render/export path
- worker-based folder export
- optional auto-merge
- optional shuffle-merge

## 2. Product Rules

### 2.1 Manual Export

- Uses the current live renderer draft
- Must export exactly what the operator sees in preview
- Does not require save-before-export
- Uses WebGPU as the render engine

### 2.2 Pipeline Export

- Uses saved template values for:
  - spectrum
  - logo settings
  - particles
  - background behavior settings
  - text overlays
  - output resolution
- Uses pipeline/runtime asset input for:
  - background image
- Uses saved logo asset/path for:
  - logo file source
- Uses WebGPU as the render engine
- Supports folder export with configurable workers
- Supports optional auto-merge
- Supports optional shuffle merge order

### 2.3 Shared Rules

- WebGPU is the only visual render engine
- FFmpeg remains the encoder/muxer
- Renderer preview and export must use the same resolved scene contract
- Python code may be referenced for behavior only, not used at runtime

## 3. Delivery Principles

- Make preview and export converge on one render truth before adding more features
- Keep domain ownership explicit: spectrum, background, logo, particles, text, atmosphere, postfx, audio-reactivity
- Keep orchestration separate from rendering
- Prefer small vertical slices that can be verified end-to-end
- Do not keep dual render paths longer than necessary

## 4. Milestones

| Milestone | Outcome | Status |
|---|---|---|
| WGX-M1 | Shared render contracts and export modes defined | pending |
| WGX-M2 | Shared scene builders for manual and pipeline export | pending |
| WGX-M3 | WebGPU offscreen frame export foundation | pending |
| WGX-M4 | Manual WYSIWYG export working end-to-end | pending |
| WGX-M5 | Pipeline WebGPU export working end-to-end | pending |
| WGX-M6 | Worker queue, merge, shuffle, and preferences | pending |
| WGX-M7 | Python export path removed | pending |
| WGX-M8 | Parity, performance, and release hardening | pending |

## 5. Workstreams

### 5.1 Render Contracts

- shared scene request
- shared asset resolution
- export mode boundaries

### 5.2 Scene Composition

- manual scene builder from live draft
- pipeline scene builder from saved template + runtime assets

### 5.3 WebGPU Export Runtime

- offscreen or hidden-window rendering
- deterministic frame stepping
- RGBA frame extraction

### 5.4 Encoding and Merge

- FFmpeg piping
- job progress
- merge orchestration

### 5.5 Queue and Preferences

- worker count
- queue lifecycle
- auto-merge
- shuffle-merge

### 5.6 Python Removal

- remove Python export/runtime entrypoints from active app flow

## 6. Detailed Checklist

### WGX-M1. Shared Render Contracts

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M1.1 | Create `ExportMode` contract with `manual` and `pipeline` | none | pending | Shared renderer/export contract |
| WGX-M1.2 | Add `ManualExportRequest` type carrying live draft-based payload | WGX-M1.1 | pending | Must not rely on saved template lookup |
| WGX-M1.3 | Add `PipelineExportRequest` type carrying template id, run dir, and runtime asset overrides | WGX-M1.1 | pending | Background override belongs here |
| WGX-M1.4 | Add `ResolvedRenderAssets` type for background, logo, audio, and output paths | WGX-M1.1 | pending | Shared by preview and export |
| WGX-M1.5 | Add `RenderOutputSettings` type for width, height, fps, and encode preset | WGX-M1.1 | pending | Resolution must come from template |
| WGX-M1.6 | Add a normalized `RenderSceneRequest` type used by preview and export | WGX-M1.2, WGX-M1.3 | pending | Main source-of-truth scene contract |
| WGX-M1.7 | Add IPC contract updates in renderer shared desktop types | WGX-M1.2, WGX-M1.3 | pending | Replace Python-centric assumptions |
| WGX-M1.8 | Add preload bridge methods for manual export and pipeline export | WGX-M1.7 | pending | Separate entrypoints for clarity |
| WGX-M1.9 | Document final ownership of background, logo, particles, spectrum, text, and resolution in this migration doc | WGX-M1.6 | pending | Keep scope unambiguous |
| WGX-M1.10 | Add contract unit tests for request validation and serialization | WGX-M1.6 | pending | Protect future refactors |

### WGX-M2. Shared Scene Builders

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M2.1 | Extract preview scene normalization into pure builder helpers | WGX-M1.6 | pending | Reduce UI-coupled logic |
| WGX-M2.2 | Create `buildManualRenderScene()` from live draft state | WGX-M2.1 | pending | Manual WYSIWYG source |
| WGX-M2.3 | Create `buildPipelineRenderScene()` from saved template + runtime background asset | WGX-M2.1 | pending | Pipeline source |
| WGX-M2.4 | Resolve background enabled/disabled behavior through shared scene builder | WGX-M2.2, WGX-M2.3 | pending | Must match preview behavior |
| WGX-M2.5 | Resolve logo asset path and logo behavior through shared scene builder | WGX-M2.2, WGX-M2.3 | pending | Separate asset vs style |
| WGX-M2.6 | Resolve particles settings through shared scene builder | WGX-M2.2, WGX-M2.3 | pending | Preserve preview parity |
| WGX-M2.7 | Resolve text overlays and timing through shared scene builder | WGX-M2.2, WGX-M2.3 | pending | Shared timeline contract |
| WGX-M2.8 | Resolve output resolution from saved template in shared builder | WGX-M2.2, WGX-M2.3 | pending | Manual export also uses template resolution |
| WGX-M2.9 | Add tests proving manual scene builder reflects unsaved draft changes | WGX-M2.2 | pending | Core manual-export guarantee |
| WGX-M2.10 | Add tests proving pipeline scene builder ignores unsaved draft changes | WGX-M2.3 | pending | Core pipeline guarantee |

### WGX-M3. WebGPU Export Runtime Foundation

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M3.1 | Choose export rendering host strategy: hidden renderer window or offscreen surface | WGX-M2.10 | pending | Recommend hidden renderer for parity |
| WGX-M3.2 | Create export runtime host bootstrap in Electron main | WGX-M3.1 | pending | Non-Python runtime |
| WGX-M3.3 | Create export renderer entry module in renderer code | WGX-M3.1 | pending | Dedicated export boot path |
| WGX-M3.4 | Reuse existing WebGPU renderer setup in export mode | WGX-M3.3 | pending | Avoid second visual implementation |
| WGX-M3.5 | Replace RAF-driven preview stepping with explicit frame-index stepping in export mode | WGX-M3.4 | pending | Deterministic export timing |
| WGX-M3.6 | Add offscreen frame render API returning RGBA data | WGX-M3.5 | pending | Bridge to FFmpeg |
| WGX-M3.7 | Add export clock based on frame index and fps | WGX-M3.5 | pending | Shared deterministic timeline |
| WGX-M3.8 | Ensure background, spectrum, logo, particles, text, and postfx render in export mode | WGX-M3.6 | pending | Same scene graph as preview |
| WGX-M3.9 | Add export runtime diagnostics for frame timing and render failures | WGX-M3.6 | pending | Needed before batching |
| WGX-M3.10 | Add smoke test rendering a fixed frame to raw RGBA | WGX-M3.6 | pending | First proof of export runtime |

### WGX-M4. Manual Export End-To-End

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M4.1 | Add `Export Current Preview` command in workspace actions | WGX-M1.8 | pending | Explicit manual export UX |
| WGX-M4.2 | Build live draft payload from current preview state | WGX-M2.2 | pending | No save required |
| WGX-M4.3 | Pass manual export payload through preload and main process | WGX-M4.1, WGX-M1.8 | pending | End-to-end desktop path |
| WGX-M4.4 | Feed manual export scene into WebGPU export runtime | WGX-M3.10, WGX-M4.3 | pending | Same scene request |
| WGX-M4.5 | Add FFmpeg encode path for one audio track + WebGPU frames | WGX-M4.4 | pending | First MP4 output |
| WGX-M4.6 | Report progress back to workspace UI during manual export | WGX-M4.5 | pending | Frame-based progress |
| WGX-M4.7 | Add cancel action for manual export | WGX-M4.6 | pending | Must stop render and encoder |
| WGX-M4.8 | Add output validation after manual export completes | WGX-M4.5 | pending | Size, duration, resolution |
| WGX-M4.9 | Add tests proving unsaved preview changes are present in manual export scene | WGX-M4.2 | pending | WYSIWYG contract |
| WGX-M4.10 | Add visual parity test for selected timestamps between preview and manual export | WGX-M4.5 | pending | Pixel-tolerance is acceptable |

### WGX-M5. Pipeline Export End-To-End

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M5.1 | Add pipeline export request builder using saved template + pipeline background input | WGX-M2.3 | pending | Manual and pipeline must stay separate |
| WGX-M5.2 | Replace Python-start pipeline export command with WebGPU export command | WGX-M3.10 | pending | Remove Python dependency from active export path |
| WGX-M5.3 | Build folder scan logic for loaded audio directory | WGX-M5.1 | pending | Source of batch queue |
| WGX-M5.4 | Implement deterministic input ordering rule for folder export | WGX-M5.3 | pending | Numeric-first or chosen final rule |
| WGX-M5.5 | Resolve per-item background image override from pipeline asset source | WGX-M5.1 | pending | Pipeline background only |
| WGX-M5.6 | Resolve saved logo asset/path for pipeline export | WGX-M5.1 | pending | Saved logo file |
| WGX-M5.7 | Render one pipeline job through WebGPU export runtime | WGX-M5.2, WGX-M5.5, WGX-M5.6 | pending | Single-track pipeline proof |
| WGX-M5.8 | Add per-job progress events | WGX-M5.7 | pending | Queue UI integration |
| WGX-M5.9 | Add skip-existing-valid-output option | WGX-M5.7 | pending | Keep useful Python-era behavior |
| WGX-M5.10 | Add retry-failed-item command | WGX-M5.7 | pending | Operator recovery |
| WGX-M5.11 | Add tests proving pipeline export uses saved template behavior, not live unsaved draft | WGX-M5.7 | pending | Core product rule |
| WGX-M5.12 | Add tests proving pipeline background overrides only background image, not template style settings | WGX-M5.7 | pending | Must match alignment |

### WGX-M6. Workers, Queue, Merge, Preferences

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M6.1 | Create desktop-native export coordinator service | WGX-M5.7 | pending | Replaces Python orchestration |
| WGX-M6.2 | Create desktop-native export worker abstraction | WGX-M6.1 | pending | One render+encode unit |
| WGX-M6.3 | Add worker pool scheduling with max concurrency from Preferences | WGX-M6.2 | pending | Python-like useful behavior |
| WGX-M6.4 | Add queue item states: pending, running, completed, failed, cancelled, skipped | WGX-M6.1 | pending | Standardized UI |
| WGX-M6.5 | Add batch-level progress aggregation | WGX-M6.4 | pending | Queue summary |
| WGX-M6.6 | Add per-item cancellation | WGX-M6.4 | pending | Operator control |
| WGX-M6.7 | Add full-batch cancellation | WGX-M6.4 | pending | Operator control |
| WGX-M6.8 | Build desktop-native merge service using FFmpeg concat | WGX-M6.1 | pending | Long/reel future-safe |
| WGX-M6.9 | Add `autoMerge` on/off setting | WGX-M6.8 | pending | User-configurable |
| WGX-M6.10 | Add `shuffleMerge` on/off setting | WGX-M6.8 | pending | User-configurable |
| WGX-M6.11 | Implement shuffle logic only for merge order, not render order | WGX-M6.10 | pending | Important distinction |
| WGX-M6.12 | Emit merge order manifest/log file | WGX-M6.11 | pending | Auditability |
| WGX-M6.13 | Add Preferences UI/settings persistence for worker count | WGX-M6.3 | pending | Current source-of-truth |
| WGX-M6.14 | Add Preferences UI/settings persistence for auto-merge and shuffle-merge defaults | WGX-M6.9, WGX-M6.10 | pending | Global defaults |
| WGX-M6.15 | Add tests for worker concurrency, queue transitions, merge order, and shuffle behavior | WGX-M6.14 | pending | Protect coordinator behavior |

### WGX-M7. Python Removal

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M7.1 | Identify all Electron main code paths that launch Python for video export or preview | WGX-M5.12 | pending | Inventory first |
| WGX-M7.2 | Replace active export Python invocations with WebGPU export coordinator | WGX-M7.1, WGX-M6.15 | pending | Main cutover |
| WGX-M7.3 | Freeze legacy Python preview/export IPC APIs | WGX-M7.2 | pending | Prevent new coupling |
| WGX-M7.4 | Remove renderer-side assumptions that export progress comes from Python CLI events | WGX-M7.2 | pending | New desktop event model |
| WGX-M7.5 | Remove preload APIs that only exist for Python video export once unused | WGX-M7.4 | pending | Cleanup |
| WGX-M7.6 | Remove Python render/export runtime requirement from app startup and preferences | WGX-M7.5 | pending | Python-free build target |
| WGX-M7.7 | Update technical docs to state WebGPU is the single render engine | WGX-M7.6 | pending | Product truth |
| WGX-M7.8 | Add migration note for old Python-based export assumptions | WGX-M7.7 | pending | Team handoff |

### WGX-M8. Parity, Performance, and Hardening

| ID | Task | Depends On | Status | Notes |
|---|---|---|---|---|
| WGX-M8.1 | Build a frame parity test set for background, spectrum, logo, particles, and text | WGX-M4.10, WGX-M5.12 | pending | Core WYSIWYG proof |
| WGX-M8.2 | Build deterministic audio-reactivity sampling tests for preview and export | WGX-M3.10 | pending | Same timestamp, same data |
| WGX-M8.3 | Build resolution/fps correctness tests for export output | WGX-M4.8, WGX-M5.7 | pending | Template-driven resolution |
| WGX-M8.4 | Add export failure-path tests for missing assets, FFmpeg unavailable, and invalid output dirs | WGX-M6.15 | pending | Hardening |
| WGX-M8.5 | Add performance smoke tests for worker concurrency settings | WGX-M6.15 | pending | Avoid unstable defaults |
| WGX-M8.6 | Add telemetry for render throughput, encode throughput, and queue latency | WGX-M6.15 | pending | Release diagnostics |
| WGX-M8.7 | Add release acceptance checklist for Python-free export | WGX-M8.1, WGX-M8.6 | pending | Final sign-off |
| WGX-M8.8 | Validate packaged app behavior on target Windows environments | WGX-M8.7 | pending | Real deployment proof |

## 7. First Recommended Delivery Slice

Deliver the migration in the smallest useful vertical slice first:

### Slice A

- WGX-M1.1 to WGX-M1.10
- WGX-M2.1 to WGX-M2.10

Outcome:

- shared contracts exist
- manual and pipeline scenes are clearly separated

### Slice B

- WGX-M3.1 to WGX-M3.10
- WGX-M4.1 to WGX-M4.8

Outcome:

- manual WebGPU export works end-to-end
- first WYSIWYG proof exists

### Slice C

- WGX-M5.1 to WGX-M5.12
- WGX-M6.1 to WGX-M6.7

Outcome:

- pipeline WebGPU export replaces Python export for single and multi-track jobs

### Slice D

- WGX-M6.8 to WGX-M6.15
- WGX-M7.1 to WGX-M7.8

Outcome:

- merge, shuffle, preferences, and Python removal complete

### Slice E

- WGX-M8.1 to WGX-M8.8

Outcome:

- parity and release hardening complete

## 8. Acceptance Criteria

The migration is complete when all of the following are true:

- Manual export matches the live preview for the same state and timestamp
- Pipeline export uses saved template styling and pipeline-supplied background image
- Spectrum, logo, particles, background behavior, text, and resolution resolve correctly in both modes
- No Python process is launched for preview or export
- Worker count follows Preferences
- Auto-merge and shuffle-merge behave exactly as configured
- Export queue, cancellation, retry, and failure handling are desktop-native
- Docs and build assumptions no longer describe Python as the active render/export engine
