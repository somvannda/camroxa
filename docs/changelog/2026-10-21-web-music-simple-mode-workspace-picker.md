# Show the workspace picker in Simple mode

**Date:** 2026-10-21  
**Surfaces:** music_web

## Summary

The Create page's **Save to…** workspace picker lived inside the Advanced-only block, so
Simple mode had no way to choose the target workspace from the form — users had to switch
to Advanced or use the Workspaces panel on the right. The picker (with the optional song
title) now renders below both forms, so Simple mode can choose where its batch lands.

## Product impact

- Simple mode shows **Song Title (Optional)** and **Save to…** under *Songs to generate*.
- The selected workspace drives Simple-mode batch generation the same way it already did
  for Advanced: `onCreate()` sends `workspace_id` for both modes.
- New workspace / rename remain in the Workspaces panel header (unchanged); the picker
  lists every workspace the panel already loaded.

## Technical impact

- `music_web/src/components/create-page-client.tsx`: the title + workspace card moved out
  of the `mode === 'advanced'` branch and renders after the mode conditional, with
  `mt-3` to match the forms' `space-y-3` rhythm.
- Frontend only. No API, billing, or schema change.

## Files touched

- `music_web/src/components/create-page-client.tsx`
- `music_web/CHANGELOG.md`

## Migration/deploy

Rebuild music web. No backend change, no migration.

## Tests

- `npx tsc --noEmit` (music_web) — no new errors (only the pre-existing `.ts`-extension
  errors in `src/lib/*.test.ts`).
- `npm test` (music_web) — 57/57 pass.
- Manual: open Create, stay on **Simple**, confirm the title + *Save to…* card appears under
  *Songs to generate* and the dropdown switches the active workspace.
