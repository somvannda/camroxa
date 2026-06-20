## UX

### Video Workspace
- Add a dropdown in the preview header:
  - Label: `Output resolution`
  - Values: same preset list as global settings

### Behavior
- Default value: current resolved output resolution (settings `outputResolution`, fallback to `imageResolution`, fallback to `1920x1080`)
- On change:
  - Persist to settings key `outputResolution`
  - Preview aspect ratio updates immediately

### Non-goals
- No new rendering engine / supersampling preview
- No template-specific resolution override (templates stay reusable across resolutions)

