# camxora.com

New apex frontend for `camxora.com`.

## Status

Phase 0: design reference imported. The application scaffold is not created yet.

No production deploy. No changes to `music.camxora.com`, `musicapi.camxora.com`, or their admin consoles.

## Purpose

Build the new Camxora music platform from the new templates while reusing the proven auth, player, streaming, library, playlist, likes, credits, and checkout logic from the existing stack.

## Structure

```
camxora.com/
  design-reference/   Static prototype snapshot. Reference only; never served.
  README.md
```

Planned next folders after Phase 1 approval:

```
camxora.com/
  app/                Next.js routes
  components/         New visual components
  lib/                API clients and adapters
  public/             Logo, fonts, Font Awesome, local images
  design-reference/   Static reference snapshot
```

## Decisions pending

- D-001: app base. Recommended: new `camxora.com` app from `music_web` + `website`.
- D-002: runtime API. Recommended: `platform_api` `/api/v3`; `musicapi` remains provider.

## Rules

- Every visible surface uses the new templates.
- Reuse logic, not old JSX or old CSS.
- Browser calls use same-origin `/api/v3`; never hardcode the backend origin.
- Pricing and credit costs come from the API/pricing table, never hardcoded.
- Dark mode only.
- Original `camxora-logo.svg`, local Inter + Niradei, local Font Awesome 7.3.1.
- Keep `music.camxora.com` untouched until the explicit production cutover.
