# Site-wide accessibility: landmarks, decorative images and heading order

**Date:** 2026-11-11
**Branch:** `fix/site-a11y-landmarks`
**Surfaces:** camxora.com (all `(site)` pages, Library in particular)
**Status:** implemented, gates green, not deployed

## Summary

Adding an axe gate for the Library (the surface that grew filters, uploads and the
add-to-project dialog) exposed four defects that had nothing to do with those features:
the site chrome had **no `<main>` landmark**, the persistent player sat outside every
landmark, four avatars/logo images repeated the adjacent text as `alt`, and the new
picker dialog used an `<h3>` under the page's `<h1>`. All four are fixed at the source,
so every `(site)` page benefits, not just the Library.

## Product impact

- **Screen-reader landmark navigation** now works on every page: `Topbar`/`Sidebar` →
  `main` (route content) → `contentinfo` (footer) → `region "Now playing"` (player).
- **No duplicate announcements**: the brand mark and account avatars are decorative
  (`alt=""`); the nearby text carries the name.
- **Heading order** is valid on the Library's add-to-project dialog (`h2`).
- **No visual change**: the landmark wrapper uses `display: contents`, so the flex
  layout of `.content` is untouched (the 124-test browser suite, including the pixel
  gate, stayed green).

## Technical impact

- `app/(site)/layout.tsx` wraps `{children}` in `<main className="content-main">`;
  `.content-main{display:contents}` keeps the layout identical.
- `components/Player.tsx` root is `role="region" aria-label="Now playing"`.
- Decorative `alt=""` on the `Sidebar` brand mark and avatar, the `Topbar` avatar and the
  `AccountView` avatar.
- `.s-modal-head h2` joins the existing `h3` rule so the dialog heading keeps its style.
- New `tests/e2e/library-a11y.spec.ts` audits four surfaces: the Library page, the filter
  menu (scoped to the menu itself, because Radix marks the page `aria-hidden` while a
  portal is open), the uploads tab, and the add-to-project dialog. Its helper waits for
  finite animations so a fading-in modal is not reported as a contrast failure.

## Files touched

- `camxora.com/app/(site)/layout.tsx`
- `camxora.com/components/{Player,Sidebar,Topbar,AccountView}.tsx`
- `camxora.com/components/LibraryView.tsx` (dialog heading)
- `camxora.com/app/globals.css`
- `camxora.com/tests/e2e/library-a11y.spec.ts` (new)

## Migration/deploy

None. Markup and CSS only.

## Create and marketing (same day)

Axe on `/create` found one more naming defect: the model picker's visible value (`v6`)
was not part of its accessible name (`"Model"`), so voice control could not address what
it saw. The trigger is now labelled `Model: <value>`.

The full run also caught dimmed Radix menu items (`aria-disabled`) at 2.38:1 — WCAG
exempts disabled controls, but the labels are still read out, so `.s-menu` disabled items
now use `--s-text3` instead of the faded tone.

`tests/e2e/create-a11y.spec.ts` audits `/create` (signed in) and the signed-in `/account`,
plus the public pages `/`, `/pricing`, `/discover` and a playlist page, so the global
landmark fix is pinned across the site. All were already clean once the shared shell was
fixed.

## Tests

| Layer | Result |
|---|---|
| `npm run typecheck` | clean |
| `npm run check:ui` | compliant |
| `npm run build` | all routes build |
| Vitest | **268 passed** (29 files) |
| Playwright | **127 passed / 2 skipped** — Studio a11y + pixel gates, Library a11y (page, menu, uploads tab, dialog), Create, Account and the public pages |

## Follow-ups

- The Studio editor's own axe gate still audits its custom menus only; the Radix-based
  `SMenu` (Library/Create) is covered per-surface as above.
- If more Radix dialogs are added, audit them with `auditWithin` rather than a
  document-wide scan.
