## Video After Suno — Technical

### Existing Systems
- Profiles are stored in Postgres table `profiles` and loaded via DB persistence helpers.
- Video templates are stored in Postgres table `video_templates` and listed/loaded via DB helpers.

### Change Overview
- Add `profiles.video_template_id` column in migration.
- Extend profile read/write to include `videoTemplateId` (camelCase in app, snake_case in DB).
- Add a dropdown in Settings → Profiles to pick a template id.

### Data Model
- Profile (app):
  - `videoTemplateId: str` (empty string when unset)
- Profile (DB):
  - `video_template_id text`

### Files to Modify
- Migration:
  - `python_app/database/music_migrate.py` — add `video_template_id` column + optional index.
- DB layer:
  - `python_app/database/persistence.py` — include `video_template_id` in `db_list_profiles` + `db_upsert_profile`.
- Model normalization:
  - `python_app/models/music_model.py` — include `videoTemplateId` in `normalize_profile`.
- UI:
  - `python_app/views/music_view.py` — add dropdown widget in Profiles settings form.
  - `python_app/main.py` — load templates into dropdown, populate selected value when profile selected, persist selected id on Save.

### Backward Compatibility
- Existing profiles without `video_template_id` continue to load with `videoTemplateId=""`.
- Existing DBs will receive the new column via `Migrate`.
