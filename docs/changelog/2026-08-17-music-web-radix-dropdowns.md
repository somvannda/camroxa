# Music web: Radix/shadcn-style dropdowns and selects

**Date:** 2026-08-17

## Summary

- Added shadcn-style Radix UI components for dropdowns and selects (`@radix-ui/react-dropdown-menu`, `@radix-ui/react-select`).
- User menu header dropdown uses `DropdownMenu` with separator, focus ring, and animations.
- Workspace and model pickers use themed `Select` (dark popover, violet highlight, works on Windows).
- Replaced native `<select>` / hand-rolled menu in create flow.

## Surfaces

- `music_web` — `components/ui/*`, `user-menu`, `music-form-ui`, `create-page-client`
