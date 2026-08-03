# User portal Guides — slide presentation (feature)

**Date:** 2026-08-03  
**Status:** implemented (sandbox shipped); production pending explicit request  
**Branch:** `feat/user-portal-guides-deck`

## Summary

New **Guides** feature in the user portal (`/dashboard/guides`): a 16:9 charcoal/cyan–emerald slide deck for creators. Nav item is pinned at the bottom of the sidebar **above** the Sign out separator.

## Deck sections

1. **Intro** — product pitch, dual-channel flow, time savings
2. **Monetization** — 100% plan refund guarantee (trade-in channels; ends when either channel monetizes)
3. **Onboarding** — niche, names, logo, cover, SEO board
4. **YouTube setup** — create channel, title/desc, keywords/tags, country/playlist
5. **Using CAMXORA** — Settings → Templates → Music → Progress → Images → Upload
6. **Growth** — reply all comments; use channel profile on larger niche channels (policy-safe)
7. **Coming soon** — Our Vision opener (“Create once. Publish everywhere”); DistroKid WAV; YouTube auto upload; Facebook Reels; unified pipeline (no release dates)
8. **Thank you** — next steps + support note

## UX details

- Keyboard (←/→/Space), section chips, progress dots, fullscreen
- Hash deep-links (`#slide-N`)
- Footer notes pinned to the **bottom** of the slide frame (cyan/emerald callout)
- Styled mock panels; optional PNGs under `user_portal/public/guides/`
- Public marketing/onboarding copy only — no secrets or internal ops

## Surfaces / files

| Path | Role |
|------|------|
| `user_portal/src/app/dashboard/guides/*` | page, deck, frame, mocks |
| `user_portal/public/guides/README.md` | PNG slot guide |
| `user_portal/src/components/dashboard/control-panel-shell.tsx` | Guides nav (above Sign out separator) |
| `scripts/deploy/deploy_user_portal_guides_sandbox.py` | path-scoped sandbox ship |
| `scripts/deploy/verify_user_portal_guides_sandbox.py` | smoke helper |

## Not included (leave on other branches / dirty tree)

Quota multi-channel UI, admin pipeline/job-queue, DistroKid product code, streaming LRC API, secrets files, desktop `camxora_python` WIP.

## Deploy

- Sandbox: `python scripts/deploy/deploy_user_portal_guides_sandbox.py`
- Production: only on explicit request (file-scoped hotfix or merge-to-main then portal rebuild)
