# CAMXORA apex Phase 0 checklist

Status date: 2026-10-23

## Completed

- [x] Clean worktree created from `main`.
- [x] Branch created: `feat/camxora-apex`.
- [x] New template source imported to `camxora.com/design-reference`.
- [x] Screenshots and concept studies excluded.
- [x] Logo, hero image, Niradei fonts, Font Awesome 7.3.1 CSS/webfonts/license included.
- [x] Route map drafted.
- [x] Component inventory drafted.
- [x] Migration plan copied into the worktree.

## Pending decisions

- [ ] D-001: approve the app base (`camxora.com` from `music_web` + `website`).
- [ ] D-002: approve `platform_api` as the browser API, with `musicapi` as provider.
- [ ] D-003: confirm `app.camxora.com` remains the billing/API-key portal in v1.
- [ ] D-004: confirm host-only apex auth cookies; no old-app cookie changes.
- [ ] D-005: confirm the old music alias/redirect policy.
- [ ] D-006: confirm MVP vs full 35-page launch scope.

## Next after approval

- [ ] Scaffold `camxora.com` Next.js app.
- [ ] Port design tokens and shared primitives.
- [ ] Build new shell and player on top of existing player logic.
- [ ] Add same-origin `/api/v3` proxy.
- [ ] Add sandbox systemd service on `3103`.
- [ ] Repoint only `sandbox.camxora.com` to `3103`.
- [ ] Add noindex and sandbox OAuth/Turnstile settings.
- [ ] Ship Home + Discover + login to sandbox.
- [ ] Stop at sandbox checkpoint; no production deploy.

## Not changed

- `music.camxora.com`
- `music.sandbox.camxora.com`
- `musicapi.camxora.com`
- `admin.musicapi.camxora.com`
- `app.camxora.com`
- Production nginx
