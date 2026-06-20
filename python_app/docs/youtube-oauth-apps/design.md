# YouTube OAuth Apps — Design

## Placement
- Settings → add a new tab: `YouTube`
  - Section A: OAuth Apps manager (global)
  - Section B: quick note that profiles choose which OAuth app to use
- Settings → Profiles:
  - Add field: `YouTube OAuth app` (dropdown)
  - Default option: `Use global settings`

## OAuth Apps Manager (Settings → YouTube)
### Layout
- Two-column panel
  - Left: list/table of OAuth apps
  - Right: editor form

### List/Table
- Columns:
  - Name
  - Client ID (masked/shortened display)
  - Updated
- Selection:
  - Selecting a row loads it into the editor

### Editor Form
- Fields:
  - Name (required)
  - Client ID (required)
  - Client Secret (required; password field; “show/hide” optional future)
- Actions:
  - New (clears editor to create a new config)
  - Save (creates or updates)
  - Delete (only enabled when not referenced by any profile)

## Profile OAuth App Selection (Settings → Profiles)
- A dropdown labeled `YouTube OAuth app`
  - Option 1: `Use global settings`
  - Options 2..N: `<appName>`
- When the profile is connected already:
  - Changing the OAuth app does not automatically reconnect
  - Next Connect action will use the newly selected OAuth app

## UX Rules
- No secrets shown in logs or status labels.
- If a profile’s selected OAuth app is missing/deleted:
  - show it as `Missing · <id>` in the dropdown and block Connect/Upload with a clear error until fixed.
