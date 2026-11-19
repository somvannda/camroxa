# Design System — Camxora Desktop (Electron)

> **Document ID:** CAMXORA-ED-06
> **Version:** 1.0.0
> **Status:** Draft for approval
> **Owner:** Design + Frontend
> **Last updated:** 2026-11-19

The brief leaves UX/UI to us. This is the direction. It is deliberately **not** a pixel copy
of the PySide6 app and **not** a generic dark dashboard. Feature parity is mandatory; the
visual language is a considered refresh that belongs to this product.

This spec follows the `unslop` method: quiet chrome, one bright moment per screen, deliberate
spacing, no decorative effects, and copy that says what the product does.

---

## 1. Direction

| Line | Answer |
|---|---|
| **Product** | A night-shift production studio for faceless music channels: generate songs, images and visuals, run the pipeline, publish |
| **Character** | Operator-grade, precise, quietly energetic |
| **World** | A broadcast control room after hours: graphite surfaces, VU-meter green/amber, violet only as a signal |
| **Moments** | The **Vizzy stage preview** and the **Dashboard weekly usage chart** carry the color; everything else stays quiet |
| **Signature** | A **2 px signal rail** on the active nav item, a **live status dot**, and **mono timecode** with tabular figures |

### 1.1 Professional bar

"Professional" is a quality bar, not a colour. Every screen must pass all of these:

1. **Predictable.** The same action sits in the same place on every page: primary action
   top-right, filters under the header, status in the footer, destructive actions in a
   dialog.
2. **Dense but readable.** A 1080p operator sees 10–14 table rows and the controls needed to
   act, without a scroll for the primary task.
3. **No toy affordances.** No mascots, no playful empty states, no confetti, no cartoon
   illustrations, no "oops" copy, no emoji.
4. **No decorative motion.** Motion explains state; it never entertains.
5. **Honest state.** Loading, stale, failed, deferred and partial are all visible and named.
   Nothing pretends to work.
6. **Keyboard-first.** Every primary action and every table is reachable without a mouse.
7. **Consistent vocabulary.** "Run", "batch", "stage", "profile", "template" mean one thing
   across Music, Progress, Image and Vizzy.
8. **No fake data.** Empty states and previews use real shapes or an honest placeholder; no
   lorem ipsum, no `[X]`, no invented numbers.
9. **Accessible.** Contrast, focus, labels, reduced motion and screen-reader names are part
   of done.
10. **Fast.** The interface never waits on a spinner for work it can do locally; heavy work
    is off the UI thread.

The test: would this screen be at home on an operator's desk for an eight-hour shift? If it
looks like a consumer social app, it is wrong.

### 1.2 What this rules out

- purple gradients on surfaces, gradient text, neon borders, glassmorphism;
- glows, colored shadows, radial washes, blurred blobs;
- emoji as icons or decoration;
- uppercase tracked section labels;
- "New ✨", "Beta 🚀", "PRO" badges unless the product truly needs a status;
- looping decorative animation, hover scale on cards, `transition-all`;
- nine slightly different greys and five accent colors.

---

## 2. Foundations

### 2.1 Color

One graphite ramp, tinted very slightly blue (the "after hours" world), three text roles,
one accent, and semantic colors used only for meaning.

```css
:root {
  /* surfaces */
  --bg:            #0b0d10;
  --surface-1:     #111418;
  --surface-2:     #171b20;
  --surface-3:     #1d2228;
  --surface-hover: #20262d;
  --surface-active:#252c34;

  /* hairlines */
  --border:        rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.14);

  /* text */
  --text-primary:  #f2f4f7;
  --text-secondary:#a7b0bc;
  --text-muted:    #6e7885;
  --text-disabled: #4b535d;

  /* accent (Camxora violet, used as a signal) */
  --accent:        #8b7cf6;
  --accent-hover:  #9d90f8;
  --accent-ink:    #0b0d10;
  --accent-soft:   rgba(139, 124, 246, 0.12);
  --accent-line:   rgba(139, 124, 246, 0.45);

  /* semantic */
  --success:       #4ade80;
  --success-soft:  rgba(74, 222, 128, 0.12);
  --warning:       #fbbf24;
  --warning-soft:  rgba(251, 191, 36, 0.12);
  --danger:        #f87171;
  --danger-soft:   rgba(248, 113, 113, 0.12);
  --info:          #38bdf8;
  --info-soft:     rgba(56, 189, 248, 0.12);

  /* chart series — only the dashboard chart may use several hues */
  --series-songs:  #8b7cf6;
  --series-images: #38bdf8;
  --series-videos: #4ade80;
}
```

Rules:

- Surfaces are neutral graphite. The world shows in the accent, charts, status dots and the
  Vizzy stage, never in the page background.
- Primary buttons are **off-white** (`--text-primary`) with dark text on dark themes; the
  accent is reserved for selection, focus, links and the one number that matters. This keeps
  violet meaningful.
- Accent text on `--bg` must reach 4.5:1. If it does not, use `--accent-hover` or a lighter
  tint.
- Semantic colors are toned down and never used as decoration.
- Borders are 1 px hairlines at 8–14 % white. Depth comes from surface steps, not shadows.
- Shadows are allowed only for floating overlays (menus, dialogs, command palette).

### 2.2 Typography

| Role | Family | Size / line | Weight |
|---|---|---|---|
| Page title | Inter | 24 / 30 | 600 |
| Section title | Inter | 16 / 22 | 600 |
| Card title | Inter | 14 / 20 | 600 |
| Body | Inter | 13 / 19 | 400 |
| Body strong | Inter | 13 / 19 | 500 |
| Meta / label | Inter | 12 / 16 | 400–500 |
| Caption | Inter | 11 / 15 | 400 |
| Timecode / numbers | JetBrains Mono | 12 / 16 | 400–500 |
| Vizzy UI | Inter (host UI) | as shipped | as shipped |

Rules:

- Sentence case everywhere. No uppercase tracked labels.
- No 700–900 weights. Hierarchy from size and color.
- Numbers use `font-variant-numeric: tabular-nums`.
- No italic for emphasis.
- No negative letter spacing below 16 px.
- Fonts are bundled locally (no Google Fonts at runtime).

### 2.3 Spacing and sizing

- 4 px grid. Allowed steps: `4 8 12 16 20 24 32 40 48 64`.
- Control heights: `28` compact, `32` default, `36` comfortable; primary CTA `40`.
- Table rows: `36` default, `32` dense, `44` with two-line cells.
- Sidebar width `232`; collapsed `64`.
- Top bar `48`; footer `28`; page padding `24`; card padding `16–20`.
- Content max width `1600`; pages are fluid below that.
- Minimum window `1280×800`; default `1440×900`; the old app's `1920×1080` minimum is dropped.

### 2.4 Radii

| Element | Radius |
|---|---|
| Buttons, inputs, selects | 8 |
| Cards, panels | 12 |
| Dialogs, command palette | 14 |
| Pills / status dots | 999 (only true pills) |
| Inner elements | outer − padding, min 4 |

Nested radii must add up. A 12 px card with 8 px padding holds a 4 px inner control.

### 2.5 Motion

- Durations: `120 ms` feedback, `160 ms` enter/leave, `200 ms` page-level.
- Easing: `cubic-bezier(0.2, 0, 0, 1)`.
- Animate only `color`, `background-color`, `border-color`, `opacity`, `transform`.
- No `transition-all`; no width/height/top/left animation.
- Respect `prefers-reduced-motion`: no entrance animation, no number tween.
- At most one entrance per route: content fades and rises 4 px.

### 2.6 Iconography

- Lucide, 16 px in controls, 18 px in nav, 1.5 stroke.
- Icons take the text role color, never their own color.
- One fixed icon column; labels align across rows.
- No emoji in UI text.

---

## 3. Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Title bar 48px: brand · project/context · status · window controls         │
├──────────────┬─────────────────────────────────────────────────────────────┤
│ Sidebar 232  │ Page header (title, description, primary actions)           │
│              ├─────────────────────────────────────────────────────────────┤
│ Account      │ Content (scrolls)                                           │
│ Workspace    │                                                             │
│  Dashboard   │                                                             │
│  Profile     │                                                             │
│  Progress    │                                                             │
│  Music       │                                                             │
│  Image       │                                                             │
│  Vizzy       │                                                             │
│  Marketplace │                                                             │
│ Utility      │                                                             │
│  Settings    │                                                             │
│              │                                                             │
│ Footer 28px: status · env · version · credits/profiles                     │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

- The sidebar is the densest region: 32 px rows, 2 px gap, 18 px icon, 10 px icon-to-label.
- Active row: `--surface-active` + a 2 px accent rail on the left + primary text.
- Section labels are 11 px sentence case in `--text-muted`, 24 px above and 8 px below.
- The title bar is frameless and draggable; buttons use `-webkit-app-region: no-drag`.
- The footer shows one status message, a live dot, environment, version, and the account
  summary. It is not a second navigation bar.
- Page header: title 24/30, description 13/19 muted, actions right-aligned. Hide the header
  only for Vizzy, which owns its own chrome.

---

## 4. Components

| Component | Rules |
|---|---|
| **Button** | Variants: `primary` (off-white), `secondary` (surface-2 + border), `ghost`, `danger`. 8 px radius. Loading spinner replaces the icon, label stays. Disabled at 40 % opacity. |
| **IconButton** | 28/32 square, tooltip, `aria-label` required. |
| **Input / Textarea** | 8 px radius, surface-1, 1 px border. Focus: accent border + 2 px accent-soft ring. Error: danger border + message below. |
| **Select** | Radix Select, same height as input, searchable when > 12 options. |
| **Checkbox / Switch** | 16 px box / 32×18 switch; accent when on; label click toggles. |
| **Slider** | 4 px track, 14 px thumb, value in mono; keyboard arrows step. |
| **Tabs** | Underline or segmented; not both. Active uses primary text + 2 px accent underline. |
| **Table** | Sticky header, 36 px rows, hairline row separators, hover `--surface-hover`, selected `--accent-soft` + accent rail. Numerics right-aligned mono. No zebra stripes. |
| **Card** | surface-1, 12 px radius, 1 px border, 16–20 padding. No shadow. |
| **Stat** | Label 11–12 muted, figure 28–32 semibold, optional delta with comparison text. No sparkline, no decorative icon. |
| **Badge / Pill** | 20 px height, 12 px text, semantic tint only. Used for status, not decoration. |
| **Dialog** | 14 px radius, surface-1, 1 px border, neutral shadow, max width 520 (confirm) / 720 (form). Focus trap, Escape closes, initial focus on the safe action. |
| **Toast** | Bottom-right, 320 wide, 4 s auto-dismiss, one action max, no stacking more than 3. |
| **Command palette** | 560 wide, grouped results, keyboard-first, `⌘/Ctrl+K`; also exposes every route and Vizzy command. |
| **Empty state** | One short sentence + one action. No illustration unless it carries meaning. |
| **Error banner** | Rose tint, one sentence, optional Retry. Replaces content, never overlays it. |
| **Skeleton** | Surface-2 blocks, no shimmer; static or 1.2 s opacity pulse at most. |
| **Progress** | 4 px bar; indeterminate only when the backend gives no progress. |
| **Chart** | Muted grid, mono labels, one accent series leading; legend as dots + labels. |

### 4.1 Table states

| State | Treatment |
|---|---|
| Header | 11 px muted, sentence case, sticky, hairline bottom |
| Row hover | `--surface-hover` |
| Selected | `--accent-soft` + 2 px left rail |
| Keyboard focus | 2 px `--accent` outline inside the row |
| Disabled row | 50 % opacity, no hover |
| Loading | 3 skeleton rows, same height |
| Empty | One row spanning columns, muted message + action |

---

## 5. Page patterns

### 5.1 Overview pages (Dashboard, Profile)

- KPI row: 3–5 stats, varied widths; the most important figure is largest.
- One wide chart or primary panel; secondary panels stack on the right.
- Tables below, full width.
- No refresh button unless the data is user-triggered; polling is silent with a "Updated
  just now" mono caption.

### 5.2 Operational pages (Progress, Music, Image)

- A filter/toolbar row directly under the header, on the page background (not inside a card).
- Stat row, then the main table/card.
- Detail panels open inline (right rail or below the row), not as a modal, unless the task is
  destructive.
- Errors sit above the table and keep the last good data visible with a "stale" label.

### 5.3 Editor page (Vizzy)

- Vizzy owns its chrome inside the view: menus, left rail, stage, inspector, timeline.
- The shell hides its page header and reduces the sidebar to a 64 px rail while Vizzy is
  active, to maximise the stage.
- A thin shell strip above the view shows "Vizzy · project name · saved/unsaved · Renders · Close".
- On close, if dirty, confirm Save / Discard / Cancel.
- **Renders** opens a right-side panel (or bottom sheet on narrow windows) with the pipeline
  queue: job, stage, progress, output, retry. It never covers the stage by default.
- **Save as video template** sits next to Export. It captures the exact preview, shows the
  auto-detected bindings (audio, background, logo, title/artist/album, palette) with simple
  confirm/override controls, and saves the user template. No multi-step wizard.
- The template library presents all 91 templates. A “featured” row may help discovery; it never
  hides the rest.

### 5.4 Pipeline surfaces (Music, Progress, Renders)

- The pipeline is shown as a **stage chain**, not a spinner: render → encode → merge → reel →
  upload, with the current stage and a per-stage retry.
- A job row shows song, branch, template, stage, progress and output. One line per job.
- A failed stage names the exact stage and reason; a failed upload leaves the local file and
  offers Retry upload.
- Costs are shown before Generate: render + merge + upload, with the balance check.
- No dead toggles. If a template is missing/incompatible, the toggle is disabled with the
  reason and a link to Settings → Profiles.

### 5.5 Settings

- Left tab list (8 tabs), right content, sticky footer with **Save all changes** and dirty
  state.
- Each tab is a set of panels; no tab is a single giant form.
- Save is global unless the tab declares an immediate action (e.g. connect YouTube).

### 5.6 Login

- Centered card, 400 px max, on a dark graphite field with one quiet visual: a thin waveform
  line that responds to the app's startup state, not a looping animation.
- One primary action, one secondary (Google), one tertiary (forgot password / create account).
- Recent accounts appear below the form as compact rows, not cards.
- No marketing copy inside the app.

---

## 6. Content and voice

- Plain, specific, calm. "Unable to load dashboard statistics" not "Oops! Something went
  wrong".
- No exclamation marks. No greeting headlines. No hype words.
- Short labels: `Search`, `Retry`, `Open folder`, `Save`.
- A change says what it compares to: `+12% vs last week`.
- Numbers use one format and tabular figures.
- Errors say what failed, what still works, and the next action.
- Empty states say what will appear and how to make it appear.

### 6.1 Error copy pattern

```
<What failed>. <What still works>. <Next action>.
Example: "Unable to load the image queue. The last loaded rows are still shown.
Check your connection and retry."
```

### 6.2 Destructive copy pattern

```
Title: Clear queue?
Body: This removes every image job for 12 Nov – 19 Nov. Generated files on disk are not deleted.
Action: Clear queue
```

---

## 7. Accessibility

- WCAG 2.2 AA: 4.5:1 body text, 3:1 large text and UI boundaries.
- Every interactive element is reachable by Tab; focus ring is always visible.
- Dialogs trap focus and restore it on close.
- Tables expose row/column semantics; sortable headers announce state.
- Charts have a text summary and a data table alternative behind "View data".
- Status is never color-only: icon or text accompanies it.
- `prefers-reduced-motion` respected.
- Minimum hit target 28×28 in dense UI, 32×32 elsewhere.
- Screen-reader labels for icon-only buttons.

---

## 8. Unslop checklist (apply per page)

- [ ] One bright moment; the rest of the chrome is quiet.
- [ ] Every spacing value on the 4 px grid; equal things equal.
- [ ] Icons, labels and numbers align in columns.
- [ ] One neutral ramp, three text roles, one accent with sufficient contrast.
- [ ] No hue gradients, gradient text, glows, colored shadows or blobs.
- [ ] No emoji in the interface.
- [ ] One icon set, one size, one stroke.
- [ ] Type weights 400–600; no uppercase tracked labels; no italic.
- [ ] No exclamation marks, no trailing periods on short strings, no greeting headline.
- [ ] Numbers use one format with tabular figures.
- [ ] Nested radii add up.
- [ ] Table states are distinct: header, hover, selected, focus.
- [ ] One primary action per region.
- [ ] No looping or bouncy motion; one easing curve.
- [ ] The page could not be mistaken for a generic AI dashboard.
- [ ] The page passes the professional bar (§1.1): predictable, dense, honest, keyboard-first,
      no toy affordances, no fake data.

---

## 9. Visual moments

### 9.1 Dashboard chart

The weekly usage chart is the one place with several hues. It is drawn as three clean lines
on a muted grid, with a single highlighted point for "today". The legend is text + dots, not
a second chart. Hover shows a vertical guide and a compact tooltip with all three series.

### 9.2 Vizzy stage

The stage is the product's richest surface. It is framed by a 1 px border and a neutral
checkerboard only when transparency matters; otherwise it sits on `--bg`. The surrounding
Vizzy chrome is Rea's own, restyled to the tokens above via a small override stylesheet
(scoped to the view, never global).

### 9.3 Marketplace cards

Preview-first: 16:9 image, name, author/kind, one line of description, install state. No
gradient overlays, no badges stacked on the image. Installed cards use a quiet checkmark and
a "Installed" label.

---

## 10. Implementation notes

- Tokens live in `src/styles/tokens.css` and are mirrored into Tailwind's theme.
- Components live in `src/components`; no page imports a raw Radix primitive directly.
- The Vizzy override stylesheet lives in `vizzy/theme/shell-overrides.css` and is loaded after
  Rea's CSS inside the Vizzy view only.
- Screenshot baselines are captured at 1440×900 and 1920×1080; see
  [`04-QA-ACCEPTANCE.md`](04-QA-ACCEPTANCE.md).
- Design review is a gate for every page: a page is not done until it passes §8 and the
  visual baseline is approved.
