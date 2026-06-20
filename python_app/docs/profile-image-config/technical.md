## Profile-Scoped Image Configuration - Technical

### Current Behavior (Verified)
- Profiles are stored in Postgres `profiles` table and are loaded/saved via:
  - [db_list_profiles](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L290-L351)
  - [db_upsert_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L353-L397)
- Image jobs are keyed by `(batch_id, profile_id, kind)` and already store the final `prompt` and `sample_paths` per job:
  - Job enqueue: [ImageController._enqueue_batch_channel_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/image_controller.py#L189-L318)
  - Table schema: [music_migrate.py (image_jobs)](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_migrate.py#L373-L413)
- However the inputs for enqueue are mostly global settings:
  - `settings.imagePrompt`, `settings.imageBgSamples`, `settings.imageThumbSamples`, `settings.imageBgRandom`, `settings.imageThumbRandom`
  - Random-mode sample directory resolution also used to be global-only, but is now resolved per profile/job in the image worker.

---

## Target Design
Goal: allow per-profile overrides while keeping the current global settings as defaults.

### Data Model Options

#### Option A (Recommended): `profiles.image_config` JSONB
Add one column:
- `profiles.image_config jsonb not null default '{}'::jsonb`

Pros:
- Minimal schema churn while supporting multiple related settings.
- Keeps future expansion (more per-profile config) straightforward.
- Avoids adding 10+ columns to `profiles`.

Cons:
- Requires careful normalization and defaulting in Python.

**Proposed `image_config` schema (JSON)**
```json
{
  "mode": "bg_thumb",
  "basePrompt": "",
  "backgroundPrompt": "",
  "thumbnailPrompt": "",
  "backgroundSamplesDir": "",
  "thumbnailSamplesDir": "",
  "backgroundRandom": null,
  "thumbnailRandom": null,
  "backgroundSamples": [],
  "thumbnailSamples": []
}
```
`backgroundRandom` / `thumbnailRandom` use:
- `null` = inherit global setting
- `true/false` = explicit override

Mapping (Python profile dict):
- Add `imageConfig` key to profile dict returned by [normalize_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L200-L250) and DB functions.

Migration (SQL sketch):
```sql
alter table profiles add column if not exists image_config jsonb not null default '{}'::jsonb;
```

#### Option B: Explicit columns
Add discrete columns like `image_mode`, `image_prompt_base`, `image_bg_samples_dir`, etc.

Pros:
- Easier ad-hoc SQL filtering/reporting.

Cons:
- Larger migration + more boilerplate mapping + harder to evolve.

---

## Integration Plan

### 1) Persistence Layer
Update:
- [db_list_profiles](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L290-L351) to select `image_config`.
- [db_upsert_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L353-L397) to insert/update `image_config`.
- [normalize_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L196-L218) to include a normalized `imageConfig` dict with defaults.

### 2) UI Layer (Profiles tab)
Update the Profiles tab host methods:
- Load UI: [MainWindow._load_music_settings_profile_details](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4429-L4620)
- Save UI: [MainWindow._save_music_settings_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4814-L4925)

Add widgets (suggested names):
- `music_settings_profile_image_mode` (combo)
- `music_settings_profile_image_base_prompt` (text edit)
- `music_settings_profile_image_bg_prompt` (text edit)
- `music_settings_profile_image_thumb_prompt` (text edit)
- `music_settings_profile_image_bg_dir` / `music_settings_profile_image_thumb_dir` (line edits + browse)
- `music_settings_profile_image_bg_random` / `music_settings_profile_image_thumb_random` (checkbox)
- `music_settings_profile_image_bg_samples` / `music_settings_profile_image_thumb_samples` (list/multi-select UI)

### 3) Workflow Layer (Enqueue logic)
Update [ImageController._enqueue_batch_channel_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/image_controller.py#L189-L318) to:
- Read `profile.imageConfig` (via `host._music_profile_by_id(profile_id)`)
- Resolve:
  - mode (`bg_thumb` vs `thumb_only`)
  - prompt sources (profile overrides → base prompt → global prompt → preset)
  - sample strategy (profile → global)
- If `thumb_only`:
  - skip creating the background job
  - thumbnail generation no longer depends on a pre-generated background job (it selects a base sample directly or falls back to solid black)
  - downstream consumers resolve background via `get_ready_background_output()` which falls back to the thumbnail output when `mode == "thumb_only"`

### 3.1) Workflow Layer (Random mode dirs)
Random mode sample dirs and random flags are resolved per job/profile at runtime:
- [run_pending_image_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/image_generation.py#L51-L178)
- Uses [db_get_profile_image_config](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L355-L385) for lookup.

### 4) Backward Compatibility
- If a profile has no `imageConfig`, treat as “inherit global”.
- Existing jobs remain valid because each job already stores its own prompt and sample paths at creation time.

---

## Risks / Constraints
- Needs a DB migration; profiles already require Postgres, so this aligns with current architecture.
- If you later introduce user sign-in and multi-tenant data, `profiles` should gain a `user_id` (or `account_id`) foreign key; the `image_config` jsonb remains valid and portable.

---

## Verification Strategy
- Unit-level:
  - normalize/defaulting for `imageConfig`
  - prompt resolution precedence
  - job enqueue behavior for `thumb_only`
- Integration:
  - create 2 profiles with different prompts/samples and verify enqueued jobs differ
  - ensure global settings still work when profile config is empty
