# Video Preview GPU + Reactivity Parity Plan

## 1. Scope

This document records the current `/app/video` renderer state, the remaining gaps, the Python ModernGL reference differences, and the next implementation plan.

This is intentionally runtime-focused.

Rules for the next improvement program:
- avoid UI changes unless a runtime capability cannot be controlled or verified without them
- do not add diagnostic noise or explanatory clutter to the operator UI
- prefer foundational improvements that remove future rework instead of shipping one-off fixes
- move frame-critical hot paths off the CPU wherever the platform realistically allows
- make preview and export converge toward one render truth

## 2. Executive Summary

The current Electron Video page already has a serious renderer foundation:
- explicit preview lifecycle and recovery
- WebGPU render path
- logarithmic spectrum mapping
- interpolation and smoothing
- beat-oriented reactive signals
- bloom/post-fx
- particles
- playback synchronization
- domain-isolated workspace architecture

The biggest remaining problems are not basic UI polish. They are renderer architecture and signal-processing quality:
- preview and export are not guaranteed 100% identical today
- audio reactivity is still weaker than the Python ModernGL reference because the current web preview depends on live `AnalyserNode` heuristics instead of a richer analyzed feature timeline
- there is no true peak-hold stage
- there is no real motion-blur pass
- particles are still CPU-simulated
- there is no adaptive performance governor for consistent 60-120 FPS
- some signal-processing logic still leaks through top-level preview code instead of living in a dedicated audio-analysis/runtime layer

## 3. Current Capability Matrix

### 3.1 Present

| Capability | Status | Current State | Notes |
|---|---|---|---|
| FFT input | present | Browser `AnalyserNode` FFT is used for live preview audio analysis | Present, but not as deterministic or information-rich as the Python offline analyzer |
| Beat-oriented reactivity | present | Bass / onset / transient-derived reactive features exist | Good baseline, but not yet reference-grade |
| Smoothing | present | Multiple smoothing layers exist across analyser, envelope, and reactive frame state | Needs consolidation into one owned signal pipeline |
| Interpolation | present | FFT bins are interpolated into log/perceptual bands | This part is already solid |
| Log frequency weighting | present | Current spectrum analysis is logarithmic instead of linear | Matches expected visualizer behavior |
| WebGPU rendering | present | Live preview renders through the WebGPU compositor | Strong foundation already in place |
| Bloom / glow | present | Bright-pass, blur, and composite bloom passes exist | Needs explicit quality-tier ownership |
| Particle rendering | present | Particle visuals are rendered in the preview | Simulation path is still CPU-bound |
| Gradient visuals | present-partial | Gradient output exists for spectrum layers | Gradient treatment is not yet fully shader-native |
| Audio playback sync | present | Preview transport is coordinated against playback state | Good enough for preview, but export parity is still separate |
| Frame telemetry | present | Preview frame timing and diagnostics exist | Not yet connected to adaptive quality decisions |

### 3.2 Partial

| Capability | Status | Current State | Gap |
|---|---|---|---|
| Beat detection quality | partial | Heuristic live beat detection exists | Python path has stronger offline beat/onset analysis |
| Gradient shader ownership | partial | Gradient colors are prepared partly on CPU and consumed by GPU | Should become fully render-graph-owned shading behavior |
| 60-120 FPS guarantee | partial | RAF loop and telemetry exist | No adaptive frame budget enforcement, no quality governor |
| GPU-first runtime | partial | Rendering is GPU-heavy | Several frame-critical transforms and all particle simulation remain CPU-heavy |
| Preview responsiveness | partial | Live edits update preview quickly | Some edits still depend on CPU-side prep that can spike or lag under load |
| Preview/export parity | partial | Same product intent, different engines | Preview uses WebGPU; export still runs Python/ModernGL subprocess |

### 3.3 Missing

| Capability | Status | Why It Matters |
|---|---|---|
| Peak hold | missing | Needed for more professional bar behavior, readability, and impact |
| Motion blur | missing | Needed for premium motion continuity and high-energy visual feel |
| GPU particle simulation | missing | Required for large counts and truly stable high frame rates |
| Adaptive quality / performance tiers | missing | Needed to hold smooth preview on weaker hardware |
| Unified preview/export renderer | missing | Required for true 100% parity |
| Dedicated GPU audio feature pipeline | missing | Required to remove repeated CPU-side frame shaping and increase reactivity quality |

## 4. Python Reference Findings

The Python renderer is still an important reference for audio feel.

### 4.1 What The Python Side Does Better Today

- Uses offline `librosa` analysis in `../python_app/visualizer/audio.py`
  - STFT
  - onset strength
  - beat tracking
- Uses precomputed vectorized log-bin mapping in `../python_app/visualizer/_spectrum_fast.py`
- Uses explicit smoothing kernels and deterministic offline frame lookup
- Has template schema support for `audioSettings.peakHold` in `../python_app/models/spectrum_model.py`
- Uses a dedicated export renderer path built around ModernGL for final video output

### 4.2 Why The Python Reactivity Feels More Professional

The Python path analyzes the whole song up front and then renders against a stable feature timeline. That gives it:
- more reliable beat timing
- cleaner onsets
- more stable band behavior
- less frame-to-frame randomness
- less dependence on browser audio-clock jitter

The current Electron preview instead derives reactivity live from `AnalyserNode` snapshots. That is cheaper to start, but it is not the strongest path for professional music-reactive visuals.

## 5. Hard Truths To Keep The Plan Honest

### 5.1 Not Everything Can Literally Leave The CPU

The renderer can and should become GPU-first, but not every responsibility belongs on the GPU:
- UI events remain CPU
- IPC remains CPU
- file I/O remains CPU
- audio decode/bootstrap remains CPU unless replaced by a native preprocessing path
- workspace/state orchestration remains CPU

The correct target is:
- no frame-critical visual shaping on CPU if the GPU can own it
- no repeated per-frame CPU loops for spectrum shaping, peak-hold, particle sim, or post-fx decisions
- CPU only prepares coarse control data and non-render orchestration

### 5.2 Preview And Export Are Not 100% The Same Today

They are not identical today because:
- live preview uses the Electron renderer WebGPU stack
- export still launches `python_app.visualizer.main`

That means exact visual parity is not guaranteed, even if both follow the same template schema.

## 6. Best Architecture

The best structure is both domain-based and pipeline-based.

### 6.1 Domain Ownership

Keep feature ownership separated by domain:
- `spectrum`
- `background`
- `logo`
- `particles`
- `text`
- `atmosphere`
- future `postfx`
- future `audio-reactivity`

Each domain should own:
- editor schema and defaults
- draft patch builders
- scene contract
- runtime prep
- GPU contract
- tests

### 6.2 Pipeline Ownership

Keep execution stages separated by runtime concern:
1. transport / clock
2. audio analysis / feature timeline
3. scene composition
4. GPU data preparation
5. GPU simulation
6. render passes
7. post-fx
8. telemetry / performance governor
9. export submission

### 6.3 Recommended New Ownership Split

Introduce or strengthen these runtime seams:
- `features/video/domains/audio-reactivity/*`
- `features/video/domains/postfx/*`
- `features/video/performance/*`
- shared render-graph contract used by both preview and export

This is the architecture that avoids “one improvement causing another improvement later.” The dependency chain becomes explicit up front.

## 7. Required Improvements

### 7.1 Audio Reactivity Revamp

Required changes:
- replace purely live analyser-driven quality expectations with a richer analyzed feature timeline
- add explicit:
  - bass envelope
  - mid envelope
  - treble envelope
  - broadband energy
  - onset envelope
  - beat grid
  - transient strength
  - peak-hold bands
- support interpolation between analyzed frames
- standardize attack/release behavior per signal family
- separate:
  - source sensitivity
  - domain reactivity multipliers
  - output smoothing

Best implementation direction:
- when an audio track is loaded, build or fetch an analyzed feature timeline once
- keep preview frame reads deterministic against that timeline
- upload feature arrays to GPU buffers/textures
- use GPU compute or shader-side interpolation for live frame sampling

Why this should happen first:
- it addresses the user's direct complaint about weak audio feel
- it removes repeated CPU work
- it improves every downstream domain at once
- it creates a stable shared signal contract for preview and export

### 7.2 GPU-First Runtime

Required changes:
- move spectrum shaping stages off repeated CPU loops where possible
- move peak-hold into GPU-side or GPU-fed runtime state
- move particle simulation to GPU compute
- move more gradient treatment into shader logic
- add GPU motion blur / history-based pass
- centralize bloom and motion-blur quality tiers under post-fx ownership

### 7.3 Preview / Export Parity

Required changes:
- stop treating preview and export as separate renderer products
- define one render-graph contract
- share:
  - scene-node inputs
  - audio feature timeline format
  - GPU pass order
  - post-fx tuning
  - blend behavior
  - color pipeline

Target state:
- preview and export are two execution modes of the same renderer architecture
- differences are limited to surface/output ownership, not visual behavior

### 7.4 Performance Governor

Required changes:
- establish target frame budgets:
  - 120 FPS high-tier preview
  - 60 FPS broad compatibility preview
- add dynamic quality degradation based on telemetry:
  - particle count
  - bloom radius / pass count
  - spectrum point density
  - optional motion-blur quality
- add quality tiers per adapter class
- keep UI editing responsive even during heavy preview load

### 7.5 Post-FX Domain Ownership

Required changes:
- make post-fx an explicit domain/runtime owner instead of scattered tuning
- own:
  - bloom
  - glow compositing
  - motion blur
  - color shaping
  - future tone mapping

### 7.6 Remove Remaining Runtime Leakage

Required changes:
- continue moving signal-processing helpers out of top-level preview components
- keep `RendererVideoPreview.tsx` as orchestration and view shell only
- prevent domain math from accumulating back into coordinator/page layers

## 8. Double-Shot Delivery Plan

The best way to avoid future rework is not to implement every shiny item at once. It is to pair improvements that share the same foundation.

### 8.1 Double-Shot 1: Audio Reactivity Core + GPU Signal Pipeline

This should be the next implementation bundle.

Includes:
- analyzed audio feature timeline
- stronger beat/onset/transient pipeline
- peak-hold
- GPU-fed feature buffers
- standardized smoothing / interpolation
- removal of duplicated CPU-side spectrum shaping

Why this is the best first shot:
- highest impact on perceived quality
- highest impact on “professional reactivity”
- directly addresses the Python parity concern
- creates the shared foundation for particles, post-fx, and parity work

Definition of done:
- preview reactivity subjectively matches or exceeds Python reference timing stability
- beat and onset behavior is deterministic
- peak-hold exists and is tunable internally
- CPU per-frame audio shaping is materially reduced
- no required operator UI expansion

### 8.2 Double-Shot 2: GPU Particles + Motion Blur + Performance Governor

This should follow immediately after Double-Shot 1.

Includes:
- GPU particle simulation
- GPU motion blur
- adaptive performance tiers
- telemetry-driven quality fallback
- post-fx domain ownership cleanup

Why this is the right second shot:
- uses the new feature timeline from Double-Shot 1
- converts the remaining expensive visual systems into GPU-owned runtime paths
- improves smoothness without needing more inspector controls

Definition of done:
- particle count scales materially above the current CPU-sim ceiling
- preview remains stable under heavier scenes
- motion continuity improves visibly
- weaker devices degrade quality instead of becoming janky

### 8.3 Convergence Shot: Preview / Export Parity

This is the critical architectural closure shot.

Includes:
- one render-graph contract
- one audio feature contract
- one scene-to-GPU preparation model
- export path convergence away from visual drift

Definition of done:
- preview and export use the same rendering contracts
- known parity drift cases are eliminated
- preview is trustworthy as the true final look

## 9. Additional Recommendations Beyond The Current Gaps

Besides the explicit checklist gaps, these are worth doing:

1. Add adapter-tier capability profiling:
   - buffer limits
   - texture limits
   - shader workgroup limits
   - preferred quality tier

2. Add render snapshots for parity testing:
   - same template
   - same audio timestamp
   - compare preview and export reference outputs

3. Add structured audio-reactivity fixtures:
   - kick-heavy
   - sustained bass
   - vocal-mid heavy
   - high-treble percussion

4. Add internal performance test scenes:
   - maximum layers
   - heavy bloom
   - high particle count
   - multiple text overlays

5. Add one runtime-owned “quality policy” object rather than scattering thresholds.

6. Add background/offline audio feature caching so switching tracks or reopening the workspace does not repeatedly rebuild expensive analysis.

## 10. Proposed Roadmap Tasks

### Completed Planning Task

- `M7.A18`: Document the Video preview parity, GPU migration, and audio-reactivity improvement program in detail and set the next implementation slices.

### Proposed Next Build Tasks

- `M7.A19`: Build the analyzed audio feature timeline and GPU signal pipeline, including beat/onset parity work and peak-hold
- `M7.A20`: Move particles and remaining frame-critical visual simulation toward GPU ownership, add motion blur, and add adaptive performance tiers
- `M7.A21`: Unify preview and export around one renderer contract so preview becomes a trustworthy 100% final representation

### Narrowed Coverage Map

The detailed closure checklists for these phases now live in `docs/tasks.md` under:
- `3.10.16 Narrowed M7.A19 Closure Checklist`
- `3.10.17 Narrowed M7.A20 Closure Checklist`
- `3.10.18 Narrowed M7.A21 Closure Checklist`

Every finding from this audit should be considered covered only when the following mapping is fully closed.

| Finding / Requirement | Coverage |
|---|---|
| Replace live-only analyser heuristics with a stronger analyzed timeline | `M7.A19.1`, `M7.A19.2`, `M7.A19.8` |
| Bass / mid / treble / energy / onset / beat / transient feature ownership | `M7.A19.2`, `M7.A19.4` |
| Real peak-hold | `M7.A19.3`, `M7.A19.10` |
| Deterministic interpolation between analysis frames | `M7.A19.5`, `M7.A19.10` |
| Preserve logarithmic weighting and existing good FFT mapping behavior | `M7.A19.6` |
| Move frame-critical audio shaping toward GPU-fed runtime consumption | `M7.A19.7`, `M7.A20.2` |
| Keep preview edits immediate and smooth without UI clutter | `M7.A19.8`, `M7.A19.11`, `M7.A20.10`, `M7.A21.11` |
| Reconcile Electron reactivity quality against Python ModernGL | `M7.A19.9`, `M7.A19.12` |
| Adapter capability profiling | `M7.A20.1` |
| One runtime-owned quality policy | `M7.A20.1`, `M7.A20.7` |
| Move particles off CPU simulation | `M7.A20.4`, `M7.A20.11` |
| Add real motion blur | `M7.A20.3`, `M7.A20.6`, `M7.A20.11` |
| Improve gradient shader ownership | `M7.A20.5` |
| Connect telemetry to adaptive quality fallback | `M7.A20.7`, `M7.A20.9` |
| Add internal stress scenes | `M7.A20.8`, `M7.A20.11` |
| Hold honest 60 FPS / 120 FPS targets by tier | `M7.A20.1`, `M7.A20.7`, `M7.A20.9` |
| Create explicit post-fx ownership | `M7.A20.3`, `M7.A20.11` |
| Define one shared render-graph contract | `M7.A21.1`, `M7.A21.10` |
| Define one shared audio-feature contract for preview and export | `M7.A21.2`, `M7.A21.10` |
| Unify scene-to-GPU preparation | `M7.A21.3`, `M7.A21.10` |
| Unify pass order / blend / post-fx / color treatment | `M7.A21.4`, `M7.A21.7` |
| Remove preview/export renderer drift | `M7.A21.5`, `M7.A21.12` |
| Add parity fixtures and diff checks | `M7.A21.6`, `M7.A21.7`, `M7.A21.9` |
| Retire mismatch reporting only when mismatch is genuinely gone | `M7.A21.8`, `M7.A21.11` |
| Guarantee preview is trustworthy as final output | `M7.A21.5`, `M7.A21.9`, `M7.A21.12` |
| Avoid unnecessary UI expansion throughout the program | `M7.A19.8`, `M7.A20.10`, `M7.A21.11` |
| Cover the additional recommendations from this plan | `M7.A19.9`, `M7.A20.1`, `M7.A20.8`, `M7.A21.6`, `M7.A21.7` |

## 11. Verification Requirements For The Build Phases

### For `M7.A19`
- focused tests for audio feature extraction/mapping/interpolation
- deterministic fixtures for beat/onset/peak-hold behavior
- preview responsiveness checks while editing Spectrum/Background/Logo/Particles
- no new UI clutter

### For `M7.A20`
- telemetry-based frame-budget tests
- particle stress verification
- motion-blur correctness checks
- quality-tier degradation tests

### For `M7.A21`
- preview/export parity fixtures
- shared contract tests
- snapshot diff thresholds
- export correctness at multiple timestamps

## 12. Final Recommendation

The best next move is not another UI cleanup pass.

The best next move is:
1. `M7.A19` first
2. `M7.A20` immediately after as a paired second shot
3. then `M7.A21` to close preview/export truth

That sequence gives the biggest quality jump with the least rework:
- better audio feel
- more GPU ownership
- smoother real-time preview
- less CPU bottlenecking
- a path toward real preview/export parity
