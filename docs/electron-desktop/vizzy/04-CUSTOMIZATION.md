# Vizzy — Customization After the Port

> **Document ID:** CAMXORA-ED-VZ-04
> **Version:** 1.0.0
> **Status:** Draft
> **Rule:** Port the whole editor first. Customize only after the parity baseline is stable.
> **Last updated:** 2026-11-19

---

## 1. Guardrails

1. **No renderer changes during the port.** The first milestone is "it runs exactly as Rea
   runs". Customization starts only after VZ-T1 … VZ-T12 pass.
2. **Customization is a layer, not a fork.** Prefer adapters, token overrides and new
   panels around the editor. Change Rea internals only when the reference behaviour is
   wrong, and record why.
3. **Every customization is reversible.** Keep the upstream patch set small and documented
   in [`02-MODULE-MAP.md`](02-MODULE-MAP.md) §3.
4. **Feature parity is a gate.** A visual change may not remove a capability.

---

## 2. Customization backlog

### 2.1 Brand and chrome

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C01 | Camxora token override | Surfaces/text/accent match [`06-DESIGN-SYSTEM.md`](../06-DESIGN-SYSTEM.md); no layout change | P0 |
| VZ-C02 | Shell strip | Above the view: "Vizzy · project · Saved/Unsaved · Close"; no duplicate menus | P0 |
| VZ-C03 | Sidebar collapse | 64 px rail while Vizzy is active; restores on close | P0 |
| VZ-C04 | Account chip | Shows the Camxora user, not a Vizzy sign-in | P0 |
| VZ-C05 | Remove "Donate"/promo links | Replaced by Camxora Help entries | P1 |
| VZ-C06 | Release chip | Shows the Camxora desktop version + a "What's new" entry | P1 |
| VZ-C07 | Window title | Reflects the project name and dirty state | P1 |

### 2.2 Project library

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C10 | Native projects | New/Open/Save/Save As use native dialogs and `.camxora-vizzy.json` | P0 |
| VZ-C11 | Recent projects | SQLite list with thumbnail, last opened, duration | P0 |
| VZ-C12 | Project browser | Grid/list with search, sort, rename, duplicate, delete | P1 |
| VZ-C13 | Autosave/recovery | Recovery prompt after a crash; keep the last 3 autosaves | P0 |
| VZ-C14 | Thumbnail capture | Capture the current stage as the project thumbnail | P1 |
| VZ-C15 | Import Vizzy exports | One-click import from a `.json` file or drag/drop | P0 |
| VZ-C16 | Export project bundle | Project JSON + media in a ZIP for sharing | P2 |
| VZ-C17 | Cloud sync | Deferred; requires a product decision and a backend contract | — |

### 2.3 Templates and marketplace

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C20 | Template picker | Lists marketplace-installed templates plus built-ins | P0 |
| VZ-C21 | Install refresh | Marketplace install updates the picker without restart | P0 |
| VZ-C22 | Template metadata | Name, author, kind, licence, thumbnail | P1 |
| VZ-C23 | Template packs | Group templates by pack; uninstall/reinstall | P2 |
| VZ-C24 | No legacy conversion | Old Camxora video templates are not converted in 2.0.0; the UI states the policy | P0 |
| VZ-C25 | Pipeline binding inspector | Mark nodes as audio/background/logo/title/artist/album/palette and validate | P0 |
| VZ-C26 | Renders panel | Queue, progress, cancel, retry, open output | P0 |

### 2.4 Export and pipeline

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C30 | Native FFmpeg export | H.264/AAC MP4 by default; progress/cancel; validated output | P0 |
| VZ-C31 | Hardware encode | Optional NVENC/QSV/AMF with probe + fallback | P2 |
| VZ-C32 | Export presets | 1080p/720p/vertical/square, fps, bitrate | P1 |
| VZ-C33 | Audio settings in export | Volume/mute/bass/rate/compressor applied exactly as preview | P0 |
| VZ-C34 | Export queue | Multiple projects queued; per-item status | P2 |
| VZ-C35 | Pipeline hand-off | Send an exported video into the Camxora merge/upload pipeline; also render the project through the pipeline directly | P0 |
| VZ-C36 | Project duration | Export honours the project duration, not the audio length | P0 |

### 2.5 Editor UX

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C40 | Command palette | Camxora commands (open project, export, send to pipeline) added under a "Camxora:" group | P1 |
| VZ-C41 | Keyboard map | Show Camxora + Rea shortcuts in one help sheet | P1 |
| VZ-C42 | Toast/status | Export/save results use Camxora toasts and footer status | P0 |
| VZ-C43 | Error panel | A Vizzy error shows a recoverable panel with "Reload" and "Open log" | P0 |
| VZ-C44 | Onboarding | First-run overlay: 3 steps (media, preview, export) | P2 |
| VZ-C45 | Tutorial content | Replace Vizzy links with local help | P2 |

### 2.6 Telemetry and support

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C50 | Structured logs | Save/export/project errors go to the Camxora log with ids | P0 |
| VZ-C51 | Diagnostics | Vizzy version, project hash (not contents), FFT tier, GPU info | P0 |
| VZ-C52 | Crash report | View crash includes the last autosave id and stack | P1 |
| VZ-C53 | Usage counters | Local counts only (exports, projects opened) | P2 |

### 2.7 Future native migration

| ID | Change | Acceptance | Pri |
|---|---|---|---|
| VZ-C60 | `VizzyHost` seam | All native interaction goes through the adapter interfaces | P0 |
| VZ-C61 | Renderer abstraction | A native renderer can replace the view without changing the shell | P2 |
| VZ-C62 | Shared project schema | Keep the Rea JSON schema as the interchange format | P0 |

---

## 3. What not to customize in 2.0.0

- Do not restyle the editor's internal panels beyond tokens; it destabilises parity.
- Do not change node defaults, shader math, analyser transforms or preset data.
- Do not add Camxora-only fields to the inner project JSON; use the wrapper.
- Do not remove Vizzy features because they look unused; hide them with a flag if needed.
- Do not replace ffmpeg.wasm until the native path passes the export matrix.

---

## 4. Sequencing

```
P7.0  Host + boot + COOP/COEP + open fixture
P7.1  Native project I/O + recent + autosave
P7.2  Media bridge + picker + protocol
P7.3  Native export bridge (image, then video)
P7.4  Parity harness + 10-project matrix
P7.5  Tokens + shell strip + account + toasts
P7.6  Marketplace template picker + refresh
P7.7  Pipeline hand-off + polish
```

Customization starts at P7.5. Anything earlier is a port fix, not a design change.

---

## 5. Definition of Done

- [ ] VZ-C01 … VZ-C62 implemented or explicitly deferred (including VZ-C24 … C26).
- [ ] The editor runs with the Camxora theme without layout regressions.
- [ ] Native project round-trip and native export pass.
- [ ] Marketplace templates appear without restart.
- [ ] The parity baseline is unchanged after customization.
- [ ] All new behaviour is documented in the Vizzy help sheet.
