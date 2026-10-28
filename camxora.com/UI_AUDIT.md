# UI audit — whole web app (2026-10-28)

Method: `ui-ux-pro-max` checklists (contrast 4.5:1, 24px target minimum, heading
hierarchy, focus) plus automated DOM/browser checks on every route: title, h1 count,
horizontal overflow, image alt text, unnamed buttons, unlabeled fields, sub-24px
interactive targets, console errors.

## Summary

| Check | Result |
|---|---|
| Routes audited | 25 |
| Console errors | 0 |
| Horizontal overflow | 0 on every route |
| Images missing `alt` | 0 |
| Unnamed buttons | 0 |
| Unlabeled inputs (aria/label/placeholder) | 0 |
| Missing page `h1` | 2 → fixed (`/create`, `/studio/editor`) |
| Real sub-24px controls | 0 (remaining hits are inline text links / range input) |

## Findings

### P1 — fixed
1. **`/create` had no `h1`** — tabs were the top of the document. Added
   `<h1 class="sr-only">Create music</h1>` (new global `.sr-only` utility).
2. **`/studio/editor` had no top-level `h1`** on the rendered page (the only `h1` was in
   a collapsed branch). Added `<h1 class="sr-only">Studio editor</h1>`.

### P2 — consistency
3. **Two design dialects.** `/create` and `/library` use the new `.s-*` system
   (`DESIGN_SYSTEM.md`); every other page still uses the older app CSS. This is the main
   reason "the app" feels inconsistent. Recommended: migrate page-by-page, keeping the
   shell untouched.
4. **Topbar account**: name now hides ≤680px, avatar + 15px chevron remain. All topbar
   icons are 15px.
5. **Small-screen labels**: ≤620px `.s-btn-label` hides; attach pills become 34px icon
   circles, Filters/List keep icons; text-only buttons (Newest, Public, Uploads) keep
   their labels so they never go blank.

### P3 — notes, no action needed
6. Footer/nav inline text links measure <24px high; WCAG 2.2 target size has an exception
   for inline text links.
7. `/login` redirects away when already authenticated (expected).
8. `/playlists/liked-songs` 404 in the probe was an invalid test slug; real slugs are
   `chill-vibes`, `edm-party`, `khmer-hits`, `my-playlist`.

## Contrast (token check)

| Pair | Ratio | Verdict |
|---|---|---|
| `#f4f5fb` on `#0f1322` | ≈15:1 | pass AAA |
| `#c9cde0` on `#0f1322` | ≈11:1 | pass AAA |
| `#8b90a6` on `#0f1322` | ≈5.8:1 | pass AA |
| `#6f748a` on `#0f1322` | ≈4.0:1 | only used for disabled/inactive states |

## Per-route results

| Route | h1 | Overflow | Console | Notes |
|---|---|---|---|---|
| `/` | Create. Discover. Enjoy AI Music. | 0 | clean | inline links <24 |
| `/discover` | Discover | 0 | clean | inline links <24 |
| `/charts` | What Camxora is playing. | 0 | clean | inline links <24 |
| `/community` | Community | 0 | clean | inline links <24 |
| `/pricing` | Buy credits. | 0 | clean | inline links <24 |
| `/studio` | Camxora Studio. | 0 | clean | inline links <24 |
| `/search` | Find your next track. | 0 | clean | inline links <24 |
| `/download` | Install Camxora… | 0 | clean | inline links <24 |
| `/create` | **fixed** (sr-only) | 0 | clean | new system, no small controls |
| `/library` | Library | 0 | clean | new system, no small controls |
| `/account` | Kong Somvannda | 0 | clean | legacy |
| `/artist-dashboard` | Kong Somvannda | 0 | clean | legacy |
| `/notifications` | Notifications. | 0 | clean | legacy |
| `/redeem` | Redeem a code. | 0 | clean | legacy |
| `/publish` | Publish a track. | 0 | clean | legacy |
| `/invite` | Invite friends. | 0 | clean | legacy |
| `/signup` | Create your account. | 0 | clean | auth shell |
| `/about` | Music, made by more people. | 0 | clean | legacy |
| `/features` | Everything you need… | 0 | clean | legacy |
| `/support` | Help Center. | 0 | clean | legacy |
| `/contact` | Talk to a human. | 0 | clean | legacy |
| `/blog` | Notes from Camxora. | 0 | clean | legacy |
| `/changelog` | What changed. | 0 | clean | legacy |
| `/legal` | Clear terms. No surprises. | 0 | clean | legacy |
| `/developers` | Music API. | 0 | clean | legacy |
| `/services` | Built for creators… | 0 | clean | legacy |
| `/google-api` | Google API data usage. | 0 | clean | legacy |
| `/studio/editor` | **fixed** (sr-only) | 0 | clean | full-screen editor |

## Next actions

1. Migrate remaining pages to the `.s-*` tokens in batches (pricing → account → discover),
   running `npm run check:ui` after each.
2. Add a skip-to-content link in the shell.
3. Optional: visible `h1` on Create (e.g. “Create music” above the tabs) if the design
   wants one; currently sr-only to preserve the Suno-style layout.

---

## Pass 2 � control audit + component migration (2026-10-28)

Scope: every `<select>`, checkbox, play control, icon+label pair, and auth surface in
`camxora.com`.

### Root causes found

1. **Icons sat 2-3px low in every icon+label pair** (sidebar, Create Music, Sign in,
   row play buttons). `components/Icon.tsx` emits `icon fa-classic fa-solid fa-replaced`,
   but `.fa-replaced{display:inline-flex}` was declared *before* Font Awesome's
   `.fa-solid{display:inline-block;line-height:1}`, so the icon computed as a block box
   with a font-sized line box (16px) inside an 11-14px box. The glyph overflowed
   downward. Fixed with a higher-specificity
   `.icon.fa-replaced{display:inline-flex;align-items:center;justify-content:center;line-height:1}`
   and removed the legacy `top:0.5px` optical hack.
2. **Play buttons were dark glass, not green.** `.card .play` only turned green on hover.
   All play controls now follow the documented "play is the one green action" rule.
3. **"Remember me" used a raw `<input type="checkbox">`** despite
   `components/ui/checkbox.tsx` existing. Its resting fill was 4% white � effectively
   invisible on `#070a13`.
4. **Google sign-in disappeared after client-side navigation.** `next/script`'s `onLoad`
   does not re-fire when the GIS script is already in the document, so moving
   `/login` ? `/signup` left an empty container.
5. **22 native `<select>` elements** bypassed the Radix Select that already shipped in
   `components/ui/select.tsx`.

### Fixes shipped

| Area | Change |
|---|---|
| Icons | Global flex centring; `.checkbox-check` sized; optical hack removed |
| Play | `.card .play`, `.chart-play`, `.chart-row-play`, `.s-row-compact .s-row-play`, `.s-cover-play span`, `.studio-transport-center .play` are green at rest |
| Checkbox | `ui/checkbox.tsx` resting `bg-white/14` + `border-white/45`, hover `0.2` / `0.65`; indeterminate state; 11px check glyph |
| Login | Remember me uses `ui/checkbox` with a real `htmlFor` label |
| Signup | Required Terms & Conditions + Privacy Policy consent, blocking submit with an inline error, `aria-invalid` / `aria-describedby` |
| Google | Custom 280x40 pill (official multicolour G) with the real GIS button invisibly overlaid at the same box; `onReady` + `window.google` probe; failure copy instead of a blank gap |
| Selects | New `ui/select-field.tsx` (empty-value sentinel, `size="sm"`, `ariaLabel`); all 22 native selects migrated in `CreateStudio` and `StudioEditorView` |
| Studio checkboxes | Auto-apply, Show archived and mashup rows migrated to `ui/checkbox` |
| Account menu | `Topbar` uses `ui/dropdown-menu` (portal, focus trap, Escape, outside click) instead of the hand-rolled state machine |
| CSS bug | Removed a literal `\n` escape that corrupted `.s-remix-sort.on` / `.s-remix-filter` |

### Verification

- `npm run typecheck` � clean
- `npm run check:ui` � compliant
- DOM checks on `/`, `/login`, `/signup`: 0 native `<select>`, 0 raw `type="checkbox"`,
  0 horizontal overflow; icon boxes compute `display:flex` with a centred line box;
  Google iframe/visual boxes identical (280x40, same top/left) and the click target
  opens the Google flow; checkbox resting fill `rgba(255,255,255,0.14)`.

### Still open

1. 21 hand-rolled `role="menu"` popups remain in `CreateStudio` (16) and `LibraryView`
   (4) plus the Studio export menu (1). They work and are keyboard reachable, but should
   move to `ui/dropdown-menu` in a dedicated pass (one menu per commit).
2. Re-run the route sweep with an authenticated session (Create/Studio/Account) to
   confirm the migrated selects at real data volumes.
3. No commits made � working tree only.

---

## Pass 3 � dropdown/menu migration (2026-10-28)

The app shipped `@radix-ui/react-dropdown-menu` but every `.s-menu` popup was hand-rolled
(`useState` + document `mousedown` listener + manual `role="menu"`). Migrated the
dropdown menus to Radix while keeping the `.s-menu*` visual language through
`components/ui/s-menu.tsx`.

### Migrated (15 popups)

| Surface | Menus |
|---|---|
| `/library` | row menu, Audio, Filters, Sort |
| `/create` audio results | row menu (both render sites) incl. Download submenu |
| `/create` song rows | row menu incl. Download submenu |
| `/create` toolbar | Credits, Model, Workspace picker, Save to�, Share workspace, Filters, Sort |
| Topbar | account menu |

Behaviour gained: portal rendering, collision-aware positioning, focus trap, roving
`ArrowUp`/`ArrowDown`, type-ahead, `Escape` + outside click, `menuitemcheckbox` /
`menuitemradio` semantics. Closed menus are forced `pointer-events:none` so a stalled
exit animation can never swallow page clicks.

### Deliberately not migrated

1. **`/create` "+" add menu** � uses `position:fixed` with computed `addMenuPos` /
   `addMenuBelow` and a submenu that *replaces* the list with a back header. That is
   documented behaviour in `DESIGN_SYSTEM.md` �7b (no flyout overflow on narrow cards),
   so it stays custom.
2. **Saved-styles popup** in `/create` � currently unreachable: the trigger opens the
   saved-styles modal instead of toggling `stylePresetsOpen`. Dead code; remove or wire up
   in a follow-up.
3. **`/studio/editor` clip context menu** � anchored to cursor coordinates
   (`clipMenu.x/y`), not a trigger element. Correct primitive is
   `@radix-ui/react-context-menu`, which is not a dependency yet.

### Verification

- `npm run typecheck` / `npm run check:ui` clean
- Live DOM checks (authenticated, `:3104`): every migrated menu opens with the expected
  `menuitem` / `menuitemcheckbox` / `menuitemradio` roles; Download submenus render;
  legacy `.s-menu[role=menu]` count is 0 on `/library` and on the migrated `/create` rows.
