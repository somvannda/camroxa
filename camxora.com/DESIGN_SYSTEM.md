# CAMXORA UI system — `.s-*` pages (Create, Library)

This is the source of truth for the Suno-parity surfaces. Anything inside a `.s-page`
must follow these rules. `npm run check:ui` enforces the numeric part.

## 1. Layers

1. **Page** — `.s-page` owns the tokens and the dark brand surface.
2. **Panel** — one frame per column (`.s-form-col`, `.s-detail-rail`).
3. **Card** — a framed section (`.s-form-card`, `.s-rail-card`).
4. **Control** — buttons, inputs, chips, pills.
5. **Row** — list items (`.s-row`, `.s-row-compact`).

Never skip a layer: a control never paints its own page background, a card never
contains another card of the same level.

## 2. Type scale (only these sizes)

| Token | Size | Use |
|---|---|---|
| `--s-fs-11` | 11px | counters, uppercase card labels, badges |
| `--s-fs-12` | 12px | meta lines, chips, download labels |
| `--s-fs-13` | 13px | labels, controls, toolbar pills, KV |
| `--s-fs-14` | 14px | body, textareas, row titles |
| `--s-fs-15` | 15px | tabs, primary CTA |
| `--s-fs-16` | 16px | rail title, panel titles |
| `--s-fs-18` | 18px | modal/hero title |
| `--s-fs-24/28/30` | 24/28/30px | page headings only |

Weights: 400 body, 500 labels/controls, 600 titles/CTA.

Line height: `1.2` for headings, `1.4` for labels, `1.5` for body.

**Icon rule:** an icon is at most **1px larger than its text**. 12px text → 12px icon,
13px → 14px, 14–16px → 16px. Page-level actions may use 18px.

**Do not** introduce 10.5, 11.5, 12.5, 13.5, 17px, etc.

## 3. Icon scale

| Token | Size | Use |
|---|---|---|
| `--s-caret` | 11px | dropdown carets, accordion chevrons, menu icons |
| `--s-ico-12` | 12px | inline counters, row play |
| `--s-ico-13` | 13px | chips, compact action grid, toolbar |
| `--s-ico-14` | 14px | standard buttons, menu rows |
| `--s-ico-16` | 16px | page-level actions, CTA icon |
| header | 15px | topbar search/bell/account chevron |

All icons render through the global `.icon` rule: `inline-flex`, centered, `line-height:1`,
`flex:none`. Icon-to-text gap is **6px** in buttons, pills, menus and selects (5px in chips).
Never hardcode an icon color except destructive.

On **≤620px** every `.s-btn-label` is hidden and the control becomes icon-only (attach
pills collapse to 34px circles, Filters/List keep their icons). Account name hides ≤680px.

## 4. Spacing (4px rhythm)

`4 · 6 · 8 · 10 · 12 · 16 · 20 · 24`

- Card padding: **12px** (rail and form cards alike).
- Gap between cards: **10px**.
- Gap inside a card: **10px**.
- Column gap: **16px**.
- Section label to content: **8–10px**.

## 5. Control heights

| Token | Height | Use |
|---|---|---|
| `--s-ctl-sm` | 28px | chips, tags, segmented items, pager |
| `--s-ctl-md` | 30–32px | menu items, icon buttons, downloads, dropdowns |
| `--s-ctl-lg` | 36px | standard buttons, rail actions |
| `--s-ctl-tab` | 40–42px | tabs, header controls |
| `--s-ctl-xl` | 44px | primary CTA + clear-all circle |

Primary CTA and its adjacent icon button must share a height. Header pill + header icon
button share one height (40). Tabs are **42px** (13px sub-tabs 40px).

## 5b. Component specs (fixed values)

| Component | Spec |
|---|---|
| Page title | 28/34, 600 |
| Tabs | 14px, 42px tall; sub-tabs 13px/40 |
| Segmented | 32px container, 28px item, 12px, items split 50/50 |
| Buttons | 36px, 13px, 13px icon; large 44px/14px/16px |
| Chips | 28px, 12px, 11px icon |
| Downloads | 26px, 11px |
| Inputs | 34px, 13px, radius 10 |
| Dropdowns | 32px, 13px, 12px chevron, `--s-field` background, 10px radius |
| Top line | segmented 3/4, credits + model 1/4 (30px controls) |
| Attach | three pills sharing the full row width |
| Menus | 28px items, 12px, 12px icon, 220px max in form/feed |
| Menu behavior | one open at a time; opening one closes the others |
| Card | 12px radius, 12px padding, 10px gap |
| Rail card label | 11px uppercase, 600 |
| Section label | 13px / 500 |
| Rail action | Play 36px, action grid 30px/12px |
| Row (library) | 110px, 86px cover |
| Row (create) | 64px, 32px play button, 13px title, 11px meta |
| Pager | 28px buttons/input |
| Empty state | 56px circle, 24px glyph, 18px title, 13px copy |

## 6. Surfaces

| Token | Value | Use |
|---|---|---|
| `--s-bg` | `#070a13` | page |
| `--s-bg2` | `#0f1322` | panels, cards, menus |
| `--s-bg3` | `#181f36` | controls, secondary buttons |
| `--s-bg4` | `#222a45` | hover |
| `--s-line` | `rgba(255,255,255,.075)` | borders/dividers |
| `--s-line2` | `rgba(255,255,255,.14)` | focused borders |
| `--s-field` | `#0a0d18` | inputs, textareas, search, selectors (darker than the card) |
| `--s-caret` | `11px` | every dropdown caret, accordion chevron and menu item icon |
| `--s-accent` | `#a855f7` | active state, checks |
| gradient | `linear-gradient(100deg,#7c3aed,#a855f7)` | primary CTA only |

Radii: 6 (chips), 8 (menu items), 10 (inputs/pills), 12 (cards), 16 (panels), 999 (pills).

## 7. Composite rules

- **Panel**: one surface + 1px border + 16px radius; no inner panel of the same tone.
- **Section card**: surface `rgba(255,255,255,.022)`, 1px border, 12px radius, 12px padding.
- **Section label**: 11–13px, weight 500; optional uppercase only for card headers.
- **Row (library)**: 110px, 86px cover, labeled actions.
- **Row (create workspace)**: 64px, play button, inline LRC/SRT/MP3/WAV, `≡` menu.
- **Empty state**: 56px icon circle, 17px title, 13px copy.
- **Footer**: gradient must fade to the card surface (`--s-bg2`), never the page surface.
- **Inputs**: text fields, textareas, search boxes and selectors use `--s-field` (darker than
  the card). Buttons, chips and segmented controls use `--s-bg3`.
- **Lyrics header**: label left; `Write | Prompt` in a 28px `.s-radio-pair` (24px items,
  12px text), Auto-generate as a 28px chip, chevron 24px — all vertically centered.

## 7b. Create page "+" add menu

The prompt composer `+` opens a 230px menu with the Suno item set:

| Item | Behaviour today |
|---|---|
| Lyrics ▸ | Write lyrics (switches to Advanced, focuses the field), Auto-generate, Instrumental |
| Styles ▸ | Saved styles, Shuffle styles, Enhance styles |
| Playlist | "Add playlist" modal — playlist reference upload is not enabled yet |
| Image | "Add image" modal — uploads not enabled yet |
| Video | "Add video" modal — uploads not enabled yet |
| Audio ▸ | Upload audio / Record audio → "Add audio" modal (Studio hand-off) |
| Voice ▸ | My voices / Browse voices → "Add voice reference" modal |

Submenus replace the list with a back header (no flyout overflow on narrow cards).
Unsupported attachments show an explicit "not enabled" explanation instead of a dead
button; each modal links to Studio.

## 8. Do / don't

- ✅ Use `var(--s-*)` tokens and the scales above.
- ✅ One primary CTA per view.
- ✅ Destructive actions are red (`--s-danger`) and never use the brand gradient.
- ✅ A panel may contain cards, but the card surface must differ from the panel surface.
- ✅ Each selector appears once in the `.s-*` block; superseded rules are deleted, not appended.
- ❌ Don't nest a card inside a card of the same level or same surface.
- ❌ Don't mix 13.5/17px text or 15/20px icons.
- ❌ Don't use raw hex outside the token block.
- ❌ Don't put pixel sizes in component `style={}` (only dynamic values such as indicator left/width).
- ❌ Don't hide a control's state (hover/active/disabled must be distinct).

## 9. Responsive

| Width | Create layout |
|---|---|
| ≥1440 | form 418 / workspace flex / rail 320 |
| 861–1439 | form 336 / workspace flex / rail 264 |
| ≤860 | single column: form, then workspace, then rail stacked; all full width |
| ≤620 | top line becomes 2:1 (segment / credits+model) so the v6 chevron stays visible |
| ≤400 | top line stacks: segment full width, credits + model on the next row |
| ≤560 | 8px page padding, compact tabs, download chips wrap under the row |

At ≤860 the rail becomes a static panel below the workspace (not a fixed drawer), so
nothing overlaps the form on phones.

## 10. Enforcement

```bash
npm run check:ui   # scans .s-* CSS for off-scale font sizes / control heights
```

The checker fails on any `font-size` outside the type scale or control height outside
`{26,28,30,32,34,36,40,44,46,48}` within the `.s-*` block. Fix the token, not the check.
