# CAMXORA Studio vs Suno Studio vs musicapi — three-column audit

Date: **2026-11-14** · Scope: the **web** Studio (`camxora.com/components/studio`), not the
legacy PyQt6 desktop app.

How to read the tables:

| Column | What it means |
|---|---|
| **CAMXORA Studio** | What ships in this worktree today, verified by the Playwright/Vitest suites or by the measured probe. |
| **Suno Studio** | What the reference exposes, from the captures in `reference/screens/` (1689×1277, DPR 1) and `SUNO_STUDIO_IMPLEMENTATION_SPEC.md`. |
| **musicapi** | Which server-side endpoint (if any) backs the row. `—` means the work happens in the browser (`WebAudio`, `OfflineAudioContext`, DOM) and no API is involved. |

Markers: ✅ comparable · ◐ exists but differs (visual or scope) · ✗ absent.

Evidence for the "ours" column: `components/studio/*`, `lib/studio-*.ts`, the 57 e2e specs
under `tests/e2e`, `public/studio-metrics.json`, and fresh captures in
[`compare/`](compare) (`ours-editor-1689.png`, `ours-editor-library-1689.png`,
`ours-editor-1280.png`) taken at the reference viewport with a 12-track project.

---

## 0. One-line verdict

**Every captured surface is present.** The 2026-11-14 completion pass closed the last five:
the Settings → Window management and Content panes, the Wavetable Designer behind advanced
content, clip-level inserts, the Stereo Utility plugin, and project-card thumbnails. The
arrangement, mixing, plugin, MIDI and collaboration surfaces now match the reference 1:1
except the Learn menu's YouTube Tutorials row, which is dropped by product decision.

Two things the earlier draft of this audit called gaps are not gaps at all: Suno Studio has
**no mixer surface** (S47 is an explicit negative capture) and no FX sends, track groups,
master spectrum or mastering presets in any capture or shipped string. We do not invent them.
Everything paid or provider-backed still goes through musicapi; the DAW maths never leaves
the browser.

---

## 1. Frame & pixel geometry

Reference viewport 1689×1277. "Ours" numbers are asserted by `tests/e2e/studio-pixel.spec.ts`
against `reference/METRICS.json`.

| Region | CAMXORA Studio | Suno Studio | Delta |
|---|---|---|---|
| App background | navy `#0b1120` family (D-025 palette) | `#111111`, text `#f7f4ef` | ◐ palette only, geometry identical |
| Header band | 52 px, pills 36 px at y8, radius 999 | 52 px `#0a0a0a`, pills 36 px y8 | ✅ |
| Wordmark / project chip | `CAMXORA` wordmark, chip at x110 | `SUNO` wordmark, chip at x115 | ◐ brand width shifts the chip 5 px |
| Transport placement | left cluster after undo/redo; clock + bar.beat beside it | centred cluster; clock + bar.beat centred | ◐ deliberate: our header also carries save status, master peak, speed |
| BPM / meter | right of the clock group, both editable | right-aligned, ~550 px from the clock | ◐ same controls, different anchor |
| Track panel | 260 px, head 29 px, row 85 px | 260 px `#141416`, head 29 px, row 85 px | ✅ |
| Track row controls | speaker / S / A / chevron + two range sliders (volume, pan) | speaker / S / A + chevron, fader capsule 167 px + half-circle pan knob | ◐ G41 replaced decorative bars with real sliders |
| Colour strip | 10 px at x8 | 10 px at x8 | ✅ |
| Lane pitch | 86 px, starts y82 | 86 px, starts y82 | ✅ |
| Clip | y84, 82 px tall, radius 10, label +17, waveform from decoded audio | same | ✅ |
| Bar ruler | 30 px, 96 px/bar default, 4 zoom levels 48–192 | 30 px, 96 px/bar, labels thin 1/2/4/8 | ✅ |
| Time ruler | 22 px dim band | 22 px | ✅ |
| Playhead | 1 px line + cyan ruler flag | same | ✅ |
| Footer band | 52 px, groups in 36 px pills | 52 px `#0a0a0a` | ✅ |
| Prompt bar | 645×97 card, centred at x652, attach + tools + line + model + send | same geometry (S34–S38) | ✅ |
| Conversation dock | 315 px bar docked bottom-left x16; expand returns it to the centre | same | ✅ |
| Assistant panel | 360 px column inset 8 px under the header | same | ✅ |
| Library rail | floating 360 px card, inset 8 px, radius 12 | same | ✅ |
| Library head / tiles / rows | 34 px head, 64 px tiles, 40 px icon squares; rows 56 px art, 15 px title, 13 px meta | same | ✅ |
| Plugin dock | full-width band, 448 px slot cards | same | ✅ |
| EQ card | 450 px, curve left, band controls right | same, pink/yellow accent | ◐ accent is CAMXORA purple |
| Popped-out plugin | fixed 460 px (520 for EQ), bottom-right | same | ✅ |
| Plugin catalog | 760 px dialog, 88 px device previews | 760 px `#171717`, `#1c1c1e` cards | ✅ geometry, our own preview art |
| Menus | project 212 px / clip 158 px / track options 164 px / add-track 208 px / Learn 206 px | same | ✅ |
| Dialogs | 480 px, radius 24, padding 32, 44 px pills | same | ✅ |
| My Projects modal | 786 px, two-column cards | same | ✅ |
| Export toast | 888 px banner, radius 16 | same | ✅ |
| Clip colours | pastel fills with dark labels (contrast-safe) | saturated fills, white labels | ◐ palette override D-025 |
| Extra chrome we add | save status, master peak, audition speed, library close X | silent autosave, no meter/speed | ◐ documented divergences (W2.1) |
| Below 768 px | desktop-only gate card with Back to Create | same gate | ✅ |

Full measured list: `docs/studio/PIXEL_PARITY.md`. Capture-by-capture: `reference/screens/`.

---

## 2. Shell & navigation

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Studio home / resume / recents | ✅ `/studio`: resume, list, search, sort, create, duplicate, archive, delete, start-from-song | ✅ landing with resume + recents + start-from-song | `GET /v1/studio/projects` (list), `POST /v1/studio/projects` (create) |
| Deep link to a project | ✅ `/studio/editor?project=<id>` | ✅ | `GET /v1/studio/projects/:id` |
| Project switcher in the editor | ✅ | ✅ | `GET /v1/studio/projects` |
| Undo / redo | ✅ Ctrl Z / Ctrl Shift Z, 50-document stack | ✅ | — (document history is client state until a save lands) |
| Project title / inline rename | ✅ | ✅ | `PATCH /v1/studio/projects/:id` |
| Export entry in the header | ✅ mix / one file per track / range / JSON | ✅ mix / range / multitrack | — (rendered in the browser) |
| Library, inspector, plugin, take-lane toggles | ✅ footer + header pills | ✅ | — |
| Signed-out gate | ✅ | ✅ | — (session lives in platform_api) |
| Standalone editor layout | ✅ full-bleed route, no site chrome | ✅ | — |
| Onboarding | ✅ start overlay for empty projects, remembered per project | ✅ “How do you want to start?” four cards | — |
| Project load skeleton / fatal error | ✅ | ✅ | — |
| Narrow viewports | ✅ 1024 keeps undo/redo + prompt bar; 768 keeps the 260 px panel; <768 gate | ✅ captured 1280/1024/768 | — |

## 3. Transport

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Play / pause, Space | ✅ | ✅ | — |
| Stop (halts at playhead) vs Back to start | ✅ two separate controls | ✅ | — |
| Seek by ruler, lane, draggable playhead | ✅ | ✅ | — |
| Arrow-key nudge | ✅ | ✅ | — |
| Time `mm:ss.mmm` + `bar.beat` readouts | ✅ | ✅ | — |
| BPM + time signature editable | ✅ 20–300 BPM, 2/4·3/4·4/4·6/8 | ✅ display; edit not captured | `PATCH /v1/studio/projects/:id` stores `bpm` / `time_signature` |
| Metronome with downbeat accent | ✅ audible, lookahead-scheduled | ✅ “Click track” | — |
| Loop region + wrap | ✅ start/end handles, wraps at loop end | ✅ | — |
| Follow playhead | ✅ | ✅ | — |
| Playback speed | ✅ 1× / 0.5× / 2× | ✅ | — |
| Per-clip gain, fades, offsets scheduled | ✅ | ✅ | — |
| Keep playing while editing | ✅ | ✅ | — |
| Queue across projects | ✗ (single project by design) | ✅ | — |

## 4. Timeline & clip editing

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Multitrack lanes, bar ruler, grid | ✅ | ✅ | — |
| Zoom (4 levels + fit to content) | ✅ Ctrl + / − / 0 | ✅ | — |
| Clip block: title, colour, waveform | ✅ decoded peaks, cached per URL | ✅ | — |
| Drag along / across lanes, snap, guideline | ✅ 3 px threshold, ghost-drag setting | ✅ | — |
| Marquee, multi-select, multi-drag | ✅ | ✅ | — |
| Copy / cut / paste / duplicate / delete | ✅ C/X/V/D, focus kept after delete | ✅ | — |
| Trim start/end, content offset | ✅ | ✅ | — |
| Split at playhead (Ctrl E) | ✅ | ✅ | — |
| Split on transients | ✅ onset detection from the clip's own peaks | ✅ (string) | — |
| Make Beat 1 | ✅ | ✅ (string) | — |
| Fades in/out (handles, Shift F) | ✅ | ✅ | — |
| Clip settings: volume, pan, pitch, speed, loop, reverse, quantize | ✅ all persisted | ✅ | — |
| Warp markers (detect, drag, quantize) | ✅ On Beat / Transients / Start-and-End | ✅ | — |
| Clip colour submenu | ✅ | ✅ | — |
| Section markers | ✅ Create Section stamps the ruler | ✅ | — |
| Time selection (range) | ✅ band, Delete/Duplicate/Extend/Export range | ✅ | — |
| Take lanes | ✅ 90 px band, newest on top, active outlined | ✅ | — |
| Clip-level inserts (§34) | ✅ clip menu → Add FX… / Remove FX; clip → clip FX → gain/fade → track chain, in playback and export | ✅ (Remove FX is captured; adding is the dock’s chain model) | — |
| Marker/loop/ruler right-click actions | ✅ | ✅ | — |
| Clip counts on very long projects | ✅ visible-window culling (300 → ~80–140 nodes) | ✅ canvas renderer | — |
| Snap guideline while dragging | ✅ | ✅ | — |

## 5. Generation inside the DAW

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Text prompt → clip at playhead / range | ✅ prompt bar + assistant panel, v6 / v6-wild / v6-mini | ✅ “Magic Bar” | `POST /v1/music` (through platform `POST /studio/generations`) |
| Attach a clip/track as prompt context | ✅ chip, removable | ✅ `+` attach menu | — (context is prompt text) |
| Job progress + failure copy on the clip | ✅ placeholder clip, provider message | ✅ | `GET /v1/task/:id` · `/me/task/:id` |
| Credit price before a paid action | ✅ reads `pricing`, never hard-coded | ✅ | `GET /studio/pricing` (platform) over `/pricing` |
| Not-enough-credits card with plans link | ✅ | ✅ | `402 INSUFFICIENT_CREDITS` envelope |
| Extend / Cover / Remaster / Vocals / Instrumental / Replace section / Mashup | ✅ clip menu, each lands as a lane or a take | ✅ (GEN-014…GEN-020) | `POST /internal/studio/{extend,cover,remaster,add-vocals,add-instrumental,replace-section,mashup}` |
| Mashup of two selected clips | ✅ new “Mashup” track at the earlier clip | ✅ | `POST /internal/studio/mashup` · `POST /v1/music/mashup` |
| Heal Edits (undo a transform) | ✅ restores pre-transform audio and drops the take stack | ✅ | — (source audio is stored on the clip) |
| Stems (2-stem, multi-stem, place on tracks) | ◐ request wired; result list gated until a finished stems job exists | ✅ | `POST /internal/studio/stems` · `POST /v1/music/stems`; `GET /studio/stems` |
| Persona from a clip's vocal / reuse in replace | ✅ | ✅ | `POST /internal/studio/persona` · `POST /v1/persona/create` |
| Cover-art generation from the editor | ✗ (lives on the song rail in Library/Create) | ✅ clip action | `POST /internal/studio/cover-image` · `/v1/music/cover-image` |
| Extend/Cover an uploaded file | ✅ from Library attach flow | ✅ | `POST /internal/studio/upload-extend|upload-cover` |
| Generation history per project | ◐ clip provenance strip (model, date, style) | ✅ project-level history | — (recorded in project data) |
| Natural-language arrangement edit | ◐ assistant answers + can commit a generated take; it does not re-arrange clips | ✅ “Studio AI” | `POST /v1/music` only |

## 6. Tracks & mixing

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Add audio / MIDI / import audio / import MIDI tracks | ✅ A / M / U | ✅ | — |
| Record with input picker + count-in | ✅ MediaRecorder → upload → take at playhead | ✅ | `POST /studio/uploads` (platform) → storage |
| Rename, reorder, duplicate, delete, colour | ✅ | ✅ | project `PATCH` |
| Volume / pan / mute / solo / arm | ✅ all live on the running graph | ✅ | project `PATCH` |
| Level meter per track | ✅ peak per track | ✅ | — |
| Master fader + main mute | ✅ | ✅ | — |
| Master peak + true-peak estimate | ✅ header readout (G10) | ✅ | — |
| Track EQ / filter / FX sends / dynamics | ◐ inside the plugin dock chain (EQ, compressor, filter, drive), **no sends** | ✅ sends + per-track panels | — |
| Volume / pan automation lanes | ✅ | ✅ | — |
| Copy/paste mix settings, reset mix | ✗ | ✗ (not evidenced in any capture or string) | — |
| Track groups A–D with collapse and group mix | ✗ | ✗ (not evidenced) | — |
| Mixer panel (strips + spectrum) | ✗ — **the reference has none** (S47: four footer tools, no mixer aria-label, Main is a chain) | ✗ | — |
| Master spectrum analyser | ✗ | ✗ (not evidenced; the row meter is level/spectrum-styled) | — |
| Master true-peak / loudness readout | ✅ peak/RMS/4× inter-sample estimate | ✅ | — |
| Track collaborator avatars | ✅ presence | ✅ | `GET/POST /studio/projects/:id/presence` (platform) |

## 7. Plugins & master chain

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Plugin catalog (760 px dialog) | ✅ 12 effect families (compressor, convolution, delay, distortion, drum bus, EQ, gate, limiter, reverb, rhythm gate, vocal, authored custom), MY PLUGINS above Audio effects | ✅ | — |
| Add / remove / reorder / bypass chain | ✅ real graph rebuild, live parameter updates | ✅ | — |
| EQ (bands, shapes, per-band handles) | ✅ curve + 6 shape buttons + Freq/Q/Gain | ✅ | — |
| Compressor (transfer curve, sidechain key) | ✅ sidechain lists every track pre/post-fader | ✅ | — |
| Convolution reverb (11 IRs, pre-delay, width) | ✅ real convolver | ✅ | — |
| Delay, filter, drive, chorus, others | ✅ | ✅ | — |
| Stereo Utility (Level / Width / Pan / Bass Mono) | ✅ mid-side implementation | ✅ (S21 dock) | — |
| Presets (save/apply/clear/default) | ✅ project-scoped user presets | ✅ | — |
| Preset stepper (‹ ›) | ✅ auditions Default / starter / saved presets without opening the menu | ✅ (S46) | — |
| Master chain (limiter, EQ, compressor, drive) | ✅ limiter lookahead/pre-gain/attack/release/link | ✅ | — |
| IR designer | ✅ our addition for custom impulses | ✗ | — |
| Plugin designer (“Build it” → catalog plugin) | ✅ authored through Suno's agent, saved to MY PLUGINS | ✅ | `POST /internal/studio/projects/:id/plugins/author`, `GET …/author/:jobId` |
| Local DSP for authored plugins | ◐ approximated by family | ✅ exact chains | — |
| Master reverb | ✗ (removed: master bus does not render it, D-034) | suggested by the UI only | — |

## 8. Editors: audio, MIDI, automation

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Audio clip editor band (S30) | ✅ 280 px settings column + zoomed waveform, warp markers | ✅ | — |
| Pitch / speed / stretch modes / formant / quantize | ✅ | ✅ | — |
| Loop / reverse / volume in dB | ✅ | ✅ | — |
| Piano roll (draw, move, resize, velocity) | ✅ | ✅ | — |
| Quantize, transpose, octave | ✅ | ✅ | — |
| MIDI instruments + synth voices | ✅ triangle / sine / saw | ✅ | — |
| Chord + arpeggiator modes | ✅ writes the expected notes | ✅ | — |
| On-screen keyboard, computer-key typing, Web MIDI | ✅ | ✅ | — |
| MIDI rendered into playback and export | ✅ | ✅ | — |
| Download MIDI (selection → one .mid) | ✅ 480 PPQ format 0 | ✅ | — |
| Get MIDI (audio → MIDI track) | ✅ needs a source generation | ✅ | `POST /internal/studio/midi` · `/v1/music/midi` |
| Automation panel | ✅ volume + pan points, drag/add/delete | ✅ | — |
| Modulation lanes (S32) | ✅ | ✅ | — |

## 9. Library

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Two-level library (tiles → list) | ✅ All Songs / Liked / Stems / Uploads + Workspaces + Studio Projects | ✅ | — |
| Search, filters, sort | ✅ filter menu, magnifier that expands | ✅ | — |
| Date grouping (Today/Yesterday/…) | ✅ collapsible headings | ✅ | — |
| Song detail rail (S100) | ✅ hero, meta, actions, tabs, cards, mini-player | ✅ | `GET /studio/generations/...` (platform) |
| Drag a row onto a lane | ✅ at the drop position | ✅ | — |
| Workspaces with counts | ✅ server-side counts | ✅ | platform `/web-music/workspaces` |
| Uploads tab | ✅ lists Studio imports | ✅ | `POST/GET /studio/uploads` (platform) |
| Stems tab | ◐ visible + disabled until a stems job exists | ✅ | `GET /studio/stems` |
| Liked | ◐ per-clip likes, not a song corpus | ✅ song corpus | — |
| Song row subtitle | ◐ tags instead of a description line | ✅ description | — |

## 10. Projects, versions, sharing

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| List / search / sort / pin / archive / tag | ✅ | ✅ | `GET /v1/studio/projects`, `PATCH …/:id` (mirror + local fields) |
| Duplicate / fork | ✅ | ✅ | `POST /v1/studio/projects/:id/fork` |
| Delete with confirm | ✅ | ✅ | `DELETE /v1/studio/projects/:id` |
| Automatic versions + named snapshots | ✅ server throttles to 1/20 s, keeps 50 | ✅ “Projects are saved automatically” | — **platform only**: `/studio/projects/:id/versions` |
| Restore a version | ✅ | ✅ | — platform only |
| Share link (view/edit, expiry, revoke) | ✅ | ✅ | — platform only (`studio_project_shares`) |
| Shared page (read-only, edit, fork) | ✅ `/studio/shared/[token]` | ✅ | `POST /internal/studio/projects/:id/resolve` (mirror resolution) |
| Comments (project + per-clip) | ✅ S55 clip notes + project thread | ✅ | — platform only (`studio_project_comments`) |
| Presence + live polling | ✅ cursors, playhead, updates endpoint | ✅ | — platform only |
| Save conflict (409) reload/overwrite | ✅ | ✗ silent overwrite | `PATCH …/:id` with `expected_updated_at` |
| JSON export / import | ◐ export yes, import no | ✅ export; import not captured | — |
| Suno mirror link/refresh/merge/archive | ✅ “keep mine / load Suno”, status badges | n/a (it *is* Suno) | `/internal/studio/projects/:id/{link,sync,refresh,merge,enqueue,status,resolve,archive}`, `/internal/studio/projects/status`, `/internal/studio/sync/health` |

## 11. Settings, help, shortcuts

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Settings (ghost drag, Learn, first-run) | ✅ three captured panes: Performance · Window management · Content (auto-stretch + advanced content) | ✅ Performance / Window management / Content | — |
| Learn menu (206 px popover) | ✅ Keyboard Shortcuts · Learning Center · What's This? | ✅ + YouTube Tutorials | — |
| Learning Center | ✅ in-app five-step tour | ✗ (video only) | — |
| Keyboard shortcut overlay | ✅ lists exactly what is bound | ✅ 40+ grouped shortcuts | — |
| What's This? hover cards | ✅ opt-in, default on | ✅ | — |
| Advanced content tools | ✅ Wavetable Designer + Impulse Response Designer, hidden when the setting is off | ✅ (gated the same way) | — |
| Full captured shortcut set | ◐ most bound (loop, metronome, mute/solo, rename, add track, panels, split, zoom) | ✅ | — |

## 12. Reliability, accessibility, state

| Feature | CAMXORA Studio | Suno Studio | musicapi |
|---|---|---|---|
| Save states (saved/saving/failed/offline) + retry | ✅ | ✗ silent autosave | — |
| Serialized writes, coalesced queue | ✅ | ✗ | `PATCH` accepts `expected_updated_at` |
| Offline draft + replay on reconnect | ✅ (e2e with the network toggled) | ✗ | — |
| `beforeunload` guard while unsaved | ✅ | ✗ | — |
| Axe-clean Studio routes | ✅ 0 violations (editor, home, shared) | unknown | — |
| Screen-reader labels on icon controls | ✅ | ✅ | — |
| Coarse-pointer 44 px targets | ✅ | unknown | — |
| Reduced motion | ✅ respects the media query | unknown | — |
| Responsive gate below 768 px | ✅ | ✅ | — |
| Moderation refusal surfaced | ✅ provider message on the clip / dialog | ✅ | provider error envelope |
| Test coverage | ✅ 339 Vitest, 163 Playwright, platform 3407 | n/a | contract tests in platform_api |

---

## 13. musicapi — the third column, expanded

`musicapi` (`localhost:4003`) is the **provider adapter + mirror**. It never renders audio,
never holds the arrangement maths, and never sees a browser. Everything the DAW does locally
has no endpoint here; everything paid or provider-backed does.

### 13.1 Studio project mirror

| Endpoint | Purpose |
|---|---|
| `GET /v1/studio/projects` | list the caller's projects (limit/offset/total) |
| `POST /v1/studio/projects` | create (title, major_version, bpm, time_signature, data) |
| `GET /v1/studio/projects/:id` | read the full document |
| `PATCH /v1/studio/projects/:id` | save the document (version-checked) |
| `DELETE /v1/studio/projects/:id` | delete |
| `POST /v1/studio/projects/:id/fork` | duplicate as the caller |
| `POST /internal/studio/projects/:id/link` | attach a Suno project id to ours |
| `POST /internal/studio/projects/:id/sync` | push/pull a reconciliation pass |
| `POST /internal/studio/projects/:id/enqueue` | queue a push without waiting (editor save path) |
| `GET /internal/studio/projects/:id/status` | mirror status for the badge |
| `POST /internal/studio/projects/:id/refresh` | pull the latest Suno document |
| `POST /internal/studio/projects/:id/merge` | merge chains per track entry, keep local-only effects |
| `POST /internal/studio/projects/:id/resolve` | resolve a share/mirror document |
| `POST /internal/studio/projects/:id/archive` | archive on the provider |
| `POST /internal/studio/projects/status` | batch status for the project list |
| `GET /internal/studio/sync/health` | sync subsystem health |

### 13.2 Generation and transforms

| Endpoint | Purpose |
|---|---|
| `POST /v1/music`, `/v1/sounds`, `/v1/lyrics` | song / sound-effect / lyrics jobs |
| `POST /v1/music/{extend,cover,stems,remaster,add-vocals,add-instrumental,mashup,replace-section,cover-image,midi,recovery,wav}` | public clip operations |
| `POST /v1/generate/{boost,upload-extend,upload-cover}` | upload-based transforms |
| `POST /v1/mp4/generate` | cover-art video render |
| `POST /internal/studio/{extend,cover,add-vocals,add-instrumental,replace-section,remaster,mashup,stems,midi,cover-image,persona,video}` | the editor's service-to-service variants (same provider calls, platform owns credits) |
| `POST /internal/studio/upload-extend`, `…/upload-cover` | uploaded-audio transforms |
| `POST /internal/studio/assets/import` | push bytes into the account's own Suno upload pipeline |
| `GET /internal/studio/clips/:clip_id/wav` | clip audio as WAV |
| `GET /internal/studio/lyrics/:clip_id` | lyrics + aligned words |
| `GET /internal/studio/jobs/:id` | job status for internal callers |
| `POST /internal/studio/projects/:id/plugins/author` + `GET …/author/:jobId` | designed-plugin authoring + idempotent polling |

### 13.3 Voice

| Endpoint | Purpose |
|---|---|
| `POST /v1/voice/{record,validate,phrase,apply,extend,generate}` | raw sample → phrase → persona → generation |
| `POST /v1/persona/create` | persona from a finished song |
| `POST /internal/studio/persona` | editor persona request |
| `GET /internal/studio/voice/phrase` | verification phrase |
| `POST /internal/studio/voice/{sample,verify}` | sample extraction + verification |
| `POST /v1/upload/{init,register}`, `GET /v1/upload/status/:id` | reference-audio upload lifecycle |

### 13.4 Account / job plumbing used by Studio

`GET /v1/credits` · `GET /pricing` · `GET /models` · `GET /v1/task/:id` ·
`GET /v1/music/wav/:id` · `GET /v1/lyrics/:id` · `GET /health` · `GET /openapi.json` ·
admin/routing/mail/payment surfaces (not Studio).

### 13.5 Fixed boundaries (deliberate)

| Concern | Owner | Why |
|---|---|---|
| Arrangement, clips, automation, MIDI notes | **browser** (`StudioEditorShell` + document `data`) | no round trip per edit; the document is the sync unit |
| Mixing, plugin DSP, fades, bounce | **browser** (`WebAudio`, `OfflineAudioContext`) | server render is not wired; bounce reuses the browser graph |
| Rendering / export bytes | **browser** (`lib/studio-export.ts`, WAV) | no upload of a mixdown to the API |
| Versions, shares, comments, presence, uploads | **platform_api** | user identity + Postgres live there; musicapi has no tables for them |
| Credits, pricing, subscription | **platform_api** | `pricing` table is the single source |
| Provider account pool, key routing, job ledger | **musicapi** | never exposed to a browser |

---

## 14. Honest gap list

### 14.1 In Suno Studio, absent here

Nothing that the captures or shipped strings prove. The 2026-11-14 completion pass closed the
last evidenced surfaces:

| Was missing | Now |
|---|---|
| Settings → **Window management** (S10) and **Content** (S11) panes | Three-pane Studio Settings dialog; whole dialog closes on Escape |
| **Advanced content features** gating | Impulse Response Designer and Wavetable Designer entries are hidden when off, not disabled |
| **Wavetable Designer** (N-14) | Real designer (16 partials, presets, preview) stored in `data.wavetables`; MIDI clips play it through `createPeriodicWave` in playback, export and bounce |
| **Auto-stretch added audio** (S11) | Tempo detection on the peak envelope; uploads snap to the project tempo when the beat is steady (`lib/studio-tempo.ts`) |
| **Clip-level FX** (§34 “Remove FX”) | Clips carry their own insert chain, applied clip → clip FX → gain/fade → track chain, and removed by the clip menu |
| **Stereo Utility** (S21 dock) | Added with Level / Width / Pan / Bass Mono and a real mid-side implementation |
| **“Already on Master”** duplicate guard | Master refuses a second limiter and names it in the menu |
| **Export scopes** (S49) | Menu now reads Full Song · Selected Time Range · Multitrack, with the captured toasts |
| **My Projects thumbnails** (S04) | Cards draw a mini-timeline from a bounded `thumb` summary in the list response |

**Deliberately absent (negative captures, not gaps):** the mixer surface (S47), FX sends and
track groups (never evidenced), master spectrum, mastering presets, project JSON import, and
the Learn menu’s YouTube Tutorials row (product decision).

### 14.2 Ours, beyond the capture

- Four save states, retry, 409 reload/overwrite, serialized writes, offline draft + replay,
  `beforeunload` guard, focus management after delete, axe-clean routes, 44 px coarse-pointer
  targets, IR designer, JSON export, −1 dBFS export normalisation, per-clip comments,
  structured e2e suite (163 tests).

### 14.3 Stale documentation found during this audit

| File | Claim | Reality |
|---|---|---|
| `SUNO_STUDIO_FEATURE_INVENTORY.md` | MIDI, marquee, copy/paste, speed, offline, onboarding marked `—` | all implemented; the ledger's `Ours` column was not updated |
| `SUNO_STUDIO_GAP_ANALYSIS.md` | “MIDI not in the web Studio (desktop only)” | piano roll, chord/arp and Web MIDI ship here |
| `PIXEL_PARITY.md` | Heal Edits / Get MIDI / Remove FX “disabled with reasons” | all three are wired (e2e: `studio-new-features`, `studio-midi-export`, `studio-clip-menu`) |
| This audit, first draft | listed a mixer, sends, groups, mastering presets and MP3 as “Suno has, we do not” | none of them appear in a capture or a shipped string; S47 proves the mixer is absent |
| `studio-pixel.spec.ts` | Learn popover has the YouTube row | fixed with the row removal (commit `4277bf6e`) |

---

## 15. Screenshots

| Ours | Reference |
|---|---|
| [`compare/ours-editor-1689.png`](compare/ours-editor-1689.png) | `reference/screens/S17-editor-loaded-project.jpeg` |
| [`compare/ours-editor-library-1689.png`](compare/ours-editor-library-1689.png) | `reference/screens/S52-library-workspaces.jpeg`, `S53-library-songs.jpeg` |
| [`compare/ours-editor-1280.png`](compare/ours-editor-1280.png) | `reference/screens/S63-1280px.jpeg` |

Captured with a 12-track / 44-clip project at 174 BPM so the frame density matches the
reference demo, at DPR 1.
