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
