# Web music workspace rename

**Date:** 2026-08-17  
**Surfaces:** `platform_api`, `music_web`

## Summary

Users can rename an existing web music workspace from the Create page.

## API

- `PATCH /api/v1/web-music/workspaces/{workspace_id}` with body `{ "name": "..." }`
- Validates name length (1–120 chars) and ownership

## UI

- Pencil button next to the workspace dropdown on Create
- Inline rename field with Save / Cancel (Enter to save, Escape to cancel)
