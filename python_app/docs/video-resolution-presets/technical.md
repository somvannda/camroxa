# Output Resolution Presets (Global + Per-Profile)

## Current Architecture (Verified)
- Export resolution is currently hardcoded to `1920×1080` in both:
  - Auto-Video export path
  - Manual batch export path
- GPU renderer already supports arbitrary `width/height` and scales backgrounds using `ImageOps.fit()` (cover crop).
- Image generation already has a global `imageResolution` setting, but it is not guaranteed to match video export.

## Data Model
### Global (app_settings)
- Unify around one “output resolution” value so image + video stay aligned:
  - Canonical: `outputResolution` (string, `WxH`, e.g. `1920x1080`)
  - Backward compatibility:
    - Keep reading existing `imageResolution` if present
    - Keep reading existing `videoExport.resolution` if present (if introduced later)
  - Default: `1920x1080`

### Per-Profile (Postgres)
- Add column: `profiles.output_resolution` (text, nullable)
- Expose it as `profile.outputResolution` in the normalized profile dict.
- Empty/NULL means inherit global.

## Resolution Presets
Store as strings `WxH`:
- `1920x1080` (16:9)
- `1080x1920` (9:16)
- `1080x1080` (1:1)
- `1080x1350` (4:5)
- `2560x1440` (QHD 16:9)
- `2160x3840` (4K vertical 9:16) (optional)

## Pipeline Wiring
### Resolution Resolver
- Helper to parse `WxH` with safe clamping.
- Image jobs (background + thumbnail):
  - Use `profile.outputResolution` if set; else global `outputResolution`
- Auto-Video:
  - Use `profile.outputResolution` if set; else global `outputResolution`
- Manual export:
  - Use global `outputResolution` (manual export is not profile-scoped)

### Preview (Optional but recommended)
- Update the Video workspace preview aspect ratio box to match the current resolved output resolution.

## Migration
- Update `music_migrate.py` to add `output_resolution` column if missing.
- Update `db_list_profiles()` and `db_upsert_profile()` to read/write the column.

## Risks / Limitations
- Some templates may be designed for 16:9; vertical output may need template/layout tuning.
- Very large resolutions increase GPU memory usage; keep presets reasonable.
