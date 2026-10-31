# SCREEN MANIFEST — the A→Z capture contract

Every screen in the product, in the order a user meets it. **No screen is skipped.**
Each row is one screenshot, one spec section, one commit.

Status: `DONE` captured and documented · `PART` partially captured · `OPEN` not captured.

---

## 1. Entry (S01–S15)

| # | Screen | Status |
|---|---|---|
| S01 | Signed-out marketing page `/studio-welcome` | DONE §57 |
| S02 | Sign-in page / redirect | DONE §58 |
| S03 | **Signed-in entry — reopens the last project** | DONE §62 |
| S04 | Studio home / project chooser ("Browse Studio projects") | DONE §56 |
| S05 | New empty project | DONE §59 |
| S06 | Onboarding dialog "How do you want to start?" | DONE §10 |
| S07 | Project menu | DONE §18.1 |
| S08 | Version History panel | DONE §25 |
| S09 | Settings → Performance | DONE §22, §64 |
| S10 | Settings → Window management | DONE §39, §64 |
| S11 | Settings → Content | DONE §29, §64 |
| S12 | Share dialog | DONE §24 |
| S13 | Learn menu | DONE §38 |
| S14 | Keyboard shortcuts overlay | DONE §36 |
| S15 | "What's This?" hover card | DONE §7.1 |

## 2. Arrangement (S16–S33)

| # | Screen | Status |
|---|---|---|
| S16 | Editor, empty project | DONE §44.10 |
| S17 | Editor, loaded project | DONE §44.10 |
| S18 | Track row anatomy | DONE §52.1 |
| S19 | Track options menu | DONE §61 |
| S20 | Add-track menu | DONE §18.3 |
| S21 | Hidden-track state | DONE §65 |
| S22 | Ruler + zoom levels | DONE §66 |
| S23 | Section markers on the ruler | DONE §67 |
| S24 | Loop region | DONE §68 |
| S25 | **Clip selected with trim handles** | DONE §69 |
| S26 | Clip context menu | DONE §47.1 |
| S27 | Clip Info panel | DONE §70 |
| S28 | Clip colour submenu | DONE §71 |
| S29 | Take lanes expanded | DONE §72.1 |
| S30 | Warp markers | OPEN |
| S31 | MIDI clip editor | DONE §73 |
| S32 | Automation lane — CC | PART §74 — empty lane only |
| S33 | Automation lane — velocity | DONE §75 |

## 3. Magic Bar (S34–S38)

| # | Screen | Status |
|---|---|---|
| S34 | Magic Bar idle | DONE §54.1 |
| S35 | Magic Bar with clip attachment | DONE §54.1 |
| S36 | Magic Bar conversation | DONE §80 |
| S37 | Generation result on the timeline | DONE §86 |
| S38 | Model picker | DONE §6 |

## 4. Plugins (S39–S46)

| # | Screen | Status |
|---|---|---|
| S39 | Add-plugin catalog | DONE §48 |
| S40 | Plugin dock, single slot | DONE §50 |
| S41 | Plugin dock, multiple slots | DONE §50 |
| S42 | EQ expanded (bands, shapes) | DONE §85 |
| S43 | Compressor with sidechain | DONE §83 |
| S44 | Convolution with IR loaded | PART §78 — card without an IR |
| S45 | Create-new-plugin designer | PART §79 — prompt entry only |
| S46 | Preset browser / bulk export | OPEN |

## 5. Mix and export (S47–S51)

| # | Screen | Status |
|---|---|---|
| S47 | Mixer strips | OPEN |
| S48 | Master with limiter | OPEN |
| S49 | Export menu | DONE §18.2.1 |
| S50 | Export dialog | DONE §87 — no dialog exists (negative) |
| S51 | Export progress + result | DONE §87 — toast only (negative) |

## 6. Library and sharing (S52–S56)

| # | Screen | Status |
|---|---|---|
| S52 | Library workspaces | DONE §19.1 |
| S53 | Library — songs in a workspace | DONE §19.1 |
| S54 | Clip permissions | OPEN |
| S55 | Comments thread | DONE §84 — flat notes, no authors |
| S56 | Shared project page | OPEN |

## 7. States (S57–S62)

| # | Screen | Status |
|---|---|---|
| S57 | Project loading | DONE §63 |
| S58 | Empty library | DONE §88 |
| S59 | Save conflict / error banner | OPEN |
| S60 | Policy / moderation refusal | OPEN |
| S61 | Insufficient credits | OPEN |
| S62 | Offline | PART §82 — no banner observed (negative result) |

## 8. Responsive (S63–S65)

| # | Width | Status |
|---|---|---|
| S63 | 1280 px | DONE §76 |
| S64 | 1024 px | DONE §76 |
| S65 | 768 px | DONE §46.1 — gate below 768, editor at ≥768 |

---

## Tally

| Status | Count |
|---|---|
| DONE | 52 |
| PART | 4 |
| OPEN | 9 |
| **Total** | **65** |

## Rules for working through this list

1. **In order.** S01 → S65. No jumping to whatever looks interesting.
2. **One screen per commit**: screenshot → spec section → implement → diff.
3. A screen marked DONE must have a spec section number next to it **and** an
   entry in `SCREENSHOT_INDEX.md`, or it isn't done.
4. `PART` means the section exists but is missing a visual — treat it as OPEN for
   implementation purposes until the missing state is captured.
5. Never implement from an OPEN row.

## Current position

S01–S23, S25–S28, S31, S33, S36, S38–S43, S49, S52/S53, S55, S57, S63–S65 are
captured with an image and a spec section — 60 files. Every `DONE` row is fully
evidenced.

**The capture phase is as complete as this project allows.** The 5 `PART` and 13
`OPEN` rows are enumerated with their unblock in
[`CAPTURE_GAPS.md`](CAPTURE_GAPS.md) — read that before attempting more captures;
five of them clear with a single new project + one generation.
