# Creator UI — unslop pass

**Skill:** [unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky ([@heydamir](https://x.com/heydamir)), CC BY 4.0.
**Installed:** global `~/.opencode/skills/unslop` and project `.opencode/skills/unslop`.
**Rule:** [`AGENTS.md`](../../AGENTS.md) § "UI craft (mandatory — unslop)".

---

## Direction for the creator surfaces

- **Product.** A release workspace for Khmer AI-native musicians, from a finished generation to a live track and a public creator page.
- **Character.** Calm, nocturnal, exact.
- **World.** Phnom Penh at night: graphite surfaces, river light, one restrained violet accent. No neon washes, no glow, no gradient chrome.
- **Moments.** The release route (Draft → Review → Live) on each row, and the selected generation's title/cover in the new-release panel.
- **Signature.** A three-node release route with a thin connecting line. It appears only on release rows.

## Audit of the existing creator screens

| Sign | Where |
|---|---|
| Uppercase tracked labels | `CREATOR STUDIO`, `CREATORS`, `CREATOR STUDIO / VERIFICATION` eyebrows |
| Purple gradient primary buttons on every screen | Creator Studio, Verification, public page, directory |
| Multiple primary actions on one screen | Creator Studio header (public page + verification + releases + browse) |
| Four equal stat cards in a row | Creator Studio, Verification, Releases |
| Purple gradient banner fallback | Public creator page when no banner |
| Decorative icon tiles in empty states | Directory / verification empty panels |

The data itself is honest: real creator records, real statuses, no fake counters.

## Passes applied to `/creator/releases`

1. **Spacing.** 24px page rhythm, 16px row padding, 4px-based gaps.
2. **Color.** Existing graphite surfaces; one violet accent for the route and the primary action. No new gradients, glows, or colored shadows.
3. **Icons.** Existing Font Awesome set only, same size; no emoji.
4. **Copy.** Sentence case, no exclamation marks, no hype, no greeting headline. Labels are short (`Draft`, `In review`, `Live`).
5. **Type.** Existing family and weights; numbers use tabular figures.
6. **Layout.** Two-column workspace that collapses to one column; quiet header with one primary action.
7. **Details.** Hairline row dividers, no pill statuses, no mini-charts.
8. **Visuals.** The signature is the release route; no decorative image, because the screen is a workspace.
9. **Motion.** No looping animation or `transition-all` added.

## Verified

- Draft created from a finished generation.
- Submitted for review; status moved to **In review** with a review deadline.
- Withdraw returns it to draft.
- No console errors.

## What changed in the third pass

- **Root cause fixed:** the global `.panel` class has no padding, so raw forms touched card edges. Creator pages now compose from `CreatorPage`, `CreatorHeader`, `CreatorPanel`, `CreatorField`, `CreatorButton`, and `CreatorMetrics`; padding, gaps, and control heights are owned by the primitives.
- **Primary buttons** are now off-white with dark text instead of purple gradients; secondary/ghost actions are quiet.
- **Forms** use a 20px field rhythm, 44px controls, 10px radii, and a visible focus ring.
- **Every panel** gets 24px padding.
- **Studio** was rebuilt on the primitives; Verification and the public page had their panels padded.
- The rules are documented in [UI_SYSTEM.md](./UI_SYSTEM.md) and enforced by `AGENTS.md`.

## Follow-ups

### Applied in the second pass

- Removed uppercase tracked eyebrows from Creator Studio, Verification, Directory, and the public creator page; they now use quiet sentence-case meta text.
- Replaced the four equal stat cards with a single `CreatorMetrics` strip (hairline rules, tabular figures, quieter rhythm) on Studio, Verification, Releases, and the public page.
- Reduced Verification to one primary action per screen: the application submit stays primary; identity evidence is now secondary.
- Replaced the public-page purple gradient banner fallback with a neutral graphite surface and a hairline.
- Converted the Studio checklist from eight equal cards to a compact readiness list.

### Global shell pass

- Primary buttons, `Create Music`, `Buy packs`, and sidebar create buttons are now flat brand violet with no gradient, glow, or colored shadow.
- Sidebar section labels are sentence case with normal tracking.
- Active navigation uses a quiet surface step and a 2px accent rule, not a glass gradient.
- `.eyebrow` is sentence case with normal tracking across the app.
- The topbar is a solid translucent surface instead of a gradient.
- Avatar/banner uploads are live with previews.

### Avatar and banner crop

- Choosing an avatar or banner opens a crop dialog instead of uploading immediately.
- Avatar crops 1:1 and saves 512 × 512; banner crops 3:1 and saves 1500 × 500.
- Drag to reposition, 1–3× zoom slider, thirds grid, Escape or Cancel to abandon.
- Output is a JPEG re-encoded on canvas, so oversized phone photos never reach storage raw.
- Verified: dialog opens, zoom is exact (2.00× doubles the rendered image), canvas output is 512 × 512, upload succeeds and the preview updates.

### Still open

- Treaty-rate table for W-8BEN withholding (non-US creators currently withheld at 30%).
- Tax statements are generated, not yet rendered as a downloadable PDF.
- Reserve release has an admin action but no scheduled job.


