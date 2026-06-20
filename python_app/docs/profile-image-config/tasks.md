## Profile-Scoped Image Configuration - Tasks

Status legend: pending | in progress | completed | blocked | needs review

---

## Phase 0 — Inspect (completed)
- [completed] Verify where profiles are stored and saved:
  - [persistence.py (profiles)](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L290-L397)
  - [music_model.py normalize_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L196-L218)
- [completed] Verify how image jobs are enqueued and what is currently global:
  - [image_controller.py enqueue](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/image_controller.py#L189-L278)

---

## Phase 1 — Data Model (pending)
## Phase 1 — Data Model (completed)
- [completed] Decide storage approach:
  - Option A: `profiles.image_config` jsonb
- [completed] Add DB migration in [music_migrate.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_migrate.py#L238):
  - add column with default `{}`::jsonb
- [completed] Update persistence mapping:
  - [db_list_profiles](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L290-L350)
  - [db_upsert_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L380-L399)
  - [normalize_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/music_model.py#L200-L250)

Acceptance
- Profiles load/save roundtrip preserves `imageConfig`.

---

## Phase 2 — UI (Profiles tab) (completed)
- [completed] Add Profile → Image section UI controls (prompts, sample dirs, sample selection).
- [completed] Wire load/save:
  - [MainWindow._load_music_settings_profile_details](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4429-L4620)
  - [MainWindow._save_music_settings_profile](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4814-L4925)

Acceptance
- Switching profiles updates the UI fields correctly.
- Saving updates only the selected profile.

---

## Phase 3 — Workflow (in progress)
- [completed] Update image enqueue logic to resolve profile overrides (prompts, samples, random mode):
  - [ImageController._enqueue_batch_channel_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/image_controller.py#L189-L318)
- [completed] Ensure Random mode uses per-profile sample dirs at run-time:
  - [image_generation.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/image_generation.py#L51-L178)
- [completed] Implement “Thumbnail only (reuse for background)” mode:
  - skip background job creation when `imageConfig.mode == "thumb_only"`
  - background consumers resolve to the thumbnail output via DB helper (needs review)

Acceptance
- Two profiles produce different prompts/sample selections in newly enqueued jobs.
- `thumb_only` creates only thumbnail jobs.

---

## Phase 4 — Verification + Docs (pending)
- [pending] Smoke test with DB:
  - create 2 profiles with different image configs
  - enqueue image jobs and verify differences in `image_jobs` rows
- [pending] Update `python_app/DEVELOPMENT_LOG.md` with implementation notes.
