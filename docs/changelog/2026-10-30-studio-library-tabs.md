# Studio clone — library dock tabs

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surface:** `camxora.com`

## Goal

F14: Suno's Studio library dock groups the user's material. Add the tabs we can
back with real endpoints, and leave the rest out.

## What landed

`camxora.com/components/StudioShell.tsx`

- **Songs** tab — the existing list (ready generations), unchanged behaviour:
  click to add at the playhead, drag onto a lane.
- **Liked** tab — the same rows filtered by the liked clip keys already used by
  the library (`clipTrackKey(songId, variant)` via `fetchWebMusicLikedKeys`).
- Tabs load their data when the drawer opens; switching is instant.

`camxora.com/app/globals.css`: pill-style tab row using `--s-*` tokens.

## Removed before shipping

A **Projects** tab was implemented, listed the platform's `studio_projects`, then
removed: those ids are not Suno Studio project ids, so choosing one opened an
empty editor (`GET /studio/sessions/{id}` → 404). It stays out until the two id
spaces can be mapped — the same constraint already recorded for F1.

## Verified in the browser

With the drawer open on project `dfd09f57-…`:

- tabs render as `Songs`, `Liked`;
- Songs lists all four finished songs (`Drive tonight`, `Neon Afterglow`,
  `Quiet Morning`, `Phnom Penh Dusk`);
- Liked narrows to `Phnom Penh Dusk`;
- switching back restores the full list;
- console clean.

`npx tsc --noEmit` and `npm run check:ui` pass.

## Still missing from the dock

Stems, Uploads, Workspaces (endpoints exist for uploads/workspaces, but adding
them to the timeline needs upload/Stem assets in `state`, which is a separate
piece of work).
