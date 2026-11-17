# Screen-capture plan for W3 (states + the “cannot judge” 14)

**Date:** 2026-11-17
**Workstream:** W3-prep of `docs/studio/RESIDUAL_VERIFICATION_PLAN.md`
**Branch:** `qa/capture-prep` (base `origin/main` `4abff799`)
**Scope:** plan + runnable capture script only. No server started, no port bound, no
browser launched, no capture taken, no reference frame, PAIRING entry or product
component changed. `G:\Developments\Projects\Camxora` was not touched, nothing pushed.

Artifacts:

| Artifact | Purpose |
|---|---|
| `camxora.com/scripts/capture-screens.mjs` | the work list as data + Playwright driver; writes `docs/studio/compare/*.png` |
| this report | the table W3 executes, the PAIRING edits, and the S43 reference-frame decision |

`node camxora.com/scripts/capture-screens.mjs --list` prints the authoritative row list
(it needs no `node_modules` and no browser).

---

## 1. What W3 has to produce

Two sources, one work list.

- **13 STATE frames** — `2026-11-17-pixel-diff.md` §5, the rows whose split is exactly
  `STATE`: `S15 S25 S28 S29 S34 S35 S40 S46 S53 S56 S63 EXTRA-library-uploads
  EXTRA-take-lanes-empty`. Their paired captures show a *different app state*; the
  percentage cannot be read as layout evidence until they are re-shot.
- **14 screens without a paired capture** — the same report §6, the screens Agent B marked
  CANNOT JUDGE: `S01 S02 S29 S43 S57 S60 S61 S62 EXTRA-generation-refused
  EXTRA-generation-refused-legacy EXTRA-library-uploads EXTRA-library-song-detail
  EXTRA-project-load-error EXTRA-restoring-last-project`.

`S29` and `EXTRA-library-uploads` appear in both lists — one capture serves both roles, so
the union is **25 screens** and **24 files** (`EXTRA-generation-refused` and
`…-legacy` share one file by declaration).

Not in scope here, on purpose: the 10 `STATE+LAYOUT` rows (`S05 S07 S14 S16 S17 S21 S30
S42 S48 S64`) and the 5 `REGION` rows (`S22 S23 S51 S54 S58`) also need re-shoots, but they
are layout-and-state mixtures the pixel report already classifies; the plan's §4 W3 line
does include them, so they are the **next** batch, not this one. `S41`/`S65` were scored
MATCH by the semantic audit and stay as they are.

### 1.1 Viewport rule (and where it deviates from “the frame's own size”)

A capture is taken at the reference frame's own width×height whenever the frame is a
full viewport — that is the whole point (`S09`'s 1115 px gutter only exists at 1115 px).

Three frames are **crops**, not viewports: `S28` (920×1040 menu crop), `S46` (840×450
menu crop) and `S43` (1040×660 card crop, see §5). Capturing the editor at 920×1040 would
re-lay-out the editor and destroy the thing being compared. Those rows are shot at the
corpus editor viewport (1689×1277) and the harness marks them `REGION`, which is what it
already does for the current captures. This is the only deviation and it is recorded in
the table's `viewport` column with `frameKind`.

---

## 2. Table A — the 13 STATE screens (re-shoot, replace the paired capture)

Actions are ordered exactly as `capture-screens.mjs` runs them. “Seeded” means a
throwaway project created through `POST /api/v3/web-music/studio/projects` from inside the
page (the same fixture the e2e suite uses), never a provider call.

| # | Screen | Title | Reference frame (size) | What today's frame gets wrong | Target state | Route | Ordered actions | Viewport | Expected visible | Pairing |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **S15** | What's This? card | `S15-whats-this-card.jpeg` (1689×1277) | No hover card at all; the frame shows the first-run explainer bottom-right (an allowed additive). | Tempo control hovered, card anchored under `120 BPM`. | `/studio/editor?project=<seeded>` | 1. seed 1 track + clip · 2. wait `.se-clip` · 3. `hover()` `input[aria-label="Tempo in BPM"]` | 1689×1277 | `role=tooltip` (`.se-help-card`), `.se-help-card` | replace `ours-editor-1689.png` → **`ours-whats-this.png`**; drop `sharedWith: S17` |
| 2 | **S25** | Clip selected / trim grips | `S25-clip-selected.jpeg` (1689×1277) | Empty plugin dock where the reference shows the master chain; stale clip bodies, no waveform. | Clip selected *and* `Main` selected so the dock holds the master chain. | same | 1. seed 1 track + clip with `audioUrl:/demo-loop.wav` · 2. click `.se-clip` · 3. click `button "Main"` | 1689×1277 | `.se-clip[aria-pressed="true"]`, `role=region[name="Master chain"]` | replace `ours-clip-selected.png` → **`ours-clip-selected-master.png`** |
| 3 | **S28** | Clip colour submenu | `S28-clip-color-submenu.jpeg` (920×1040, **crop**) | Submenu closed: only the parent row is hovered. | Clip menu open with `Clip Color` expanded (Auto row + swatch grid). | same | 1. seed · 2. right-click clip at `+30,+40` · 3. wait `role=menu[name="Clip options"]` · 4. click menuitem `Clip Color` | 1689×1277 (crop frame) | the menu, `role=group[name="Clip colour"]`, swatches `Clip colour #…` | replace `ours-clip-color.png` → **`ours-clip-color-open.png`** |
| 4 | **S29** | Take lanes | `S29-take-lanes.jpeg` (1689×1277) | Our capture is the **empty** band (“Create a clip to see alternate takes here”), not the numbered take rows. | Two takes stacked under the clip, take 2 active. | same | 1. mock `generate` + `generations/take-gen` · 2. seed clip · 3. select clip · 4. click `Take lanes` · 5. fill prompt, `Generate this part` · 6. commit the assistant take | 1689×1277 | `role=region[name="Take lanes"]`, `button "Use take 2"`, `button "Use take 1"` | replace `ours-take-lanes.png` → **`ours-take-lanes-populated.png`** |
| 5 | **S34** | Prompt bar idle | `S34-magicbar-idle.jpeg` (1689×1277) | Track menu open over the bar and the MIDI editor docked, so the idle bar is only partly visible. | Idle editor: prompt bar + BETA badge, no menu, no attachment chip. | same | 1. seed · 2. wait `.se-clip` · 3. assert `.se-prompt`; assert **no** `role=menu`, **no** MIDI editor | 1689×1277 | `.se-prompt`, `textarea[aria-label="Describe a part to generate"]`, `button "Generate this part"` | replace `ours-magicbar.png` → **`ours-magicbar-idle.png`** |
| 6 | **S35** | Prompt bar attachment | `S35-magicbar-attachment.jpeg` (1689×1277) | Reused editor frame with no attachment chip; the attachment state is unevidenced. | A clip attached: chip with the clip title and its ×. | same | 1. seed clip titled `Drum Kit Main` · 2. click `Attach a track or clip` · 3. click menuitem `Drum Kit Main` | 1689×1277 | `.se-prompt-context`, `button[name="Clear track context"]` | replace `ours-prompt-attachment.png` → **`ours-magicbar-attached.png`** |
| 7 | **S40** | Plugin dock · one slot | `S40-plugin-dock-single.jpeg` (1689×1277) | Our dock shows the **selected track's** chain with track-scoped footer chips; the reference dock is the **master** chain. | `Main` selected, one EQ in the master chain, add-effect rail with ghost tiles. | same | 1. seed · 2. click `Main` · 3. wait `role=region[name="Master chain"]` · 4. click `button "Add EQ"` | 1689×1277 | `role=region[name="Master chain"]`, `role=article[name="EQ slot"]`, `button "Add Compressor"` | replace `ours-plugin-dock-eq-convolution.png` → **`ours-plugin-dock-master-eq.png`** (see §6 re-anchor) |
| 8 | **S46** | Preset menu / stepper | `S46-preset-menu.jpeg` (840×450, **crop**) | Preset popover closed; only the stepper is visible, so order and placement are unevidenced. | Compressor card with the preset menu open. | same | 1. seed · 2. click `Track 1` · 3. dock `Add effect` · 4. catalog `Compressor` · 5. click the preset button (`Default`) | 1689×1277 (crop frame) | `role=article[name="Compressor slot 1"]`, `role=menu[name="Compressor presets"]`, menuitem `Clear all settings` | replace `ours-plugin-dock-eq-convolution.png` → **`ours-plugin-preset-menu.png`**; drop `sharedWith: S40` |
| 9 | **S53** | Library songs | `S53-library-songs.jpeg` (1689×1277) | Predates the tag strip: “V6 PRO OK · 0:04” instead of model · key · BPM. | Library ▸ All Songs: date groups + the tag strip. | same | 1. mock `generations?*` with 3 tagged songs · 2. seed · 3. click `Toggle library` · 4. click `All Songs` | 1689×1277 | `role=complementary[name="Library"]`, `.se-lib-song`, `.se-lib-tags` | replace `ours-library-songs.png` → **`ours-library-songs-tags.png`** |
| 10 | **S56** | Shared link logged out | `S56-shared-link-logged-out.jpeg` (1920×1211) | Ours is stuck on “Loading project…” **and the reference frame is the marketing hero — it contains no share surface at all.** | No-cookie visitor on `/studio/shared/<token>`: read-only heading, timeline, “Sign in to fork”. | `/studio/shared/<token>` | 1. sign in · 2. seed project · 3. `POST …/shares {expires_days:7,permission:"view"}` · 4. new **anonymous** context at 1920×1211 · 5. open the share URL | 1920×1211 | `Read-only Studio share`, `aria-label="Read-only project timeline"`, link `Sign in to fork` | replace `ours-share-page-logged-out.png` → **`ours-shared-link-readonly.png`** |
| 11 | **S63** | 1280 px | `S63-1280px.jpeg` (1280×900) | Both fit at 1280, but the frames compare different bottom surfaces: the reference has a docked MIDI editor + master chips. | 1280×900, MIDI clip open in the docked editor, master chain selected. | same | 1. seed · 2. `Add new track` → `MIDI` · 3. wait MIDI editor · 4. click `Main` | 1280×900 | `role=region[name="MIDI editor"]`, `role=region[name="Master chain"]` | replace `ours-editor-1280-audit.png` → **`ours-editor-1280-midi.png`** |
| 12 | **EXTRA-library-uploads** | Library uploads | `EXTRA-library-uploads.jpeg` (1261×1245) | Right surface, stuck on “Loading uploads…” — no row, tag or date group evidenced. | Uploads view resolved: day headings + dated rows. | same | 1. mock `studio/uploads?*` with 3 dated uploads · 2. seed · 3. `Toggle library` · 4. click `Uploads` | 1261×1245 | `.se-lib-day`, `.se-lib-upload`; **not** “Loading uploads…” | replace `ours-library-uploads.png` → **`ours-library-uploads-resolved.png`** |
| 13 | **EXTRA-take-lanes-empty** | Take lanes empty | `EXTRA-take-lanes-empty.jpeg` (1261×1245) | The first-run help card covers the band's right end, so the band cannot be judged. | Empty take band with its captured copy, help card dismissed. | same | 1. seed clip (`studio:help:seen=1` is pre-set) · 2. select clip · 3. click `Take lanes` | 1261×1245 | `.se-takes-empty`, `role=region[name="Take lanes"]`; **no** `.se-help-first` | replace `ours-take-lanes-empty.png` → **`ours-take-lanes-empty-clean.png`** |

---

## 3. Table B — the 14 screens without a paired capture (add)

Twelve had no capture at all; two (`S29`, `EXTRA-library-uploads`) are the wrong-state
captures from Table A and are not repeated.

| # | Screen | Title | Reference frame (size) | State to capture | Route | Ordered actions | Viewport | Expected visible | Pairing |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **S01** | Marketing signed out | `S01-marketing-signed-out.jpeg` (1116×1245) | Signed-out `/studio` marketing page in product chrome. | `/studio` | 1. anonymous context · 2. open `/studio` | 1116×1245 | `h1` “Camxora Studio.” | **add** `ours-marketing-signed-out.png` |
| 2 | **S02** | Sign-in modal | `S02-sign-in-modal.jpeg` (1250×1245) | Our `/login` page (route, not a modal — the W0 decision on that divergence is still open). | `/login` | 1. anonymous context · 2. open `/login` | 1250×1245 | `h1` “Welcome back.”, labelled `Email` field | **add** `ours-sign-in.png` |
| 3 | **S43** | Compressor sidechain | **no `S43-*.jpeg`** (frame exists misfiled — §5) | Compressor card + Sidechain routing list on a 4-track project. | same editor route | 1. seed 4 tracks (Brass Section, Long Vocal, Bass Line, Bass Answer) · 2. `Track 1` · 3. `Add effect` → `Compressor` · 4. click `Sidechain` | 1689×1277 | `role=article[name="Compressor slot 1"]`, `role=menu[name="Sidechain routing"]`, `Pre-fx` / `Post-fader` rows | **add** `ours-compressor-sidechain-routing.png`; pairing **blocked** until §5 is decided |
| 4 | **S57** | Project loading blank | `S57-project-loading-blank.jpeg` (1094×1245) | Editor holding the load state (project GET delayed 15 s). | `/studio/editor?project=<seeded>` | 1. seed (open:false) · 2. delay GET project 15 s · 3. navigate | 1094×1245 | `.se-loading` | **add** `ours-project-loading-1094.png` |
| 5 | **S60** | Moderation refusal | `S60-moderation.jpeg` (1440×900) | Create ▸ Advanced, submit refused by the policy. | `/create` | 1. mock `quota` + `generations` (no provider) · 2. mock `generate` → 400 `MODERATION_BLOCKED` · 3. click tab `Advanced` · 4. fill style + lyrics + title · 5. click `.s-create-btn` | 1440×900 | `.s-error` (form refusal) | **add** `ours-moderation-refusal.png` — note: our refusal is **inline**, the reference is an orange toast |
| 6 | **S61** | Insufficient credits | `S61-insufficient-credits.jpeg` (1440×900) | Create with a zero balance: CTA blocked, warn note explains why. | `/create` | 1. mock `quota` `credits_remaining:0` · 2. click tab `Advanced` · 3. fill style | 1440×900 | `.s-note.warn` | **add** `ours-insufficient-credits.png` — no out-of-credits **modal** exists (`CreateStudio.creditsOpen` is unused): evidence for a W7 absence decision |
| 7 | **S62** | Offline cold load | `S62-offline-cold-load.jpeg` (1971×1277) | Browser offline, cold navigation: network error page, no app shell. | `/studio` | 1. `context.setOffline(true)` · 2. navigate `/studio` · 3. assert no `header.se-head` | 1971×1277 | *nothing from the app* (chrome error page) | **add** `ours-offline-cold-load.png` |
| 8 | **EXTRA-generation-refused** | Generation refused (legacy copy) | `EXTRA-generation-refused-legacy.jpeg` (1250×1245) | Prompt-bar generation refused; the assistant notice explains it. | editor | 1. mock `generate` → 400 `MODERATION_BLOCKED` · 2. seed · 3. fill prompt · 4. `Generate this part` | 1250×1245 | `.se-assistant-notice`, refusal copy | **add** `ours-generation-refused.png` (anchor) |
| 9 | **EXTRA-generation-refused-legacy** | Generation refused (legacy copy) | same frame | Same state — one capture evidences both rows. | editor | (covered by row 8) | 1250×1245 | — | same file, `sharedWith: "EXTRA-generation-refused"` |
| 10 | **EXTRA-library-song-detail** | Library song detail | `EXTRA-library-song-detail.jpeg` (1261×1245) | Library ▸ All Songs ▸ song opened in the read-only rail. | editor | 1. mock `generations?*` with one song · 2. seed · 3. `Toggle library` · 4. `All Songs` · 5. double-click the row | 1261×1245 | `role=complementary[name="Song details"]`, tab `Info` | **add** `ours-library-song-detail.png`; drop the bogus `spec: studio-components.test.tsx` |
| 11 | **EXTRA-project-load-error** | Project load error | `EXTRA-project-load-error.jpeg` (1689×1277) | Editor after a failed project GET. | editor | 1. seed (open:false) · 2. mock GET project → 500 · 3. navigate | 1689×1277 | `.se-error[role="alert"]` | **add** `ours-project-load-error.png` — note: the reference offers *Try again / Dismiss*; ours has neither |
| 12 | **EXTRA-restoring-last-project** | Restoring last project | `EXTRA-restoring-last-project.jpeg` (1689×1277) | The state between reload and load. | editor | 1. seed (open:false) · 2. delay GET project · 3. navigate | 1689×1277 | `.se-loading` | **add** `ours-restoring-last-project.png` — note: our copy is “Loading project…”, not “Restoring your last project…” |
| 13 | **S29** | Take lanes | see Table A #4 | see Table A #4 | | | 1689×1277 | | same file as Table A #4 |
| 14 | **EXTRA-library-uploads** | Library uploads | see Table A #12 | see Table A #12 | | | 1261×1245 | | same file as Table A #12 |

---

## 4. Selector provenance

Every selector above is taken from the shipped component, not invented. The ones worth
recording, with their source:

| Selector | Source |
|---|---|
| `.se-clip`, `.se-clip[aria-pressed]` | `StudioTimeline.tsx` (clip button), `studio-clip-menu.spec.ts:38` |
| `role=menu[name="Clip options"]`, menuitem `Clip Color`, `role=group[name="Clip colour"]` | `StudioEditorShell.tsx:6425-6622` |
| `role=region[name="Take lanes"]`, `button "Use take N"`, `.se-takes-empty` | `StudioTakeLanes.tsx:36-77` |
| `.se-prompt`, `.se-prompt-context`, `button "Attach a track or clip"`, `role=menu[name="Attach to the prompt"]` | `StudioEditorShell.tsx:6067-6168` |
| `header.se-head`, `input[aria-label="Tempo in BPM"]`, `data-help="tempo"` | `StudioHeader.tsx:314-326` |
| `role=tooltip` / `.se-help-card` (hover card), `.se-help-first` (first-run) | `StudioLearn.tsx:189-215` |
| `button "Main"` (master select), `.se-master-strip` | `StudioTrackPanel.tsx:659-668` |
| `role=region[name="Master chain"]`, `button "Add EQ"`, `role=article[name="EQ slot"]`, `button "Add Compressor"` | `StudioMasterDock.tsx:82-210` |
| `role=region[name="Plugins for Track 1"]`, `button "Add effect"`, `.sp-add-inline`, `role=dialog[name="Add a track plugin"]` | `StudioPluginDock.tsx:761`, `studio-plugins.spec.ts:9-12,76-82` |
| `role=article[name="Compressor slot 1"]`, `role=menu[name="Compressor presets"]`, `menuitem "Clear all settings"` | `StudioPluginDock.tsx:779-940` |
| `button "Sidechain"`, `role=menu[name="Sidechain routing"]`, rows `— Pre-fx` / `— Post-fader` | `StudioPluginDock.tsx:1100-1186` |
| `button "Toggle library"`, `role=complementary[name="Library"]`, tiles `All Songs`/`Uploads`, `.se-lib-song`, `.se-lib-tags`, `.se-lib-day`, `.se-lib-upload`, `.se-lib-empty` | `StudioFooter.tsx:145`, `StudioLibrary.tsx:313-380,566-880` |
| `role=complementary[name="Song details"]`, tabs `Info`/`Stems` | `StudioSongDetail.tsx:185,319-338` |
| `.se-loading` (“Loading project…”) | `StudioEditorShell.tsx:7485` |
| `.se-error[role="alert"]` (load error) | `StudioEditorShell.tsx:7423` |
| `.se-assistant-notice` | `StudioEditorShell.tsx:6262-6267`, `studio-pixel.spec.ts:926` |
| `.s-error`, `.s-note.warn`, `.s-create-btn`, `#create-style`, `#create-lyrics`, tab `Advanced` | `CreateStudio.tsx:3519-3537,3966,4047,4366-4373,4388` |
| `h1` “Camxora Studio.” | `StudioMarketing.tsx:38` |
| `h1` “Welcome back.”, `#email` | `app/(auth)/login/page.tsx:29`, `LoginForm.tsx:64` |
| `Read-only Studio share`, `aria-label="Read-only project timeline"`, `link "Sign in to fork"`, `h1={title}` | `app/studio/shared/[token]/page.tsx:167-193`, `studio-share-page.spec.ts:34-37` |

States that are **not reachable without a provider call** and are mocked in the script:
generation for take-lanes (`S29`), the moderation/credit refusals (`S60`, `S61`,
`EXTRA-generation-refused`), the library song list (`S53`, `EXTRA-library-song-detail` —
`fetchGenerations` is the provider-backed `/api/v3/web-music/generations`), and the uploads
list (`EXTRA-library-uploads`). The slow/failing project GET is a route-level mock, not a
provider mock.

---

## 5. S43 — the reference frame

### 5.1 Finding: the frame exists; the file is misfiled

The plan and the pixel report both say “S43 has no reference frame”. That is true of the
**filename** only. Three independent records say the pixels are already in the corpus:

- `docs/studio/SUNO_STUDIO_IMPLEMENTATION_SPEC.md` §83: *“Capture
  `screens/S46-compressor-routing-list.jpeg` — the `Compressor` card with its selector
  open.”* It then lists the exact options: every track twice as `— Pre-fx` / `— Post-fader`.
- `docs/studio/reference/SCREENSHOT_INDEX.md:74`: `S43 | screens/S46-compressor-routing-list.jpeg
  | Compressor sidechain — every track twice as Pre-fx / Post-fader`.
- `2026-11-16-agent-b-parity.md:90` already diffed against it by hand and found our list
  *matches exactly* (“None”, then per-track pairs).

I opened the file: it is a Compressor card with the routing dropdown open over the
arrangement, showing `Brass Section — Post-fader`, `Long Vocal — Pre-fx` / `— Post-fader`,
`Bass Line — Pre-fx` / `— Post-fader`, `Bass Answer — Pre-fx` / `— Post-fader`, with the
What's This? card bottom-right. That is S43 and nothing else. `S46` has its own frame
(`S46-preset-menu.jpeg`), so the file was never S46's primary evidence.

**Consequence:** W3 does not need a live Suno session to judge S43. `pixel-diff.mjs`
matches frames by filename prefix (`framesFor(id)`), so the fix is a **rename**, not a
harness change:

```
git mv docs/studio/reference/screens/S46-compressor-routing-list.jpeg \
       docs/studio/reference/screens/S43-compressor-routing-list.jpeg
```

plus the SCREENSHOT_INDEX row, and then S43's existing capture pairs to
`S43-compressor-routing-list.jpeg` (slug overlap: `compressor`, `routing`). `NO-FRAME`
drops from 21 to 20 and S43 becomes diffable.

This is a reference-corpus filename change, so it needs **W0 sign-off**; it is listed as
decision D-S43 in §6.2. No frame is invented and no pixel is edited either way.

### 5.2 Fallback: capture the frame from the live session (read-only)

Only if W0 prefers a fresh frame over the rename. Nothing in this path is executed now.

**Preconditions** (none of them starts a web server):

1. `musicapi/.env` present and readable (DB URL + `COOKIE_ENCRYPTION_KEY`).
2. `musicapi` built: `npm run build` in `musicapi` (the script requires
   `musicapi/dist/db.js` and `dist/cookieCrypto.js`).
3. `camxora.com/node_modules` installed with a Chromium build (`npm ci` +
   `npx playwright install chromium`).
4. An active `suno_accounts` row (default label `iamduke1987@gmail.com`, override with
   `--label`).

**Steps**

1. `node scripts/dev/suno-session.cjs --probe` → prints `signed-in=true|false`, exit 0/1.
   If `false`, stop: record S43 as a corpus gap (plan §4) and fall back to the rename.
2. Open headed: `node scripts/dev/suno-session.cjs --url https://suno.com/studio`.
3. Read-only route: from the account's own project list open a **multi-track** project
   (the frame's tracks are `Brass Section`, `Long Vocal`, `Bass Line`, `Bass Answer`, so
   the reference project had ≥4). Do not add tracks, do not save, do not rename.
4. Select the track that carries a Compressor (the reference card is on one), or — if the
   project already has one — open the per-track inspector and expand the Compressor.
5. Open the sidechain selector under the card header (the control whose options are
   `X — Pre-fx` / `X — Post-fader`).
6. Screenshot **the card + open list**, i.e. a card crop like the existing
   `S46-compressor-routing-list` (1040×660), not the full viewport; write it as
   `docs/studio/reference/screens/S43-compressor-routing-list.jpeg` and record the
   capture date, the project title and the visible `suno.com` build in the report.
7. Verify: the list must contain `None`-equivalent plus at least two tracks in both taps.
   Otherwise the frame does not evidence the screen — discard it.

**Scripted shape** (what the executing agent writes, ~40 lines, in the same style as
`suno-session.cjs`): reuse its `loadEnv` → decrypt a `suno_accounts.__client` cookie →
`chromium.launch({ headless: false })` → `addCookies` → open the project URL → wait for the
studio shell → click the compressor's sidechain control → `locator.screenshot()` on the
card → `browser.close()`. Guard every step with an `if (!visible) throw`, and abort if
`page.url()` leaves `suno.com`.

**Feasibility estimate with the current decrypted session: medium-high (~60–70 % one-shot).**

| Factor | Assessment |
|---|---|
| Auth | `--probe` is the only gate and it is cheap; the cookie is the same one the firmware-side mirror uses. |
| Project availability | The corpus frames came from this account (`S17` “Drum & Bass Demo”, 12 tracks; S43's frame names four more), so a multi-track project should be in the list. |
| UI reachability | Compressor + sidechain selector exist in the reference build by definition (the frame shows them). Suno ships frequently, so the control may have moved or been renamed since the frame was taken — this is the main risk. |
| Session state | A cookie can decrypt and still be stale; `--probe`'s heuristic (zero “sign in” buttons) can pass on a marketing page with no such button. Assert a studio shell selector, not just the URL. |
| Risk of mutation | Low if the steps above are followed: selecting a track and opening a dropdown are reads, but *opening* a project can create a server-side session and the UI may auto-save a touched project. |
| Credits | Zero — no generation. |

Because the rename is free and this path is neither free of UI drift nor guaranteed, the
recommendation is: **rename first, re-run `check:pixels` on the existing capture (free,
deterministic), and only use the live session if the renamed frame's diff is unconvincing.**

---

## 6. PAIRING edits (deterministic)

Apply **in the same commit as the captures**, then `npm run check:clone` and
`npm run check:pixels`. `check:clone` fails on a capture path that does not exist, so do
not land the JSON first.

### 6.1 Entry edits (`docs/studio/reference/PAIRING.json`)

| Screen | Field | From | To |
|---|---|---|---|
| S15 | `capture` | `ours-editor-1689.png` | `ours-whats-this.png` |
| S15 | `sharedWith` | `"S17"` | *(delete)* |
| S25 | `capture` | `ours-clip-selected.png` | `ours-clip-selected-master.png` |
| S28 | `capture` | `ours-clip-color.png` | `ours-clip-color-open.png` |
| S29 | `capture` | `ours-take-lanes.png` | `ours-take-lanes-populated.png` |
| S34 | `capture` | `ours-magicbar.png` | `ours-magicbar-idle.png` |
| S35 | `capture` | `ours-prompt-attachment.png` | `ours-magicbar-attached.png` |
| S40 | `capture` | `ours-plugin-dock-eq-convolution.png` | `ours-plugin-dock-master-eq.png` |
| S42 | `sharedWith` | `"S40"` | `"S41"` |
| S44 | `sharedWith` | `"S40"` | `"S41"` |
| S46 | `capture` | `ours-plugin-dock-eq-convolution.png` | `ours-plugin-preset-menu.png` |
| S46 | `sharedWith` | `"S40"` | *(delete)* |
| S53 | `capture` | `ours-library-songs.png` | `ours-library-songs-tags.png` |
| S56 | `capture` | `ours-share-page-logged-out.png` | `ours-shared-link-readonly.png` |
| S63 | `capture` | `ours-editor-1280-audit.png` | `ours-editor-1280-midi.png` |
| EXTRA-library-uploads | `capture` | `ours-library-uploads.png` | `ours-library-uploads-resolved.png` |
| EXTRA-take-lanes-empty | `capture` | `ours-take-lanes-empty.png` | `ours-take-lanes-empty-clean.png` |
| S01 | `capture` | *(none)* | `ours-marketing-signed-out.png` |
| S02 | `capture` | *(none)* | `ours-sign-in.png` |
| S43 | `capture` | `ours-compressor-sidechain.png` | `ours-compressor-sidechain-routing.png` |
| S57 | `capture` | *(none)* | `ours-project-loading-1094.png` |
| S60 | `capture` | *(none)* | `ours-moderation-refusal.png` |
| S61 | `capture` | *(none)* | `ours-insufficient-credits.png` |
| S62 | `capture` | *(none)* | `ours-offline-cold-load.png` |
| EXTRA-generation-refused | `capture` | *(none)* | `ours-generation-refused.png` |
| EXTRA-generation-refused-legacy | `capture` | *(none)* | `ours-generation-refused.png` |
| EXTRA-generation-refused-legacy | `sharedWith` | *(none)* | `"EXTRA-generation-refused"` |
| EXTRA-library-song-detail | `capture` | *(none)* | `ours-library-song-detail.png` |
| EXTRA-library-song-detail | `spec` | `"studio-components.test.tsx"` | *(delete — a component test is not a frame)* |
| EXTRA-project-load-error | `capture` | *(none)* | `ours-project-load-error.png` |
| EXTRA-restoring-last-project | `capture` | *(none)* | `ours-restoring-last-project.png` |

**The trap to get right:** `S40` was the anchor of the five-way
`ours-plugin-dock-eq-convolution.png` group (`S40 S41 S42 S44 S46`). After `S40` and `S46`
get their own files, `S41 S42 S44` still share the old file, and `check:clone` requires
exactly one anchor per digest. `S41` has no `sharedWith` today, so it becomes the anchor
and **`S42` and `S44` must be re-pointed from `"S40"` to `"S41"`** or `check:clone` fails
with *“one capture is paired with S41, S42, S44; mark every screen but one sharedWith”*.

Untouched groups: `S03/S06` (`ours-entry-overlay.png`), `S05/S16`
(`ours-empty-project-clean.png`), `S12/S54` (`ours-share-dialog.png`).

### 6.2 File and doc edits

| # | Edit | Gate |
|---|---|---|
| 1 | `git mv docs/studio/reference/screens/S46-compressor-routing-list.jpeg docs/studio/reference/screens/S43-compressor-routing-list.jpeg` | **D-S43** — W0 sign-off (reference corpus filename) |
| 2 | `SCREENSHOT_INDEX.md:74` → `screens/S43-compressor-routing-list.jpeg` | with #1 |
| 3 | `S43` PAIRING `capture` (see §6.1) | after #1, or `S43` stays `NO-FRAME` |
| 4 | No `FRAME_OVERRIDES` change in `pixel-diff.mjs` | — |

If D-S43 is rejected, skip #1–#3: capture `ours-compressor-sidechain-routing.png` anyway
(it is free), leave `S43` paired to it, and record one remaining `NO-FRAME` + the live-session
fallback in §5.2.

---

## 7. Running the captures

```bash
cd camxora.com
npm ci && npx playwright install chromium     # once per worktree (no node_modules here)
node scripts/capture-screens.mjs --list       # the work list, no browser
node scripts/capture-screens.mjs              # all 25 rows → 24 files
node scripts/capture-screens.mjs --only S28,S46
node scripts/capture-screens.mjs --only S43 --headed
```

**Preconditions** (the executing agent owns these; this script never starts a server):
the Next dev server on `:3103` and the sandbox platform API behind `/api/v3`; the sandbox
login (`STUDIO_SMOKE_EMAIL` / `STUDIO_SMOKE_PASSWORD`, defaults = the e2e fixture's
`somvannda@gmail.com` / `StudioLocal!2026`); `public/demo-loop.wav` (present) for waveform
decoding.

**Behaviour**

- one fresh browser context per screen, viewport from the table, `deviceScaleFactor 1`,
  `reducedMotion: "reduce"`, and `studio:settings` / `studio:help:seen` seeded so no run
  inherits the previous run's What's This?/first-run state;
- each screen builds **its own** project through the API, so `--only` never depends on
  another row;
- every structural expectation is **hard**: on failure the run prints
  `SELECTOR MISSING: <screen> — <selector> — <scenario>`, the page URL, writes
  `docs/studio/reports/capture-failures/<screen>.png`, and exits 1 with all failures
  listed. Two measured tags (library key, BPM) are **soft** and only reported, because they
  are computed from the audio and may legitimately stay absent.

**Known-soft spots, expect deltas not failures**

| Screen | What will differ from the reference | Why that is correct |
|---|---|---|
| S60 | our refusal is `.s-error` inline, the reference is a toast | different surface, same state; W7/absence call |
| S61 | no out-of-credits modal exists | evidence for the W7 absence decision |
| EXTRA-project-load-error | no *Try again / Dismiss* buttons on `.se-error` | layout delta, not a capture defect |
| EXTRA-restoring-last-project | copy is “Loading project…” | copy delta |
| S56 | the **reference** is the marketing hero | frame defect; needs a W0 frame decision, not a re-shoot |
| S15 / S43 | reference has the first-run “What's This?” card in the corner | allowed additive, per the pixel report |

---

## 8. Sign-off

- Work list: **25 screens** = 13 STATE + 14 unjudged, with `S29` and
  `EXTRA-library-uploads` shared between the two lists.
- Capture files to write: **24** (`EXTRA-generation-refused` and `…-legacy` share one).
- PAIRING edits: **31 field edits** over **27 entries** (§6.1), one group re-anchor
  (`S42`, `S44` → `S41`), one dead spec pointer removed (`EXTRA-library-song-detail`).
- S43: **1** screen, **0** new reference frames required if D-S43 (rename) is approved;
  the live-session path is documented with a ~60–70 % one-shot estimate.
- Nothing was run: no server, no browser, no capture, no port, no push. The only writes are
  `camxora.com/scripts/capture-screens.mjs` and this report.
