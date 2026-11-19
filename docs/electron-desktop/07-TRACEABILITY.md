# Traceability — Features, Phases, Tests and Sources

> **Document ID:** CAMXORA-ED-07
> **Version:** 1.0.0
> **Status:** Living document
> **Rule:** No orphan feature. Every feature ID appears in a page doc, a phase task and a
> test suite.
> **Release target:** Camxora Desktop **2.0.0**. Vizzy is the only video engine; the pipeline
> is part of 2.0.0. See [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).
> **Last updated:** 2026-11-19

---

## 1. Feature ID ranges

| Prefix | Page / area | Doc | Phase | Test suite |
|---|---|---|---|---|
| `SH-` | Shell and shared services | [`pages/10-SHELL-AND-SERVICES.md`](pages/10-SHELL-AND-SERVICES.md) | P0/P1/P9 | `shell.spec` |
| `LG-` | Login/auth/onboarding/update | [`pages/01-LOGIN.md`](pages/01-LOGIN.md) | P1 | `auth.spec` |
| `DB-` | Dashboard | [`pages/02-DASHBOARD.md`](pages/02-DASHBOARD.md) | P2 | `dashboard.spec` |
| `PR-` | Profile | [`pages/03-PROFILE.md`](pages/03-PROFILE.md) | P2 | `profile.spec` |
| `PG-` | Progress | [`pages/04-PROGRESS.md`](pages/04-PROGRESS.md) | P3 | `progress.spec` |
| `MU-` | Music | [`pages/05-MUSIC.md`](pages/05-MUSIC.md) | P4 | `music.spec` |
| `IM-` | Image | [`pages/06-IMAGE.md`](pages/06-IMAGE.md) | P5 | `image.spec` |
| `VZ-` | Vizzy | [`pages/07-VIZZY.md`](pages/07-VIZZY.md) | P7 | `vizzy.spec` |
| `MK-` | Marketplace | [`pages/08-MARKETPLACE.md`](pages/08-MARKETPLACE.md) | P6 | `marketplace.spec` |
| `ST-` | Settings | [`pages/09-SETTINGS.md`](pages/09-SETTINGS.md) | P2/P8 | `settings.spec` |
| `PL-` | Pipeline automation + all-91 templates + content parity | [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md) | P7 | `pipeline.spec` + `vizzy-content.spec` + `vizzy-corpus.spec` |
| `QA-` | Cross-cutting quality | [`04-QA-ACCEPTANCE.md`](04-QA-ACCEPTANCE.md) | all | all |
| `PK-` | Packaging/release | [`03-IMPLEMENTATION-PLAN.md`](03-IMPLEMENTATION-PLAN.md) P9 | P9 | manual |

---

## 2. Page ↔ phase ↔ source map

| Page | Phase | PySide6 source | Rea source | API routers |
|---|---|---|---|---|
| Login | P1 | `features/account`, `features/onboarding`, `app/root_window.py`, `shared/services/session_service.py`, `google_desktop_oauth.py`, `software_update_*` | — | `auth`, `users`, `licenses`, `public_desktop` |
| Shell | P0/P1 | `app/application.py`, `app/router.py`, `shared/widgets`, `shared/services` | — | `users`, `ws`, `client_logs` |
| Dashboard | P2 | `features/dashboard` | — | `users`, `stats`, `profiles`, `licenses` |
| Profile | P2 | `features/profile` | — | `users`, `stats`, `profiles`, `licenses` |
| Progress | P3 | `features/progress`, `shared/lib/video_runtime_inspection.py`, `manual_asset_paths.py` | — | `progress`, `settings`, `music_downloads`, `image_jobs` |
| Music | P4 | `features/music`, `shared/services/music_download_coordinator.py` | — | `users`, `profiles`, `settings`, `prompts`, `music_history`, `credits`, `generation`, `batch`, `content_pools`, `music_downloads` |
| Image | P5 | `features/image` | — | `image_jobs`, `settings`, `profiles`, `music_history`, `progress` |
| Vizzy | P7 | — | `G:\Developments\Rea\editor` | `users`, `marketplace` (templates) |
| Pipeline | P7 | `visualizer/*` (reference), `features/video/services/*` (reference) | `G:\Developments\Rea\editor` renderer | `progress`, `batch`, `music_history`, `publish`, `youtube`, `credits` |
| Marketplace | P6 | `features/marketplace` | — | `marketplace` |
| Settings | P2/P8 | `features/settings` | — | `profiles`, `profile_video_templates`, `settings`, `prompts`, `content_pools`, `youtube`, `image_sample_packs`, `client_logs` |

---

## 3. API endpoint map (page-level)

| Page | Endpoint | Method | Purpose |
|---|---|---|---|
| Login | `/auth/login` | POST | Email/password |
| Login | `/auth/register` | POST | Create account |
| Login | `/auth/google/*` | GET/POST | Google flow |
| Login | `/users/me` | GET | Session/entitlement |
| Login | `/licenses/validate` | GET | Plan gate |
| Dashboard | `/stats/dashboard` | GET | KPIs/chart/activity |
| Dashboard | `/profiles` | GET | Context |
| Profile | `/users/me` | GET | Account |
| Profile | `/licenses/validate` | GET | Membership |
| Profile | `/profiles` | GET | Channel profiles |
| Profile | `/stats/dashboard` | GET | Activity |
| Progress | `/progress` | GET | Rows |
| Progress | `/settings` | GET | Image mode |
| Progress | `/music/downloads/pending` | GET | Queue |
| Progress | `/image-jobs/sync-manual` | POST | Continue pipeline |
| Music | `/profiles` | GET | Channels |
| Music | `/settings` | GET/PATCH | Defaults/autosave |
| Music | `/prompts/descriptions/public` | GET | Descriptions |
| Music | `/prompts/structures/public` | GET | Structures |
| Music | `/music/history` | GET | History |
| Music | `/credits/operation-costs` | GET | Costs |
| Music | `/content-pools/{kind}/claim|finalize|release` | POST | Draft seeds |
| Music | `/generation/draft` | POST | Draft |
| Music | `/generation/polish-lyrics` | POST | Polish |
| Music | `/batches` | POST | Generate |
| Music | `/batches/{id}` | GET | Status |
| Music | `/music/downloads/pending` | GET | Downloads |
| Music | `/music/downloads/sync` | POST | Download sync |
| Image | `/image-jobs` | GET | Queue |
| Image | `/image-jobs/retry` | POST | Retry |
| Image | `/image-jobs/clear` | POST | Clear |
| Image | `/settings` | GET/PATCH | Prompts |
| Image | `/music/history` | GET | Batch dates |
| Marketplace | `/marketplace/catalog` | GET | Catalog |
| Marketplace | `/marketplace/items/{id}/download` | GET | Template ZIP |
| Settings | `/profiles` | GET/POST/PATCH/DELETE | Profiles |
| Settings | `/profiles/{id}/youtube/*` | GET/POST | YouTube |
| Settings | `/publish/playlists` | GET/POST | Playlists |
| Settings | `/settings` | GET/PATCH | Preferences |
| Settings | `/prompts/{kind}/public` | GET | Admin prompts |
| Settings | `/prompts/{kind}/mine` | GET/POST/PATCH/DELETE | User prompts |
| Settings | `/content-pools/*` | GET | Pools |
| Settings | `/image-sample-packs` | GET/POST | Packs |
| Settings | `/client-logs` | POST | Diagnostics |
| Vizzy | `/marketplace/catalog` | GET | Template picker |
| Vizzy | `/users/me` | GET | Account chip |
| Pipeline | `/progress` | GET | Run/stage state |
| Pipeline | `/batches/{id}` | GET | Batch inputs |
| Pipeline | `/music/history` | GET | Song metadata |
| Pipeline | `/credits/operation-costs` | GET | Render/merge/upload costs |
| Pipeline | `/credits/consume` | POST | Charge after validated output |
| Pipeline | `/credits/refund` | POST | Refund a failed stage |
| Pipeline | `/publish/*` | POST | YouTube upload |
| Pipeline | `/youtube/*` | GET/POST | Channel/publication state |

The exact request/response schemas come from `platform_api/openapi.json`; generated types are
the contract.

---

## 4. Source file map (PySide6 → Electron)

| PySide6 | Electron target |
|---|---|
| `app/bootstrap.py` | `electron/main.ts` |
| `app/root_window.py` | `electron/main.ts` + `src/features/auth` |
| `app/application.py` | `src/shell/*` |
| `app/router.py` | `src/router.tsx` |
| `shared/constants/navigation.py` | `src/shell/routes.ts` |
| `shared/services/session_service.py` | `electron/services/session.ts` |
| `shared/services/platform_client.py` | `electron/services/api-client.ts` |
| `shared/services/platform_api.py` | `src/lib/api.ts` + generated schema |
| `shared/services/secure_storage.py` / `dpapi.py` | `electron/services/session.ts` (`safeStorage`) |
| `shared/services/software_update_*` | `electron/services/updates.ts` |
| `shared/services/app_logger.py` | `electron/services/logger.ts` |
| `shared/services/file_service.py` | `electron/services/paths.ts` + `files.ts` |
| `shared/services/audio_analysis_cache.py` | `electron/services/cache.ts` |
| `shared/services/music_download_coordinator.py` | `electron/services/coordinators/music-downloads.ts` |
| `shared/services/pipeline_recovery_coordinator.py` | `electron/services/coordinators/pipeline-recovery.ts` |
| `shared/services/image_output_sync_coordinator.py` | `electron/services/coordinators/image-sync.ts` |
| `shared/services/progress_local_sync_coordinator.py` | `electron/services/coordinators/progress-sync.ts` |
| `shared/services/video_pipeline_coordinator.py` | `electron/services/coordinators/video-pipeline.ts` |
| `features/account/*` | `src/features/auth/*` |
| `features/dashboard/*` | `src/features/dashboard/*` |
| `features/profile/*` | `src/features/profile/*` |
| `features/progress/*` | `src/features/progress/*` |
| `features/music/*` | `src/features/music/*` |
| `features/image/*` | `src/features/image/*` |
| `features/marketplace/*` | `src/features/marketplace/*` |
| `features/settings/*` | `src/features/settings/*` |
| `visualizer/*` | **Reference only** for pipeline behavior; 2.0.0 renders on Vizzy, not the Python engine |
| `features/video/services/pipeline_automation_service.py` | `electron/services/pipeline/orchestrator.ts` |
| `features/video/lib/pipeline_inputs.py` | `electron/services/pipeline/bindings.ts` |
| `features/video/lib/render_scene_request.py` | `electron/services/pipeline/bindings.ts` |
| `features/video/lib/pipeline_merge.py` | `electron/services/pipeline/merge.ts` |
| `features/video/lib/video_template_draft.py` | Reference only; old Camxora templates are not migrated in 2.0.0 |
| `features/video/services/template_normalizer.py` | Reference only; not used by the Electron pipeline |
| `camxora_python/visualizer/templates/*` | **Not migrated** in 2.0.0 |
| `G:\Developments\Rea\editor` presets/catalogues | Vizzy content parity source (PL-41 … PL-45) |
| `G:\Developments\Rea\docs\reference-exports\creations\templates` | All 91 templates (90 JSON + Moai Money); product library, not just fixtures |
| `G:\Developments\Rea\editor\public\creations\assets\templates` | Ported media for the 91 (265.6 MB); first-run pack or bundle; licence record required |
| `G:\Developments\Rea\editor\src\domain\presets.ts` | “Save as video template” / user preset source |
| `camxora_python/shared/themes/*` | `src/styles/tokens.css` |

---

## 5. Review checklist (per page)

- [ ] Every feature ID has an owner and a phase.
- [ ] Every `P0` feature has an acceptance criterion.
- [ ] Every acceptance criterion maps to a test.
- [ ] Every test has a runnable command.
- [ ] Every source file is mapped to a target.
- [ ] No feature is marked done without evidence.
- [ ] Open questions do not block the page or are explicitly deferred.
