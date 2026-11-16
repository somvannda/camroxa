# CAMXORA Studio QA — consolidated defect ledger (Agent C)

**Date:** 2026-11-16
**Consolidator:** Agent C, branch `qa/studio-consolidation` (base `origin/main` @ `46f68025`)
**Inputs (read-only, copied verbatim into this worktree):**
`2026-11-16-agent-a-functional.md` (Agent A, real-UI functional audit) and
`2026-11-16-agent-b-parity.md` (Agent B, screen/string parity audit).
**Method:** every claim below was re-derived from the shipped code
(`camxora.com/components/studio/**`, `camxora.com/lib/studio-*.ts`,
`platform_api/services/web_music_service.py`, `camxora.com/app/globals.css`) and, where
relevant, checked against the two agents' own evidence files. **Nothing was run:** no
server, no browser, no test suite. "Confirmed" below means *the code does what the claim
says*, not "I reproduced it in a browser".

---

## 1. Summary counts

| | Count |
|---|---|
| Claims audited | 18 (A: D1, D2, D3, O1, O2 · B: 13 ranked parity defects) |
| Ledger rows after dedupe | **19** (17 + 1 new defect found during consolidation, 1 merged) |
| **PRODUCT DEFECT** | **11** |
| **COSMETIC** | **7** |
| **EVIDENCE DEFECT** | **1** |
| **CANNOT VERIFY** (as a whole row) | **0** |
| Sub-claims withdrawn or overstated inside otherwise-valid rows | 6 |
| Sub-claims that cannot be verified | 1 (B9 blank catalog tile) |
| Defect promoted from B's "capture staleness" bucket | 1 (C1, no timeline waveforms) |

**Headline:** D1 and D2 are **both confirmed in code, exactly as A described them.**
D1 is the only data-loss defect and the only one whose blast radius is permanent.
B's 13 ranked parity defects hold up in substance, but six of them contain at least one
sub-claim that the code contradicts, and B's habit of writing off "no waveform" frames as
*stale captures* hid a real rendering defect (C1) that A's independent screenshots also show.

**Cross-check of the two audits' own headline numbers**

| Agent | Reported | Consolidation verdict |
|---|---|---|
| A | 47 PASS · 3 FAIL · 1 BLOCKED | FAILs all real; D1 high/data-loss, D2 medium, D3 cosmetic. A's PASS set is not re-verified here (see §6). |
| B | 15 MATCH · 44 DELTA · 14 CANNOT JUDGE | 13 "real" DELTAs ≈ correct count; 11 stand as defects, 2 are mostly real with overstated sub-claims, and B's own 31 "capture-state" items contain 1 real defect (C1). |

---

## 2. Defect ledger

Class legend: **PD** = product defect · **COS** = cosmetic · **ED** = evidence defect ·
**CV** = cannot verify.

### 2.1 Agent A — functional findings

| ID | Claim (as filed) | Class | Code path that causes it | Does the claim hold? | Dedupe / notes |
|---|---|---|---|---|---|
| **A-D1** | Editing while "Loading project…" is visible replaces the server document with `{tracks:[…]}` — all clips gone, permanently. **High.** | **PD** | `StudioEditorShell.tsx:1893-1911` (`writeProjectData` builds `{...currentData(), tracks}` where `currentData()` is `{}` because `projectRef.current` is still `null`), `:297` (`projectVersionRef` starts `null`), `:1965-1980` + `:1990` (`expected = null` ⇒ no `expected_updated_at` is sent), `lib/studio-api.ts:250` (omits the field when null), `platform_api/services/web_music_service.py:3776-3801` (`data = COALESCE($7::jsonb, data)` — **whole-document replace, no key merge**), `:3754` (conflict check only runs when `expected_updated_at` is present). Gate that is missing: `:3976-3980` (`letter === "a"` → `addTrack()`), `:3817` (the only gate is "a dialog is open"), `globals.css:4967` (`.se-loading` is a 12 px toast, not a blocking overlay). | **CONFIRMED**, mechanism exactly as A stated. A's one imprecision: the loss is not "one GET round-trip" in the sense of a race with the user's intent — it is unconditional for *any* document write before the first load resolves (add-track, drop-a-song, mute, etc. all funnel through the same choke point). | Deep dive §3. This is the only defect in the set that destroys user data. |
| **A-D2** | Rename, then the next edit 409s with a false "changed in another tab" dialog. **Medium.** | **PD** | `StudioProjectMenu.tsx:337-348` (`submitRename` → `updateStudioProject(projectId, { title })`, **no** `expectedUpdatedAt`), `web_music_service.py:3787` (`updated_at = now()`), `StudioEditorShell.tsx:5725` (`onRenamed` only copies `title` into state; the rename response's fresh `updated_at` is **discarded**), `:1138` (`projectVersionRef` is re-synced from `project.updated_at` every render ⇒ stays stale), `:1990` + `web_music_service.py:3754-3765` (stale value sent, `>0.001 s` ⇒ `ConflictError` 409). | **CONFIRMED.** A's write-up is accurate; the "rename PATCH bumps `updated_at`" and "`onRenamed` only copies the title" are both literally true. | Deep dive §4. Note the **same defect exists on the second rename path**, `saveNameThenShare` (`StudioProjectMenu.tsx:386-398`) — "name project before sharing" then edit will 409 the same way. Neither A nor B mentioned that. |
| **A-D3** | First recorded take is titled "Take 2" when the track already has a clip. **Low.** | **COS** | `StudioEditorShell.tsx:1459` `const take = (owner?.clipIds.length ?? 0) + 1;` → `:1470` `title: \`Take ${take}\``. Counts **clips**, not takes. | **CONFIRMED.** Log agrees: `before:1` lane, recorded `title:"Take 2"` (`evidence-a/12-final-verify.console.log`). | Real bug, cosmetic impact. Distinct from B13's take-band ✕ (different surface, same feature). |
| **A-O1** | Success toast "can expire before a long render finishes" (bounce). | **ED** | `StudioEditorShell.tsx:4865` sets "Bouncing …" at start; `:4917` sets the **success** toast *after* `renderMix` + upload resolve; `:4975-4979` clears it 6 s later. | **Observation unproven, mechanism contradicted.** The success toast is created *after* the render, so it cannot expire *during* it. A's log shows `toast:""` at one sample point and no screenshot — consistent with a 6 s transient being missed by polling. | Downgraded from "observation/behaviour note" to an **evidence defect**: no image, one empty string, wrong stated cause. The legitimate residue is "a single 6 s toast is a weak confirmation for a 15 s operation" — a UX opinion, not a filed defect. |
| **A-O2** | Assistant panel takes over the left column; track headers unreachable. | **COS** | `globals.css:4775-4779`: `.se-shell.has-assistant .se-tracks{display:none}` — the track rail is **removed from the layout**, not just covered; `.se-assistant` is `position:fixed;left:8px`. Toggle at `StudioEditorShell.tsx:5714`, `:6215`. | **CONFIRMED and slightly understated by A** ("not reachable" — it is `display:none`, so arm/mute/options/Add-track do not exist while the panel is open). | This is a deliberate rule with a stated rationale (give the assistant a column), so it is a **product decision**, not a bug. Classed cosmetic; it needs an explicit call, not a patch. A's own screenshot `evidence-a/02-gen-assistant.png` proves it. |

### 2.2 Agent B — the 13 ranked parity defects

B's numbering below is its §9 rank. "Verdict" says whether the code backs the claim.

| ID | B's defect (abridged) | Class | Code path | Verdict vs B | Notes |
|---|---|---|---|---|---|
| **B1** | Shortcuts overlay: one centred column, no search, no group headers, no header ✕, lower-case title. | **PD** | `StudioLearn.tsx:290-314` — `role="dialog"` → `<div className="se-dialog">` → `<h2>Keyboard shortcuts</h2>` (`:298`, lower-case "s"), `<ul>` of `SHORTCUTS` (`:300-305`), bottom "Close" pill (`:307-311`). No `<input>`, no headings, no ✕. Row source `lib/studio-help.ts:163+`. | **CONFIRMED** on every structural point. | B correctly flagged its own capture as stale (7 rows vs 57). The *code* is what fails, not the frame. `tests/e2e/studio-shortcuts.spec.ts` exists and asserts presence only. |
| **B2** | Start overlay ships 3 tiles instead of 5, no ✕, no "Browse Studio projects ›". | **PD** | `StudioOnboarding.tsx:81-99` — exactly 3 tiles ("Empty arrangement", "Create a song", "Open a project"); `:101-105` "Start empty" pill only; no close button anywhere in the component. Docstring `:11-14` states the omission is deliberate ("we only offer what this build can actually do"). | **CONFIRMED.** B's framing ("a captured control was deleted") is fair *except* that the component documents the decision — that makes it a product decision to revisit, not an oversight. | Side effect B noted is real: the overlay covers the empty editor, so S05/S16 cannot be judged from a frame. |
| **B3** | Transport centred (plus extra Stop, missing `<<`); footer centre is a dead "Add Track Effects"; master chain empty on the demo project. | **PD** | `StudioHeader.tsx:190` `.se-head-center` inside `globals.css:4616` `grid-template-columns:1fr auto 1fr` ⇒ geometrically centred. Stop `StudioHeader.tsx:270-272`. "Back to start" `:192-201` is `fa-backward-step` — no `fa-backward` rewind exists. Dead control `StudioFooter.tsx:119-128` — `disabled` is hard-coded (`:122`), so it is dead in **every** state, not just empty chains. Master chain: `lib/studio-seed.ts:71-75` seeds `{lanes:[…]}` only — no `masterChain`, no `tracks`, so a seeded/demo project always opens with an empty master rack. | **CONFIRMED** (B's "only when the chain is empty" understates the dead button). | The `<<`/Stop/centre trio is one small PR. The master-chain one is a **seeding** defect, not a dock defect — fix in `studio-seed.ts` (+ the demo project's data), not in the footer. |
| **B4** | Share dialog rewords the captured guarantee, prints a raw `window.location.origin` URL (localhost in the frame), hard-codes "expires in 7 days", offers no permission choice although the API supports `view`/`edit` and 1–90 days. | **PD** | `StudioProjectMenu.tsx:971-976` (reworded copy), `:979-985` (raw `<input value={shareUrl}>`), `:986-989` ("…not live collaboration. It expires in 7 days."), `:140-141` (`${window.location.origin}${share.path}`), `:379-383` (`createStudioProjectShare(projectId, 7, "view")` — both values hard-coded). | **CONFIRMED**, and the most user-facing of the set: the dialog makes a **contractual-sounding claim** the product does not enforce. | Recommend splitting: (a) copy/permission honesty (small), (b) origin-relative link (trivial — render `share.path`, copy the absolute URL on click). |
| **B5** | Additive rows interleaved *inside* captured menu sequences: Import project…, Send to Suno Sync, Bounce track, 11 clip-menu rows, format toggle + Normalise above the export scopes; plus `Download WAV` vs `Download .WAV`, title-cased accelerators, red Delete. | **PD** | Project menu `StudioProjectMenu.tsx:446-494` (Import… at `:465` between Duplicate and Version History; Send to Suno Sync `:478-480` between Share and Open-a-copy-in-v1). Track menu `StudioTrackPanel.tsx:340-359` (Bounce between Collapse and Duplicate), `:363-370` (`className="danger"` on Delete). Clip menu `StudioEditorShell.tsx:6726` ("Download WAV"), `:6739` (Download MIDI between `.WAV`/Get MIDI), `:6762` (Add FX… before Remove FX). Export `StudioHeader.tsx:369-405` (format group + Normalise above Full Song). Accelerators `StudioEditorShell.tsx:6411` ("Ctrl C"), `:6442` ("Backspace"). | **CONFIRMED.** B's sharpest catch is also correct: `FUNCTIONAL_STRINGS` "Download .WAV" is satisfied by a **comment**, `StudioEditorShell.tsx:3591` (`/** Clip menu — Download .WAV … */`), not by the button. | This is the biggest "volume vs severity" item: ~8 small independent edits. Dedupe note: A's D2/D3 touch the same files but nothing in A duplicates these rows. |
| **B6** | Clip info rail: header below the top bar instead of inside it; no cover art, no date, no like/overflow; no Remix-adjacent preview player; 300 vs **340** px. | **PD** | `StudioClipInfo.tsx:128-134` (`se-inspector-head` is the rail's own row), `:137-147` (hero = colour swatch + title + date), `:149-161` (Remix), `:163-169` (`se-clip-player` with a `Waveform`), `globals.css:5019` (`position:fixed;top:8px` + `padding-top:44px` under the 52 px header). Width `StudioEditorShell.tsx:182` `LIBRARY_W = 360` → passed at `:5946`. | **Mostly confirmed, three corrections:** (1) the **date does exist** (`:145`, `sourceDate()`); (2) a **preview player does exist** (`:163-169`) — what the capture shows as "a bare green line" is the same broken waveform as C1; (3) the rail is **360 px**, not 340. | What genuinely fails: cover art (colour swatch), the like/dislike/overflow cluster, header placement, width. B's "no date / no player" are **overstatements** caused by reading a frame rather than the component. |
| **B7** | Hidden-tracks popover: "Unmute all" vs captured "Mute all"; text pills instead of speaker/eye icons; no `shift alt H` hint. | **PD** | `StudioTrackPanel.tsx:651-653` ("Unmute all"), `:635-648` (two `.se-pill` text buttons "Show"/"Mute"), `:654-656` ("Show All Hidden Tracks" with no accelerator `<span>`). Header ✕ at `:620-630` (current implementation). | **CONFIRMED.** B also correctly separates the stale capture (old 245 px inline panel) from the surviving deltas. | The binding exists (`lib/studio-help.ts` "Shift Alt H") but is undocumented in the UI it belongs to. |
| **B8** | Learn menu is ~16 px too narrow → "Keyboard Shortcuts" and "shift ?" each wrap to two lines. | **COS** | `globals.css:5363` `.se-learn-menu{min-width:206px}`; row `:5364` `height:44px` with `white-space` unset; markup `StudioLearn.tsx:233` (`<Icon/> Keyboard Shortcuts <span>shift ?</span>`). | **CONFIRMED** — and visible in B's own frame (`ours-learn-menu.png`): both strings wrap, row height grows. | Trivial one-line CSS fix (`min-width` or `white-space:nowrap`). Same component as B1, so batch them. |
| **B9** | Plugin surfaces: blank tenth catalog tile, identical generic previews, missing ⋯ in the catalog header, "No impulse response" where the capture says "NO ASSET LOADED", two placeholder tiles instead of three. | **COS** | `StudioPluginDock.tsx:1231-1251` header = title + search + ✕ only (**no ⋯**). `:292` "No impulse response". `:621-631` `PREVIEW_PATHS` has **9** entries for **10** plugins (`lib/studio-plugins.ts:88-235`), so `:634` `PREVIEW_PATHS[id] ?? "M0 30 H200"` gives exactly **one** flat-line tile (`stereoUtility`). Ghost rail `:1197-1216` = `["compressor","reverb","delay"]` minus what's already in the chain, `.slice(0,3)`. | **Partly contradicted:** "every tile's preview art is the same generic curve" is false (9 of 10 are bespoke). "Two placeholders instead of three" is by design (`slice(0,3)` minus present plugins) and commit `3f96ba1d` explicitly removed the Reverb ghost. The **blank tenth tile cannot be verified** — there is no unnamed plugin in the data. | Real residue: missing ⋯, "No impulse response" vs "NO ASSET LOADED", one generic fallback preview. The blank tile is a **CANNOT VERIFY** sub-claim. |
| **B10** | Clip editor / MIDI lanes: no overview strip; note-rows drawn inside automation lanes; stretch modes as inline pills instead of stacked rows with ⓘ; no collapse control in the Clip Settings header. | **COS** | `StudioAudioEditor.tsx:229-234` — header is `Clip Settings` + ✕, **no collapse/minus** (confirmed). `:306` `.se-audio-modes` `role="radiogroup"` = inline pills (confirmed). `StudioMidiEditor.tsx:657-719` — velocity/bend/mod lanes are a separate 64 px band; no overview/zoom strip anywhere in the file. | **Confirmed for the header and the stretch pills.** The "note rows inside the automation lane" claim is layout-dependent: `.se-midi-velocity` (`globals.css:4886`) has no row background, so it is only true if the piano gutter spans both bands — not provable from code, not worth litigating. | Lowest-confidence row in B's top 13; keep it in the "parity polish, retake capture first" bucket. |
| **B11** | Library: key tag is an "≈" estimate or absent, BPM best-effort, project rows use a ☰ placeholder, Workspaces has no "See all", workspace avatars are letters. | **PD** | `StudioSongKey.tsx:34-38` (`if (!key) return null`; renders `≈ {tonic} {mode}`), `StudioSongTempo.tsx:40-41` (`if (!bpm) return null`; nothing on a low-confidence read), `StudioLibrary.tsx:481-483` (`fa-bars-staggered` ☰ instead of a thumb), `:383-395` (See all **is** implemented, gated on `workspaces.length > ROOT_ROWS` (=4), `:92`). | **Mixed.** Tags: **CONFIRMED** — both tags silently disappear, which A's own frame also shows ("V6 PRO OK" with no key/BPM). ☰: **CONFIRMED** (the real thumbnail component exists but is wired only into My Projects: `StudioProjectMenu.tsx:731`). "Missing See all": **CONTRADICTED** — it renders whenever there are >4 workspaces; the capture simply had ≤4. | This is the row where B most clearly mistook *conditional rendering* for *missing control*. It should be re-filed as "• project rows drop the real thumbnail that My Projects already renders". |
| **B12** | Chrome consistency: **translucent** My Projects panel, letter avatars, circular-vs-bare close buttons, `h:mm:ss` timestamps with a permanent Restore button, "Studio settings" casing, lost display-serif title. | **COS** | `globals.css:5268` `.se-dialog{…background:#1c1c1e}` — **opaque hex, no alpha**; `.se-projects-dialog{max-width:786px}` only (`:5269`). `:5297` `.se-dialog h2{font-size:24px}`. A 36 px circular close **already exists** (`:5313` `.se-dialog-x`) but My Projects uses a bare `.se-icon` ✕ (`StudioProjectMenu.tsx:636-643`). Timestamps `:581` `toLocaleTimeString()` (⇒ `h:mm:ss AM`), per-row Restore `:591-593`. "Studio settings" `:624`, `:801`. | **Mostly confirmed; the lead sub-claim is false.** "Translucent — track rows and clips legible through the panel" is **contradicted** by `background:#1c1c1e`. Title is 24 px, not 32. Everything else holds. | Since `.se-dialog-x` already ships, the circular-close fix is a one-line class swap — the cheapest parity win in the whole set. |
| **B13** | Low trio: empty take band carries an extra ✕; loop range marks one end; model picker dropped the captured custom-model row. | **COS** | `StudioTakeLanes.tsx:37-39` — the ✕ renders before the `rows.length === 0` branch (`:40-41`), so it is always present. `globals.css:5418` `.se-loop-handle{width:8px;height:16px;border-radius:3px}` while `lib/studio-help.ts:38` says "drag the **round** handle" (copy/geometry disagree — confirmed). Model picker `StudioEditorShell.tsx:6164-6172` = 3 models; the custom-model row was deleted in `3f96ba1d` **with a written rationale**. | **CONFIRMED** for the ✕ and the handle/copy mismatch. The model-picker item is a **documented product decision**, not an oversight — B is right that it is not on the allowed-divergence list, but wrong to imply it is unexplained. | "Marks one end only" is a capture-level observation I could not confirm in code (the ruler renders from `loopStart`/`loopEnd` state, `StudioEditorShell.tsx:778-779`). |

### 2.3 New defect found during consolidation

| ID | Defect | Class | Code path | Evidence |
|---|---|---|---|---|
| **C1** | **Timeline clip bodies never paint a waveform.** Every clip renders as a flat colour block. B filed this three times as "stale capture" (S17c, S25, S30); A's independent run shows the same thing. | **PD (Medium-High)** | `StudioTimeline.tsx:328-336` renders `<Waveform url={clip.audioUrl} …/>`; `Waveform.tsx:34-51` draws **only** inside `computePeaks(url).then(...)` and does nothing when the promise yields `null`; `lib/studio-peaks.ts:14-44` fetches then `decodeAudioData`s the URL and swallows every failure (`:36-38 catch { return null; }`) with **no retry, no error surface, no user-visible fallback**. A cross-origin audio host without CORS (the sandbox serves signed URLs from `127.0.0.1:9000`) fails `fetch`/`decode` and the clip stays blank forever. | Three independent frames, two agents: `evidence-a/07-lib2-add-clip.png`, `evidence-a/02-gen-assistant.png`, and B's `ours-editor-1689.png` / `ours-learn-menu.png` — all show coloured rectangles with titles and no peaks, on clips that demonstrably have `audioUrl` (A's log shows the uploaded/served URLs). |

Why this matters for consolidation: B used "the code renders a waveform, therefore the capture is stale" as a **falsifier** for three separate rows. That inference is invalid — the code *intends* to draw one, and it can silently not draw one. The parity audit therefore under-reported a real defect, and its §5 "captures that need refreshing" list is partly wrong: those frames are current, the renderer is broken.

---

## 3. Deep dive — A-D1 (data loss while "Loading project…")

### 3.1 What allows an edit during load

1. `StudioEditorShell.tsx:843-857` reads `?project=` into `projectId` in the **mount effect**. So `projectId` is non-null almost immediately.
2. `:913-952` then starts `getStudioProject(projectId)` and sets `loading = true` until it resolves (`:920`, `:947`). `loading` is initialised `true` at `:763`.
3. **Nothing reads `loading` to block input.** Grep confirms only four uses of `loading`: the auth skeleton (`:5277`), the onboarding `isEmpty` guard (`:6352`), and the "Loading project…" string (`:7446`). The keyboard handler at `:3776-4104` gates on dialogs only (`:3817`) and has no loading check.
4. `.se-loading` (`globals.css:4967`) is a **12 px toast pinned bottom-right** — it neither covers the UI nor sets `pointer-events`, so toolbar clicks, drags and shortcuts all land.
5. Pressing `a` reaches `:3976-3980` → `addTrack()` (`:3067-3084`) → `commitTracks([...tracks, next])` (`:3050-3053`).

### 3.2 What `persist()` sends

`commitTracks` calls `writeProjectData({ ...base, tracks: next }, …)` where

```
const base = currentData() as Record<string, unknown>;   // StudioEditorShell.tsx:3051
function currentData() { return (projectRef.current?.data || {}) as … }  // :1145-1147
```

`projectRef.current` is assigned from `project` at `:1136`, and `project` is still `null` because the GET has not resolved. So **`base` is `{}`** and the outgoing document is literally `{"tracks":[ {…one new track…} ]}`.

`persist()` (`:1959-1981`) → `performWrite()` (`:1983-2033`) with

```
const expected = projectVersionRef.current;   // :1990  → null (declared :297, only set at :1138/:1996)
```

and `updateStudioProject` (`lib/studio-api.ts:245-252`) does

```
body: JSON.stringify({ ...rest, ...(expectedUpdatedAt ? { expected_updated_at: expectedUpdatedAt } : {}) })
```

⇒ **no `expected_updated_at` key at all.**

### 3.3 What the server does with a document that omits `lanes`

`web_music_service.py:3737-3805`:

* `:3754` `if expected_updated_at is not None:` — skipped, so **no conflict check**.
* `:3776-3801` `UPDATE … data = COALESCE($7::jsonb, data) … RETURNING *` with `$7 = json.dumps(data)`.

`COALESCE` here only falls back when the **whole value is SQL NULL**; a JSON object `{"tracks":[…]}` is not NULL, so the entire `data` column is **replaced**. `lanes` is not merged, not preserved, not diffed. The two clips cease to exist, and `queue_studio_mirror(row)` (`:3804`) then propagates the emptied document to the Suno mirror.

A's log matches this byte for byte:

```
before = {keys:["lanes","tracks"], lanes:2, tracks:1, laneTitles:["Probe A","Probe B"]}
@0.6s  = {keys:["tracks"],        lanes:"missing", tracks:1, laneTitles:null}   ← after "a"
afterReload = same → clipsShown: 0
control (edit after load) = lanes still 2, tracks 1→2   ← the two clips survive
```

(`evidence-a/11-loading-data-loss.console.log` lines 7 and 12-13.)

### 3.4 Verdict and minimal fix

**A is right, on both the symptom and the mechanism.** The only correction: it is not a narrow race with the user's intent, it is a **structural hole** — *every* document write that happens before the first GET resolves destroys the document, and there are ~60 call sites of `writeProjectData` (`:567` … `:7262`) plus `insertClips` (`:3308`), `restoreDraft` (`:1861`), and `performWrite`'s own queued path. Any of them is sufficient.

**Minimal fix location: `StudioEditorShell.tsx:1893` (`writeProjectData`), one guard.**

```ts
function writeProjectData(next, label, nextTracks?) {
  // The document does not exist yet: a write now would replace the server's copy
  // with the empty object plus this one edit. Refuse until the first load lands.
  if (!projectRef.current) return;
  …
}
```

Why here and not elsewhere:

* It is the single choke point for document writes, so one guard covers add-track, drop-a-song, mute/solo, fades, splits — everything.
* It sits **before** `history.undo.push` (`:1900`), so no bogus undo entry is created.
* `persist()` should *also* refuse a document write while `!projectRef.current` (defence in depth for `restoreDraft`/`saveNow`, `:1867`/`:1938`), but that is belt-and-braces; the `writeProjectData` guard is the fix.
* **Do not "fix" this on the server by merging `data`.** Whole-document replacement is load-bearing: deleting the last clip legitimately sends a document without that clip, and a key-wise merge would make deletions impossible. The contract is right; the client is wrong to invoke it before it has a document.
* Follow-up (UX, not the fix): disable the transport/track controls and the `a`/`m`/`s`/`h`/`u` shortcuts while `loading`, and give `.se-loading` a real overlay. Without that, the guard turns a data-loss bug into a silent no-op — better, but still confusing.

**Test that should pin it:** extend `tests/e2e/studio-write-queue.spec.ts` (it already presses `a` and asserts the server document) with a case that `page.route`-delays the `GET /studio/projects/*` by ~1.5 s, presses `a` while `.se-loading` is visible, then asserts `data.lanes` is unchanged **and** that no PATCH was issued before the GET resolved. A unit-level companion belongs next to `tests/studio-api.test.ts`.

---

## 4. Deep dive — A-D2 (rename → false 409)

### 4.1 Where the cached `updated_at` lives

Three places, and the rename updates none of them:

| Holder | Where | Value after a rename |
|---|---|---|
| `projectVersionRef.current` | `StudioEditorShell.tsx:297` (declared `null`), re-synced **every render** at `:1138` from `project?.updated_at` | stale (old timestamp) |
| `project.updated_at` (`StudioProject` state) | set only by the load (`:924`), by `performWrite`'s response (`:1996-1999`), and by `loadSunoVersion` (`:1015`) | stale |
| the server row | `web_music_service.py:3787` `updated_at = now()` | **new** |

### 4.2 Why renaming does not update it

The rename is issued from a **sibling component** that talks to the API directly:

```
// StudioProjectMenu.tsx:343-347
const updated = await updateStudioProject(projectId, { title: next });   // no expectedUpdatedAt
onRenamed(updated.title || next);                                        // only the string survives
```

* `updateStudioProject` without `expectedUpdatedAt` (`lib/studio-api.ts:250`) omits `expected_updated_at`, so `web_music_service.py:3754` skips the precondition and `:3787` bumps `updated_at`. **The rename succeeds — which is exactly what makes the bug invisible.**
* `onRenamed`'s type is `(title: string) => void` (`StudioProjectMenu.tsx:55`), so the response's fresh `updated_at` is **thrown away at the component boundary**.
* The editor's handler (`StudioEditorShell.tsx:5725`) does `setProject(current => current ? { ...current, title: next } : current)` — title only.
* `:1138` then keeps `projectVersionRef` pinned to the old `updated_at` on every subsequent render.

The next edit calls `writeProjectData` → `persist` → `performWrite` with `expected = <old timestamp>`, and `web_music_service.py:3761` rejects when the difference exceeds **1 ms**:

```
if abs((current["updated_at"] - expected_updated_at).total_seconds()) > 0.001:
    raise ConflictError("This project changed since you loaded it. Reload before saving.")
```

### 4.3 Verdict and minimal fix

**A is right.** The rename succeeds, the version is dropped at the callback boundary, and the next write is a guaranteed 409 whenever the rename and the edit are more than a millisecond apart — i.e. always.

**Minimal fix location: the callback contract between `StudioProjectMenu.tsx:55/345` and `StudioEditorShell.tsx:5725`.**

Widen it to carry the version, e.g. `onRenamed: (next: { title: string; updated_at?: string | null }) => void`, pass `updated` through, and in the shell:

```ts
onRenamed={(saved) => setProject((current) => current
  ? { ...current, title: saved.title, updated_at: saved.updated_at ?? current.updated_at }
  : current)}
```

Because `:1138` already syncs `projectVersionRef` from `project.updated_at`, that single change fixes **both** rename entry points (`submitRename` `:337` and `saveNameThenShare` `:386`) with no new state. A tempting alternative — calling `persist` for the rename — is worse: it would route a title change through the document write path and resurrect D1 on any pre-load rename.

**Test that should pin it:** extend `tests/e2e/studio-project-menu.spec.ts::"project menu renames the project and the name survives a reload"` (it renames but never edits afterwards, which is why this shipped) with: rename → wait for the chip to update → press `a` → assert no "changed since you loaded" dialog, `.se-save` reaches "Saved", and the server document has 2 tracks. Unit companion in `tests/studio-project-menu.test.tsx`.

---

## 5. Evidence audit

### 5.1 Agent A

Checked every `NN-*.png` / `*.console.log` filename named in the report against `evidence-a/` (64 distinct references).

| Defect | Claimed evidence | Present? | Assessment |
|---|---|---|---|
| **D1** | `11-loading-data-loss.console.log` (before / @0.6s / @3.6s / @7.6s / after reload), `02-load-probe.png`, `03-load-probe-reload.png`, **`01-load-control.png`** | log ✅ (strong: full before/after document dumps + a control run) · probe shots ✅ · **`01-load-control.png` MISSING** | The control run's *numbers* are in the log (laneTitles preserved, lanes 2), so the experiment is still controlled — but the control **image** does not exist. `01-load-control.png` and `04-load-final.png` are referenced by the log itself and absent from the folder. |
| **D2** | `02-home-error.png`, `01-verify-rename-conflict.png`, `02-verify-keep-mine.png`, `12-final-verify.console.log` | all ✅ | Strong. The log carries `patchStatuses`-equivalent document dumps: server unchanged during the conflict, 2 tracks after "Keep mine". |
| **D3** | `12-final-verify.console.log` (`recorded:{title:"Take 2", duration:3.6…}`), `03-verify-record.png` | both ✅ | Sufficient (and the code confirms the off-by-one origin). |
| **O1** | console logs only | logs ✅, **no screenshot of the missing toast** | **Insufficient.** One `toast:""` sample, no frame, and the stated mechanism is impossible in the code (§2.1). Filed as an evidence defect. |
| **O2** | none cited | — | Prose only, but A's own `02-gen-assistant.png` proves it (left column is the assistant, track rail absent). Evidence exists by accident. |
| **O3 / O4** | `05-lib2-search-filters.png` etc. | ✅ | Not defects; notes. |

**Four additional missing files** break PASS rows rather than FAIL rows:
`04-lib-master-spectrum.png` (#35 master spectrum), `05-arrange-duplicate.png` (#18 duplicate),
`06-fx-remove.png` (#33 remove plugin), plus the two D1 files above. Those PASS verdicts still
have their console logs, but a reader cannot check the visual claim.
(`downloads/v4rcv-project.json` **does** exist — the report's path is correct, my name-only
sweep just could not see the subfolder.)

### 5.2 Agent B

B's method is static (no runtime), so "evidence" = a paired capture in `docs/studio/compare/`
plus a code line. Two different failure modes appear:

| Mode | Rows | Verdict |
|---|---|---|
| Backed by a frame **and** a code line | most of §2 (B1, B2, B4, B5, B7, B8, B12, B13) | Good. I re-read the frames for `ours-my-projects.png`, `ours-editor-1689.png`, `ours-learn-menu.png` and they show what B says (transport centred, dead footer button, 206 px menu wrapping, bare ✕, letter avatars, real thumbnails in My Projects). |
| **Frame is used as proof of absence**, but the control is conditional or already implemented | **B9** (blank tile — no unnamed plugin exists in the data), **B11** ("See all" — renders at >4 workspaces, `StudioLibrary.tsx:386`), **B12** ("translucent panel" — `background:#1c1c1e`), **B6** ("no date / no player" — both exist, `StudioClipInfo.tsx:145`, `:163-169`) | **Overstated / contradicted.** This is B's systematic weakness: absence in one frame is treated as absence in the product. |
| **Prose/spec only, no frame** | exactly one DELTA: **S38 model picker** (Ev = `S studio-pixel`) | Flagged by B itself; the code confirms 3 models, so the *fact* is safe even though the *pairing* is not. |
| **Frame present but does not show the subject** | S28 (clip colour submenu closed), S46 (preset popover closed), S48 (limiter absent), S56 (shared page stuck on "Loading project…"), S23/S29 (marker/take rows absent) | B labels most of these honestly in §5. Note **S56's "stuck on Loading project…" is itself suspicious** — it is the same state that enables D1, and nothing in B explored that. |

Verified independently: `ours-onboarding.png` and `ours-empty-project.png` are **byte-identical**
(sha256 `928A7A81…`), exactly as B claims — so S06 has no evidence of its own.

### 5.3 Claims with no evidence at all

* A's **O1** (toast expiry) — no image, mechanism contradicted.
* A's **O2** — no cited evidence (though a screenshot accidentally covers it).
* B's **S38** (model picker DELTA) — no capture, spec only.
* B's **"blank tenth catalog tile"** — no way to confirm from code or data.
* Neither agent covers **the two other rename entry points' side effects** (`saveNameThenShare`) or the **`insertClips` path into D1** — both found here by reading code, not evidence.

---

## 6. Not covered by either agent

Do not read this consolidation as full coverage. Explicitly out of scope of **both** audits:

**Agent A (functional) explicitly excluded:** responsive/narrow layout (single viewport
1689×1277), keyboard-only navigation beyond the shortcuts it pressed, accessibility (no axe
run), performance, the credit-charged plugin designer (**blocked**), real provider
generation/stem quality (both mocked), Suno Sync push, conflict branch "Reload theirs",
version-history restore, export scopes "Multitrack" and "Selected Time Range".

**Agent B (parity) could not cover:** anything behavioural (no server, no browser) — so
no motion/animation parity, no focus/trap/keyboard-order parity, no hover/pressed/disabled
state parity, no error/empty/loading state parity beyond what a still frame shows,
`CANNOT JUDGE` on 14 of its own 73 rows, and 31 of its 44 DELTAs dismissed as capture-state
(one of which, C1, is actually a defect). It also audited only the dark theme and only the
70 strings in `FUNCTIONAL_STRINGS.json`.

**Neither agent touched (gaps this report inherits):**

* **Agent C did not execute anything.** Every conclusion here is static code reading plus
  the two agents' logs. D1 and D2 are code-confirmed, not re-run.
* **The write/queue surface beyond D1-D2:** coalescing failure modes (`performWrite` drops a
  queued write on error, `:2020`), draft recovery vs queue races, `autoSnapshot` version
  spam, and offline replay (`:2056-2088`).
* **Presence/comments at scale**, the Suno mirror (`queue_studio_mirror`) and its conflict
  semantics, share permissions/expiry enforcement server-side, and the 409 "Reload theirs" path.
* **IMPORT/EXPORT contracts**: JSON import validation against a hostile document (B flagged
  the dialog, nobody audited the parser), MP3 encoder conformance, multitrack stems.
* **The rest of the product:** `musicapi/`, `platform_api/` (other routers), `admin_portal/`,
  auth, billing/credits, migrations, and the production deploy path — all outside both scopes.
* **Test-suite health:** whether the existing specs (79 studio unit files, 58 e2e specs)
  actually pass, and which of them are vacuous. Two known holes found here: nothing covers
  the loading-window write (D1), and `studio-project-menu.spec.ts` renames without editing (D2).
* **Accessibility of every defect below** — several (dead button, wrap, overlays) are
  likely a11y-relevant but no axe run was done by either agent.

---

## 7. Severity-ranked fix plan

Order = blast radius first, then user-visible truthfulness, then parity volume.
Effort: **S** ≤ half a day, **M** ≤ 2 days, **L** > 2 days. No production deploy (project hold,
`AGENTS.md`); all work stays on a branch off `main`.

| # | Fix | Effort | Files | Test that pins it |
|---|---|---|---|---|
| 1 | **D1 — refuse document writes until the project has loaded.** Guard `writeProjectData` on `!projectRef.current`; also guard `persist` for the draft/saveNow paths; then disable the transport/track controls + unmodified-key shortcuts while `loading` and make `.se-loading` a real overlay. | **S** | `components/studio/StudioEditorShell.tsx` (`:1893`, `:1959`, `:3776-4104`, `:7446`), `app/globals.css` (`.se-loading`) | `tests/e2e/studio-write-queue.spec.ts` — new case: delay `GET`, press `a` under the loading toast, assert `data.lanes` intact **and** no pre-load PATCH. Unit: `tests/studio-api.test.ts`. |
| 2 | **C1 — make timeline waveforms actually render.** Retry + surface failure in `computePeaks` (explicit `mode:"cors"`, one retry, cached negative result), and give `Waveform` a deterministic fallback (flat baseline or skeleton) instead of an invisible canvas; log the decode failure once. | **S–M** | `lib/studio-peaks.ts`, `components/studio/Waveform.tsx`, `components/studio/StudioTimeline.tsx` | `tests/studio-timeline.test.tsx` (canvas painted or fallback class present when peaks are null) + `tests/e2e/studio-persistence.spec.ts` assertion that `.se-clip-body canvas` is non-blank after load. |
| 3 | **D2 — carry the rename's `updated_at` back into the editor.** Widen `onRenamed` to a `{title, updated_at}` payload; set `project.updated_at` (and therefore `projectVersionRef`). Covers the share naming gate too. | **S** | `components/studio/StudioProjectMenu.tsx` (`:55`, `:337-348`, `:386-398`), `components/studio/StudioEditorShell.tsx` (`:5725`) | `tests/e2e/studio-project-menu.spec.ts` — rename → `a` → expect no conflict dialog, "Saved", server has 2 tracks. Unit: `tests/studio-project-menu.test.tsx`. |
| 4 | **B4 — stop the share dialog lying.** Relative-path link + copy-on-click absolute URL; surface the real `permission`/`expires_days` returned by the API (or drop the claim); align the copy with the captured guarantee. | **S–M** | `components/studio/StudioProjectMenu.tsx` (`:140-141`, `:379-383`, `:971-989`), `lib/studio-api.ts` (`createStudioProjectShare` params) | `tests/e2e/studio-share-gate.spec.ts` — assert no `http://localhost` in the dialog, the expiry text matches the created share, permission selectable. |
| 5 | **B3 — footer/master-chain truth + transport parity.** Footer centre shows the **master** chain always (`StudioEditorShell.tsx:7314-7321`), never a `disabled` button (`StudioFooter.tsx:119-128`); seed `masterChain` in `studio-seed.ts`; move transport into the left flow / add `<<`. | **M** | `components/studio/StudioFooter.tsx`, `StudioEditorShell.tsx`, `StudioHeader.tsx`, `app/globals.css` (`.se-head`), `lib/studio-seed.ts` | `tests/e2e/studio-master.spec.ts` + `studio-transport.spec.ts`; `tests/studio-seed.test.ts` for the seeded chain. |
| 6 | **B2 — onboarding parity or an explicit decision.** Either reach 5 tiles / ✕ / Browse pill, or record the divergence in `CLONE_DEFINITION.md` (the component already argues the case). | **M** | `components/studio/StudioOnboarding.tsx`, `app/globals.css`, `docs/studio/CLONE_DEFINITION.md` | `tests/e2e/studio-home.spec.ts` (tile count, ✕ closes, Browse link present-or-documented). |
| 7 | **B1 — shortcuts overlay to spec.** Search field, five group headers, header ✕, two columns, capitalised title. | **M** | `components/studio/StudioLearn.tsx` (`:290-314`), `lib/studio-help.ts` (group metadata), `app/globals.css` | `tests/e2e/studio-shortcuts.spec.ts` — search filters rows, groups render, ✕ closes; `tests/studio-learn.test.tsx` already covers the dialog shell. |
| 8 | **B5 — menu displacement + string/casing/role sweep.** Move additive rows out of captured sequences (submenus: "Import…" near Duplicate is fine if documented, "Send to Suno Sync"/"Bounce"/clip transforms into an "Advanced" submenu), fix `Download .WAV`, lowercase accelerators, drop `danger` on Delete. | **M** (8 small edits) | `StudioProjectMenu.tsx`, `StudioTrackPanel.tsx`, `StudioEditorShell.tsx` (`:6411`, `:6442`, `:6719-6790`), `StudioHeader.tsx` (`:369-405`) | `tests/e2e/studio-clip-menu.spec.ts`, `studio-project-menu.spec.ts`, `studio-export.spec.ts` — assert captured row order/number and exact labels. |
| 9 | **B7 + B8 + B12 + B13 (chrome sweep).** "Mute all" label, icon buttons + `shift alt H` hint; `.se-learn-menu` width; `.se-dialog-x` in My Projects; `Studio Settings` casing; hide the take-band ✕ when empty; loop-handle copy; 24→19 px dialog title. | **S** (batch) | `StudioTrackPanel.tsx` (`:618-657`), `app/globals.css` (`:5313`, `:5363`, `:5418`), `StudioProjectMenu.tsx` (`:636-643`, `:624`, `:801`), `StudioTakeLanes.tsx` (`:37`), `lib/studio-help.ts` (`:38`) | `tests/e2e/studio-tracks.spec.ts` (bulk label), `studio-takes.spec.ts` (no ✕ when empty), `studio-learn.spec.ts` (one-line rows). |
| 10 | **B11 — library truth.** Render the real `StudioProjectThumbView` in library project rows; decide the key/tempo contract (keep "≈" but always render a placeholder tag so rows never lose both). | **M** | `components/studio/StudioLibrary.tsx` (`:481-483`, `:739-746`), `StudioSongKey.tsx`, `StudioSongTempo.tsx` | `tests/e2e/studio-library.spec.ts`; `tests/studio-song-tempo.test.tsx`, `studio-key.test.ts` for the low-confidence branch. |
| 11 | **B6 + B9 + B10 — deep parity polish** (cover art/like cluster in clip info, catalog ⋯ + asset-empty copy + `stereoUtility` preview, MIDI overview strip, stacked stretch modes, Clip Settings collapse). **Retake the captures first** (and after C1 lands) so the deltas are measurable. | **L** | `StudioClipInfo.tsx`, `StudioPluginDock.tsx` (`:292`, `:621-631`, `:1231-1251`), `StudioMidiEditor.tsx`, `StudioAudioEditor.tsx` (`:229-234`, `:306`), `docs/studio/compare/*` | `studio-clip-info.spec.ts`, `studio-plugins.spec.ts`, `studio-midi.spec.ts`, `studio-warp.spec.ts` + refreshed `check-clone-parity` captures. |

**Suggested batching:** 1+3 in one branch (both are the write path and share a test harness),
2 alone (audio), 4+5 in one, 6+7 in one, 8+9 as a single "menu & chrome sweep", 10, then 11
after the capture refresh.

**Retire instead of fix (recommended):** A-O1 (measurement artefact), B13's model-picker row
(documented decision in `3f96ba1d`), B9's "blank tenth tile" (no such plugin), B11's "See all"
(already implemented), B12's "translucent panel" (already opaque). If the team wants them
tracked at all they belong in a "capture refresh" ticket, not a defect list.

---

## 8. Sign-off

* Reports copied verbatim: `docs/studio/reports/2026-11-16-agent-a-functional.md`,
  `docs/studio/reports/2026-11-16-agent-b-parity.md` (evidence image paths left as written;
  the PNGs/logs stay in the agents' own `evidence-a/` and `compare/` folders).
* Ledger rows: **19**. Classes: **PRODUCT DEFECT 11 · COSMETIC 7 · EVIDENCE DEFECT 1 ·
  CANNOT VERIFY 0** (one unverifiable sub-claim inside B9).
* **D1: CONFIRMED** — `writeProjectData` → `persist(expected=null)` → server whole-document
  replace; fix at `StudioEditorShell.tsx:1893`.
* **D2: CONFIRMED** — the rename's `updated_at` is discarded at the `onRenamed(title)` boundary;
  `projectVersionRef` never advances; fix at `StudioProjectMenu.tsx:55/345` + `StudioEditorShell.tsx:5725`.
* **Top 5 to fix first:** (1) D1 data loss · (2) C1 missing waveforms · (3) D2 rename→409 ·
  (4) B4 share dialog truthfulness · (5) B3 footer/master-chain + dead control.
* No product code, CSS, spec or capture was modified. No server, browser or port was used.
  `G:\Developments\Projects\Camxora` untouched; nothing pushed or merged.

> **Correction to carry forward:** this consolidation promoted one B "capture staleness" item
> (C1, no timeline waveforms) to a product defect after A's independent screenshots showed the
> same blank clips in a live run. Until C1 is fixed, no parity judgement about clip *bodies*
> (waveforms, peaks, preview players) should be made from a capture.
