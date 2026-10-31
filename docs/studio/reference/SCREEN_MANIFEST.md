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
| S21 | Hidden-track state | OPEN |
| S22 | Ruler + zoom levels | PART — labels only |
| S23 | Section markers on the ruler | PART — flags visible |
| S24 | Loop region | OPEN |
| S25 | **Clip selected with trim handles** | OPEN |
| S26 | Clip context menu | DONE §47.1 |
| S27 | Clip Info panel | OPEN |
| S28 | Clip colour submenu | OPEN |
| S29 | Take lanes expanded | OPEN |
| S30 | Warp markers | OPEN |
| S31 | MIDI clip editor | OPEN |
| S32 | Automation lane — CC | OPEN |
| S33 | Automation lane — velocity | OPEN |

## 3. Magic Bar (S34–S38)

| # | Screen | Status |
|---|---|---|
| S34 | Magic Bar idle | DONE §54 |
| S35 | Magic Bar with clip attachment | DONE §54 |
| S36 | Magic Bar conversation | OPEN |
| S37 | Generation result on the timeline | OPEN |
| S38 | Model picker | DONE §6 |

## 4. Plugins (S39–S46)

| # | Screen | Status |
|---|---|---|
| S39 | Add-plugin catalog | DONE §48 |
| S40 | Plugin dock, single slot | DONE §50 |
| S41 | Plugin dock, multiple slots | DONE §50 |
| S42 | EQ expanded (bands, shapes) | PART — §53 |
| S43 | Compressor with sidechain | PART — §53 |
| S44 | Convolution with IR loaded | OPEN |
| S45 | Create-new-plugin designer | OPEN |
| S46 | Preset browser / bulk export | OPEN |

## 5. Mix and export (S47–S51)

| # | Screen | Status |
|---|---|---|
| S47 | Mixer strips | OPEN |
| S48 | Master with limiter | OPEN |
| S49 | Export menu | DONE §18.2 |
| S50 | Export dialog | OPEN |
| S51 | Export progress + result | OPEN |

## 6. Library and sharing (S52–S56)

| # | Screen | Status |
|---|---|---|
| S52 | Library workspaces | DONE §19 |
| S53 | Library — songs in a workspace | OPEN |
| S54 | Clip permissions | OPEN |
| S55 | Comments thread | OPEN |
| S56 | Shared project page | OPEN |

## 7. States (S57–S62)

| # | Screen | Status |
|---|---|---|
| S57 | Project loading | DONE §63 |
| S58 | Empty library | OPEN |
| S59 | Save conflict / error banner | OPEN |
| S60 | Policy / moderation refusal | OPEN |
| S61 | Insufficient credits | OPEN |
| S62 | Offline | OPEN |

## 8. Responsive (S63–S65)

| # | Width | Status |
|---|---|---|
| S63 | 1280 px | OPEN |
| S64 | 1024 px | OPEN |
| S65 | 768 px | DONE §46 (706 px) |

---

## Tally

| Status | Count |
|---|---|
| DONE | 31 |
| PART | 4 |
| OPEN | 30 |
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

S01–S14 captured and documented (§57, §58, §54, §56, §59, §10, §18.1, §25, §64,
§24, §38, §36). S19, S20 and S57 also have images (§61, §18.3, §63).

**Next capture: S15** — `What's This?` hover card, needs a signed-in session.
Then S16 (empty editor without the overlay), S17 (editor with clips), S18.
