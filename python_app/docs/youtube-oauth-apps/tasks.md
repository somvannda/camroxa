# YouTube OAuth Apps — Tasks

## Phase 1 — Database
- [x] Add migration for `youtube_oauth_apps`
- [x] Add migration for `profiles.youtube_oauth_app_id`
- [x] Add DB helpers:
  - list/create/update/delete oauth apps
  - list profiles referencing an oauth app (for delete guard)

## Phase 2 — Settings UI (OAuth Apps Manager)
- [x] Add Settings tab: `YouTube`
- [x] Add OAuth Apps list + editor + actions (New/Save/Delete)
- [x] Mask client id display in list (e.g., show first/last 6 chars)
- [x] Validate required fields and show friendly errors

## Phase 3 — Profile Selection UI
- [x] Add profile dropdown: `YouTube OAuth app`
- [x] Persist to DB via existing profile save mechanism
- [x] Handle “Missing · <id>” edge case

## Phase 4 — Runtime Integration
- [x] Update Connect flow to use the selected OAuth app per Profile (fallback to global settings)
- [x] Update Upload flow to use the selected OAuth app per Profile (fallback to global settings)

## Phase 5 — Verification
- [x] `python -m compileall -q python_app`
- [ ] Manual UX smoke test:
  - Create 2 OAuth apps
  - Assign different apps to two profiles
  - Connect each profile and ensure it uses the correct client
  - Upload a test video and confirm it still works

## Documentation
- [ ] Update `python_app/DEVELOPMENT_LOG.md`
