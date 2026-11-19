# Vizzy — Feature Inventory and Port Checklist

> **Document ID:** CAMXORA-ED-VZ-01
> **Version:** 1.0.0
> **Status:** Draft
> **Source:** `G:\Developments\Rea\editor` + Rea docs
> **Last updated:** 2026-11-19

This is the line-item checklist for "port the whole thing first". Tick an item only when it
works inside the Electron host and the acceptance test passes.

---

## 1. Editor shell

- [ ] **VZ-01a** Top bar: brand, File/Edit/Project/View/Help
- [ ] **VZ-01b** Release chip opens the changelog
- [ ] **VZ-01c** Project name and save state ("Not saved" / "Saving…" / "Saved")
- [ ] **VZ-01d** Warning chip with count and list
- [ ] **VZ-01e** Account/sign-in affordance (Camxora session, not Vizzy)
- [ ] **VZ-01f** Export primary action
- [ ] **VZ-02a** File → Export (`Ctrl+E`)
- [ ] **VZ-02b** File → New Project (`Ctrl+B`)
- [ ] **VZ-02c** File → Save (`Ctrl+S`)
- [ ] **VZ-02d** File → Save As New (`Ctrl+Shift+S`)
- [ ] **VZ-02e** File → Close Editor
- [ ] **VZ-03a** Edit → Cut (`Ctrl+X`), disabled when nothing is selected
- [ ] **VZ-03b** Edit → Copy (`Ctrl+C`)
- [ ] **VZ-03c** Edit → Paste (`Ctrl+V`)
- [ ] **VZ-04a** Project → Explore creations
- [ ] **VZ-04b** Project → Rename
- [ ] **VZ-04c** Project → Update thumbnail
- [ ] **VZ-04d** Project → Set creator note
- [ ] **VZ-04e** Project → Set custom resolution
- [ ] **VZ-04f** Project → Set background
- [ ] **VZ-04g** Project → Organise track positions
- [ ] **VZ-04h** Project → Save preview as image
- [ ] **VZ-05a** View → Command Palette (`Ctrl+Shift+P`)
- [ ] **VZ-05b** View → Change editor layout
- [ ] **VZ-05c** View → Window dragging (`Ctrl+D`)
- [ ] **VZ-05d** View → Theme
- [ ] **VZ-06a** Help → Project information
- [ ] **VZ-06b** Help → System information
- [ ] **VZ-06c** Help → Discord / FAQ / tutorial
- [ ] **VZ-06d** Help → Export project as JSON
- [ ] **VZ-06e** Help → Export current/last log
- [ ] **VZ-06f** Help → Changelog
- [ ] **VZ-07** Command palette: 37 commands, grouping, shortcuts, substring search, Enter/Down runs first
- [ ] **VZ-08** Editor warnings: import skips, approximations, failed media fetches
- [ ] **VZ-09** Status bar message strip
- [ ] **VZ-10** Changelog modal

---

## 2. Left panel

### 2.1 Composition

- [ ] **VZ-11a** Layers listed top-first, items nested, type chips
- [ ] **VZ-11b** Selection sync with timeline and inspector
- [ ] **VZ-11c** Collapse/expand layers
- [ ] **VZ-12a** Add layer
- [ ] **VZ-12b** Add item (all 28 kinds)
- [ ] **VZ-12c** Add effect to layer
- [ ] **VZ-12d** Rename
- [ ] **VZ-12e** Delete
- [ ] **VZ-12f** Reorder layers / move item between layers
- [ ] **VZ-13a** Visibility toggle
- [ ] **VZ-13b** Shy toggle
- [ ] **VZ-13c** Render-to-buffer toggle
- [ ] **VZ-13d** Audio toggle
- [ ] **VZ-13e** Clear
- [ ] **VZ-14a** Multi-select
- [ ] **VZ-14b** Drag item to another layer
- [ ] **VZ-14c** Drag item onto an analyzer to bind
- [ ] **VZ-15** Context menus: add, rename, delete, move, reorder
- [ ] **VZ-16** Timeline layer headers mirror the tree

### 2.2 Analyzers

- [ ] **VZ-31a** "Add audio analyzer"
- [ ] **VZ-31b** Default analyzer cannot be deleted
- [ ] **VZ-31c** Rename/delete row actions
- [ ] **VZ-31d** Expand connections; "not being used" when empty
- [ ] **VZ-31e** Right-click Edit/Rename/Delete
- [ ] **VZ-32a** `sampleProvider` (filter bank / goertzel)
- [ ] **VZ-32b** `outputMultiplier` 0–120
- [ ] **VZ-32c** `sampleOutCount` 16–256 step 4
- [ ] **VZ-32d** `audioDuration` 0–1000 ms
- [ ] **VZ-32e** `audioOffset` −1000–1000 ms
- [ ] **VZ-32f** `audioReactionAlignment` −1–1 step 0.01
- [ ] **VZ-32g** `frequencyRange` log range 1–2000 Hz
- [ ] **VZ-32h** `smoothingTimeConstant` 0–1
- [ ] **VZ-32i** `windowFunction` (11)
- [ ] **VZ-32j** `windowParameter` 0–10 step 0.1 (conditional)
- [ ] **VZ-32k** `windowSkew` −2–2 step 0.1
- [ ] **VZ-32l** `cqtBandwidth` 2–16 (filter bank)
- [ ] **VZ-32m** `cqtWindowFunction` / parameter / skew
- [ ] **VZ-32n** `perBinFrequencyTilt` −12–12 dB/oct (goertzel)
- [ ] **VZ-32o** `perBandFrequencyTilt` −12–12 dB/oct
- [ ] **VZ-32p** `perBandWeightingAmount` 0–0.1 step 0.001
- [ ] **VZ-32q** `perBandWeighting` A/B/C/D/M
- [ ] **VZ-32r** `frequencyScale` linear/log/mel/critical/ERB/sinh/nth root
- [ ] **VZ-32s** `hzLinearFactor` 0–1 (sinh/nth root)
- [ ] **VZ-32t** `downSample`
- [ ] **VZ-33** Bind/unbind items and automations; ownership persists
- [ ] **VZ-34** WASM analyser + JS fallback parity
- [ ] **VZ-35** Frequency scale transforms match
- [ ] **VZ-36** Weighting curves and tilts match
- [ ] **VZ-37** 64-analyzer batch, one WASM call per frame, fixed scratch

### 2.3 Effects

- [ ] **VZ-38a** Color Tint
- [ ] **VZ-38b** Invert
- [ ] **VZ-38c** Pixelate
- [ ] **VZ-38d** Chromatic Aberration
- [ ] **VZ-38e** Box Blur
- [ ] **VZ-38f** Render
- [ ] **VZ-38g** Two Pass Blur
- [ ] **VZ-38h** Blur Triangle
- [ ] **VZ-38i** VHS
- [ ] **VZ-38j** Time Stop
- [ ] **VZ-38k** FidelityFX CAS
- [ ] **VZ-38l** Liquify
- [ ] **VZ-38m** Gradient Map
- [ ] **VZ-38n** Chroma Shift
- [ ] **VZ-38o** Premultiply Alpha
- [ ] **VZ-38p** Distance Field
- [ ] **VZ-38q** Advanced Outline
- [ ] **VZ-38r** Advanced Shadow
- [ ] **VZ-38s** Glitch
- [ ] **VZ-38t** VHS2
- [ ] **VZ-38u** Outline
- [ ] **VZ-38v** Drop Shadow
- [ ] **VZ-38w** Streak Glow
- [ ] **VZ-38x** Morphing Fractal
- [ ] **VZ-38y** Displacement
- [ ] **VZ-38z** Image Mask
- [ ] **VZ-38aa** Spooky
- [ ] **VZ-38ab** Impact Ripple
- [ ] **VZ-38ac** Render Layer
- [ ] **VZ-38ad** Repeating Ripple
- [ ] **VZ-38ae** RGB Displace
- [ ] **VZ-38af** Scale
- [ ] **VZ-38ag** Channel Blur
- [ ] **VZ-38ah** God Rays
- [ ] **VZ-38ai** Chroma Key
- [ ] **VZ-38aj** Edge Detection
- [ ] **VZ-38ak** FXAA
- [ ] **VZ-38al** Glow
- [ ] **VZ-38am** Bloom
- [ ] **VZ-38an** Alpha
- [ ] **VZ-39** Add/enable/remove/back
- [ ] **VZ-40** Per-effect parameters + shader controls
- [ ] **VZ-41** Reorder/rename/context menu
- [ ] **VZ-42** Layer vs item scope
- [ ] **VZ-43** Shader source editing (where exposed)
- [ ] **VZ-44** Effect thumbnails

### 2.4 Automations

- [ ] **VZ-45a** Add keyframe at playhead
- [ ] **VZ-45b** Move/delete keyframe
- [ ] **VZ-45c** Easing: linear/ease-in/out/hold + named curves
- [ ] **VZ-46a** Math automation with formula
- [ ] **VZ-46b** Variables `t, p, a, m, d, u1–u5, g1–g5, rx, ry`
- [ ] **VZ-46c** Unit inputs and automation connections
- [ ] **VZ-47a** Audio impact min/max/sensitivity/smoothing
- [ ] **VZ-47b** Floor/ceiling
- [ ] **VZ-47c** Cumulative
- [ ] **VZ-47d** Delta smoothing/decay/threshold
- [ ] **VZ-48** Color automation from/to
- [ ] **VZ-49a** Add group/folder
- [ ] **VZ-49b** Rename/remove/toggle group
- [ ] **VZ-49c** Drag automations into groups
- [ ] **VZ-50a** Property connections
- [ ] **VZ-50b** Effect parameter connections
- [ ] **VZ-50c** Automation-to-automation connections
- [ ] **VZ-51** Comparator + threshold
- [ ] **VZ-52** Enable/disable/delete/undo

### 2.5 Media

- [ ] **VZ-60a** Upload image
- [ ] **VZ-60b** Upload video
- [ ] **VZ-60c** Upload audio
- [ ] **VZ-60d** Drag/drop upload
- [ ] **VZ-60e** Asset store and cache by id
- [ ] **VZ-60f** Replace media
- [ ] **VZ-60g** Missing-media warning

### 2.6 Projects

- [ ] **VZ-65a** List projects
- [ ] **VZ-65b** Search
- [ ] **VZ-65c** Open
- [ ] **VZ-65d** Delete
- [ ] **VZ-65e** Recent projects
- [ ] **VZ-65f** Thumbnail

### 2.7 Lyrics

- [ ] **VZ-67a** Import text
- [ ] **VZ-67b** Import LRC
- [ ] **VZ-67c** Import lyric items
- [ ] **VZ-68a** Split/join lines
- [ ] **VZ-68b** Timing editor
- [ ] **VZ-68c** Preview
- [ ] **VZ-69** Lyrics renderer
- [ ] **VZ-70** Export lyrics

---

## 3. Inspector

- [ ] **VZ-24a** `Objects / <name>`
- [ ] **VZ-24b** Selection follows tree/timeline
- [ ] **VZ-24c** Delete from header
- [ ] **VZ-25** Collapsible sections in reference order
- [ ] **VZ-26a** Select
- [ ] **VZ-26b** Slider
- [ ] **VZ-26c** Range
- [ ] **VZ-26d** Boolean
- [ ] **VZ-26e** Text
- [ ] **VZ-26f** Color
- [ ] **VZ-26g** File
- [ ] **VZ-26h** Image grid
- [ ] **VZ-26i** Analyzer
- [ ] **VZ-26j** Custom path
- [ ] **VZ-27a** Keyframe diamond per animatable row
- [ ] **VZ-27b** Add/remove keyframe
- [ ] **VZ-27c** Prev/next keyframe
- [ ] **VZ-28** Constraints, disabled rows, tooltips
- [ ] **VZ-29** Composition properties when nothing is selected
- [ ] **VZ-30** Rename object/layer/effect/analyzer/automation

---

## 4. Nodes

- [ ] Layer
- [ ] Media (image/video)
- [ ] Particles
- [ ] Spectrum
- [ ] Cube
- [ ] Square
- [ ] Plane
- [ ] Point light
- [ ] Progress bar
- [ ] Logo
- [ ] Ground
- [ ] Noise
- [ ] Skia text
- [ ] Animated text
- [ ] Lyrics
- [ ] Audio wave
- [ ] Basic spectrum bars
- [ ] Particle lines
- [ ] 3D model
- [ ] Line bed
- [ ] Spherical field
- [ ] Instanced particle system
- [ ] Particle system
- [ ] Confetti
- [ ] Shader item
- [ ] Skottie/Lottie
- [ ] Video
- [ ] WASM video
- [ ] Video 2
- [ ] Butterchurn
- [ ] Particle timeline

For each node: create, default controllers, inspector, timeline row, save/import/export,
render, and at least one screenshot test.

---

## 5. Presets and templates

- [ ] **VZ-53a** Built-in 5 presets
- [ ] **VZ-53b** Spectrum catalogue
- [ ] **VZ-53c** Community presets
- [ ] **VZ-53d** User presets
- [ ] **VZ-54** Apply as one undo step
- [ ] **VZ-55a** Save current settings as preset
- [ ] **VZ-55b** Overwrite preset
- [ ] **VZ-55c** Edit preset image
- [ ] **VZ-55d** Delete preset
- [ ] **VZ-56** Import/export preset JSON
- [ ] **VZ-57** Context menus and order
- [ ] **VZ-58a** Templates modal
- [ ] **VZ-58b** Template panel
- [ ] **VZ-58c** Apply template
- [ ] **VZ-58d** Import template
- [ ] **VZ-59** Marketplace template refresh

---

## 6. Timeline

- [ ] **VZ-71a** Wheel pan
- [ ] **VZ-71b** Ctrl/Cmd+wheel zoom at pointer
- [ ] **VZ-71c** Zoom buttons anchor playhead
- [ ] **VZ-71d** Fit / `Shift+Z`
- [ ] **VZ-71e** `Z` frames selection
- [ ] **VZ-71f** Auto-follow playhead
- [ ] **VZ-72a** Ruler 40 px
- [ ] **VZ-72b** Playhead + handle
- [ ] **VZ-72c** Timecode readout
- [ ] **VZ-72d** Seconds/frames toggle
- [ ] **VZ-73a** Shift-drag loop span
- [ ] **VZ-73b** Drag loop edges
- [ ] **VZ-73c** Double-click ruler clears
- [ ] **VZ-73d** Loop playback only the span
- [ ] **VZ-74** Beat/bar grid from BPM
- [ ] **VZ-75a** Audio waveform (2048 buckets)
- [ ] **VZ-75b** Audio name
- [ ] **VZ-75c** Choose audio
- [ ] **VZ-76a** Layer headers (24 px) with visibility + count
- [ ] **VZ-76b** Clips in 35 px lanes
- [ ] **VZ-76c** Move/resize with trim grips
- [ ] **VZ-76d** Multi-select + group drag
- [ ] **VZ-76e** Empty state
- [ ] **VZ-77a** Snap to playhead
- [ ] **VZ-77b** Snap to project ends
- [ ] **VZ-77c** Snap to markers
- [ ] **VZ-77d** Snap to loop edges
- [ ] **VZ-77e** Snap to beats
- [ ] **VZ-77f** Snap to clip edges
- [ ] **VZ-77g** Dashed guide within 6 px
- [ ] **VZ-78a** Add marker `Shift+M`
- [ ] **VZ-78b** Click to jump
- [ ] **VZ-78c** Drag marker
- [ ] **VZ-78d** Rename/delete
- [ ] **VZ-79a** Select tool `V`
- [ ] **VZ-79b** Hand tool `H`
- [ ] **VZ-79c** Razor `C`
- [ ] **VZ-79d** Slip `Y`
- [ ] **VZ-79e** Split at playhead `Ctrl+K`
- [ ] **VZ-79f** Ripple delete `Shift+Delete`
- [ ] **VZ-80a** Keyframe lane
- [ ] **VZ-80b** Marquee keys
- [ ] **VZ-80c** 2D group drag, one undo
- [ ] **VZ-81** Source in/out for video
- [ ] **VZ-82** Clip comments
- [ ] **VZ-83** Accessibility (hidden list, focus, arrows, Home/End, reduced motion)
- [ ] **VZ-84** Cached static frame + playhead-only redraw

---

## 7. Stage, audio, render, export

- [ ] **VZ-85a** Resolution 360/480/720/1080
- [ ] **VZ-85b** Bounce
- [ ] **VZ-85c** Open external
- [ ] **VZ-86** Canvas drag/drop
- [ ] **VZ-87a** Volume
- [ ] **VZ-87b** Mute
- [ ] **VZ-87c** Bass boost + frequency
- [ ] **VZ-87d** Playback rate
- [ ] **VZ-87e** Compressor
- [ ] **VZ-87f** Attenuator
- [ ] **VZ-87g** Additional gain
- [ ] **VZ-88** Offline audio graph feeds analysers
- [ ] **VZ-89a** Resolution presets + width/height
- [ ] **VZ-89b** Frame rate
- [ ] **VZ-89c** Tempo BPM
- [ ] **VZ-89d** Duration
- [ ] **VZ-89e** Background
- [ ] **VZ-89f** Globals g1–g5
- [ ] **VZ-89g** Spectrum colour options
- [ ] **VZ-90** Export current frame as image
- [ ] **VZ-91a** H.264/AAC MP4
- [ ] **VZ-91b** VP9/Opus WebM
- [ ] **VZ-91c** VP8/Vorbis WebM
- [ ] **VZ-92a** Progress
- [ ] **VZ-92b** Cancel
- [ ] **VZ-92c** Error with output path/log
- [ ] **VZ-93** WebCodecs export
- [ ] **VZ-94** Native FFmpeg export bridge
- [ ] **VZ-95** Audio muxed at project duration
- [ ] **VZ-96** Export resolution independent of preview
- [ ] **VZ-97** Project information dialog
- [ ] **VZ-98** System information dialog
- [ ] **VZ-99** Export logs
- [ ] **VZ-100** Tutorial/FAQ content

---

## 8. Project I/O

- [ ] **VZ-61a** New project with resolution
- [ ] **VZ-61b** Open native project
- [ ] **VZ-61c** Save / Save As
- [ ] **VZ-61d** Close with dirty guard
- [ ] **VZ-62a** Import Vizzy project export
- [ ] **VZ-62b** Map layers/items/transforms
- [ ] **VZ-62c** Map spectrum settings
- [ ] **VZ-62d** Map shader items/SkSL
- [ ] **VZ-62e** Map lyrics
- [ ] **VZ-62f** Map media/audio references
- [ ] **VZ-63** Export project JSON
- [ ] **VZ-64** Thumbnail/creator note/description
- [ ] **VZ-66a** Autosave 2 s
- [ ] **VZ-66b** Crash recovery prompt
- [ ] **VZ-66c** Recent projects
- [ ] **VZ-66d** Atomic write

---

## 9. Acceptance evidence

For each section, record:

- the project used;
- the screenshot path;
- the export path and probe result;
- the console/log result;
- the tester and date.

Use [`03-PARITY-HARNESS.md`](03-PARITY-HARNESS.md) for the procedure.
