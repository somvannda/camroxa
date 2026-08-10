# Composition Studio — wiring matrix

**Branch:** `feature/studio-v1`  
**Scope:** Studio polish (NLE timeline = future only).

Status legend: **FULL** = control changes preview (and export when applicable); **PARTIAL** = wired with known GPU limits; **STUB** = UI only / deferred.

| Axis / control | UI | Document | Compile / GPU | Export | Status |
|---|---|---|---|---|---|
| Color palette | Dropdown | `colorPalette` | Unique gradient stops on spectrum (+ particle tint when palette set) | Template | FULL |
| Palette Expert intensity/sat | Expert sliders | `paletteIntensity`, `paletteSaturation` | Baked into palette stops (+ soft sat proxy) | Template | FULL |
| Background image / video | File pickers | `assets.*` | Preview plate (+ video frames) | Image required for video export | FULL / PARTIAL (video plate preview-only for export) |
| Background motion | Dropdown | `background.motion` | Live offsets + userScale + zoom/vibrate; warp proxies | Template | FULL (GPU mode whitelist still 4 modes) |
| Background Expert grade | Expert sliders | brightness/contrast/react/sat/hue/smooth | backgroundSettings | Template | FULL |
| Background Expert motion | Expert sliders | motionSpeed/Amplitude/Zoom/Warp | Multiplies active motion style | Template | FULL |
| Atmosphere | Dropdown | `background.atmosphere` | Per-style atmosphereDraw (weather/volume/sky/distort) | Template | FULL |
| Atmosphere Expert | Expert sliders | density/speed/opacity/wind | Scales active atmosphere style | Template | FULL |
| Left Composition Studio | Scene tree + AI Designer | 420px rail | Node select drives right Inspector | Template | FULL |
| Center Playback | Backward/Play/Stop/Forward + scrub | preview transport | Video Playback card | Template | FULL |
| Center console | TRACK LIST \| Actions | `audioTracks` + studio export | Under playback | Template | FULL |
| Right Inspector | Inspector / Developer tabs | 380px rail | Axis settings + Tuning + JSON | Template | FULL |
| Spectrum shape / material / animation | Dropdown | `spectrum.*` | Unique shape geometry × material scale × live instance sync | Template | FULL |
| Spectrum Expert (height/glow/opacity/blur/width/thickness) | Expert sliders | `spectrum.*` | Layer uniforms | Template | FULL |
| Spectrum center image (Vizzy-style) | File + mask/size/opacity/react | `assets.logo` + `logo.*` + `spectrumAttachToLogo` | logoSettings live; authored under Spectrum (no Logo tree node) | Template | FULL |
| Text + Expert opacity/scale/offset | Checks / fields / Expert sliders | text + studio extras | textOverlays | Template | FULL |
| Overlay style / animation / amount | Dropdown + Expert slider | overlay + `overlayStyle` | Distinct effect stacks per style | Template | FULL |
| Particles + Expert spawn/size/opacity/speed/react | Dropdown + Expert sliders | `particles.*` | particlesSettings (type-native colors) | Template | FULL |
| Lighting effect / trigger | Dropdown | `lighting.*` | Unique lightning profiles + GPU trigger/threshold | Template | FULL |
| Lighting Expert intensity/thickness/glow/flash/speed | Expert sliders | `lighting.*` | Lightning layer uniforms + live trigger bus | Template | FULL |
| Camera + Expert zoom/pan/shake/roll | Dropdown + Expert sliders | `camera.*` | Live cameraSettings | Template | FULL |
| Post stack | Checks | `postProcessing.effects` | Distinct `effects.*` + preview proxies (washes / grain / RGB / letterbox / motion streaks) | Template | FULL (proxies, not full export stack) |
| Post amount / quality / LOD | Expert slider + combo + check | `postProcessing.amount`, `performance.*` | Amount scales effects; quality/LOD → `barCount` + particle spawn | Template | FULL |
| Audio mapping + gain/smooth/bass | Dropdown + Expert sliders | `audio.*` | Live bus levels | Template | FULL (vocals/melody/snare = FFT heuristics) |
| Export resolution / fps / quality | Export panel dropdowns | `studioExport` | ManualRenderSceneRequest + speed_mode | FULL |
| Export include audio / range | Checkbox / spins | `studioExport` | Stored on request/settings + template | PARTIAL (mux always includes audio today; range validated, full-track render until GPU trim) |
| Player bar | Transport stub | — | Preview seek/play | — | FULL (not NLE) |
| NLE timeline | — | — | — | — | STUB / future |

## Audit notes (2026-08-09)

Catalog uniqueness (compile/live signatures): shapes/materials/animations/camera/bg motion/atmosphere/particles/lighting/triggers/palettes/overlays = unique.  
Previous gaps fixed in this pass: palette Expert colors, performance quality/LOD density, broader post preview proxies, lighting trigger bus in live motion.

## Known intentional limits

- GPU `backgroundSettings.motionMode` ∈ {none, zoom, vibrate, both}. Distinct catalog looks come from `userScale` / offsets / warp proxies.
- Vocals / Melody / Snare buses remain v1 FFT heuristics.
- Post checks use lightweight preview proxies (not the full export color pipeline).
- Full NLE (clips, razor, transitions, keyframes, nested, mixer) is deferred.
