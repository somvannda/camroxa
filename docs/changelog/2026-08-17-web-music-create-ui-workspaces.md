# 2026-08-17 — Web music create UI overhaul + workspaces

## Music web

- Header: remove Pricing and credit pill when logged in; add user dropdown (Profile, Sign out).
- Sidebar: account card with songs/credits/daily quota and Top up; Upgrade to Pro moved under Privacy menu.
- Create form: model dropdown (default V5.5), clickable Audio/Voice/Inspo tabs, equal-height slider ticks, More Options card rows, negative tags under Styles, vocal gender pill tabs (deselected by default), workspace selector with create-new.

## Platform API

- Migration `092_web_music_workspaces`: `web_music_workspaces` table, `suno_tasks.workspace_id`.
- Endpoints: `GET/POST /api/v1/web-music/workspaces`; generations filtered by `workspace_id`.

## Notes

- Suno exposes a lyrics generation API only (`/api/v1/lyrics`); there is no dedicated style-generation endpoint. Style suggest uses local tag shuffle until a provider adds style generation.
