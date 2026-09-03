# Playlist template backgrounds

Each sub-template (track-list style) has its own folder. Place a full-scene background image here and the preview will use it automatically.

## Folder layout

```
assets/playlist_templates/
  minimal-white/
    background.png      ← drop your wave / silk background here
  glass-blur/
    background.jpg
  cyberpunk/
    background.webp
  …
```

Folder name must match the **sub-template id** (e.g. `minimal-white`, `deep-space`).

Supported filenames:

- `background.png`
- `background.jpg` / `background.jpeg`
- `background.webp`

Or any single image file inside the folder.

## Background images (required for preview)

Each sub-template loads **only** from its bundled folder — no procedural fallback:

```
assets/playlist_templates/
  minimal-white/background.png
  forest-mist/background.png
```

Drop your full-scene image there (1920×1080 or larger recommended). The renderer cover-fits it to the preview canvas.

## Style-picker thumbnails (optional)

Used as the mini preview in **Track list style** when present:

```
assets/playlist_templates/
  minimal-white/thumbnail.png
  forest-mist/thumbnail.png
```

Recommended size: about **264×156** px (2× the 132×78 card preview) or larger. PNG with transparency is fine.
