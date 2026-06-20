# Output Resolution Presets (Global + Per-Profile)

## Product Goals
- Boss can generate images and export videos in common platform-friendly sizes:
  - Landscape (YouTube): 16:9
  - Shorts/Reels/TikTok: 9:16
  - Square: 1:1
  - Instagram feed: 4:5
- Boss can set a global default and optionally override per profile/channel.

## UX / UI
### Global Setting (Settings → Image / Performance)
- Field: `Output resolution`
- Control: preset dropdown
- Shows label + dimensions, e.g.:
  - `Landscape 720p (16:9) — 1280×720`
  - `Landscape 1080p (16:9) — 1920×1080`
  - `Shorts/Reels (9:16) — 1080×1920`
  - `Square (1:1) — 1080×1080`
  - `Instagram Feed (4:5) — 1080×1350`
  - `QHD (16:9) — 2560×1440`
  - `4K UHD (16:9) — 3840×2160`

### Per-Profile Override (Settings → Profiles)
- Field: `Output resolution`
- Control: dropdown with:
  - `Use global (default)` (inherit)
  - same preset list as global

### Visual Expectations
- Image generation outputs are created at the selected width×height:
  - Background image size matches the output resolution
  - Thumbnail image size matches the output resolution
- Export output is exactly the selected width×height.
- Background images use “cover” scaling (center crop) to fill the frame.
- Existing templates may be tuned for 16:9; vertical outputs may require template adjustments (Boss can pick different templates per profile).

## Empty / Edge States
- If an invalid resolution is saved, fall back to global, then to `1920×1080`.
- If profile override is blank, inherit global.
