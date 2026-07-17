# Camxora Implementation Status

> **Last updated:** 2026-07-07  
> **Current phase:** Phase 9 — Settings page (implemented, manual verify pending)  
> **Tests:** 76 passing (`python -m pytest tests/ -q`)

---

# Quick Start

```bash
# Terminal 1 — platform API (required for login)
cd MusicGenerator
python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8000

# Or use camxora/start-services.ps1

# Terminal 2 — desktop app
cd camxora_python
pip install -e ".[dev]"
python main.py
```

Default API: `http://localhost:8000/api/v1` (not shown in UI — fixed in code).

---

# Phase Progress

| Phase | Name | Status | Exit criteria |
|-------|------|--------|---------------|
| **0** | Foundation | **Done** | Themed app launches |
| **1** | Core shell | **Done** | All 11 routes navigable |
| **2** | Auth + API client | **Done** | Login works against `platform_api` |
| **3** | **Dashboard page** | **Done ✅** | Requirements §14 checklist complete |
| **4** | **Profile page** | **Done ✅** | Requirements §11 checklist complete |
| **5** | **Workflow page** | **Done ✅** | Requirements §11 checklist complete |
| **6** | **Progress page** | **Done ✅** | Requirements §8 checklist complete (manual verify pending) |
| **7** | **Music page** | **Done ✅** | Requirements §15 implemented (manual verify pending) |
| **8** | **Image page** | **Done ✅** | Requirements §15 implemented (manual verify pending) |
| **9** | **Settings page** | **Done ✅** | All 8 tabs implemented (manual verify pending) |
| 10 | Video + export | Pending | Template workspace + visualizer |
| 11 | Automation | Pending | Auto-video, YouTube upload |
| 12 | Polish + deferred | Pending | Merger, Log, onboarding wizard |

---

# What Exists Today

## Application shell

| Module | Path | Notes |
|--------|------|-------|
| Entry point | `main.py` | → `app/bootstrap.py` |
| Root window | `app/root_window.py` | Startup → auth → onboarding → app shell |
| App shell | `app/application.py` | Sidebar + stacked pages |
| Router | `app/router.py` | Real views for home/profile/progress/workflow |
| Navigation | `shared/constants/navigation.py` | Mirrors `shellNavigation.ts` |

## Auth & session

| Module | Path | Notes |
|--------|------|-------|
| Login / register | `features/account/views/auth_view.py` | Email + password; Enter submits |
| Startup splash | `features/account/views/startup_view.py` | Bootstrap progress |
| Onboarding stubs | `features/onboarding/views/onboarding_views.py` | Welcome + wizard placeholder |
| Session service | `shared/services/session_service.py` | Bootstrap routing, token refresh |
| Secure storage | `shared/services/secure_storage.py` | DPAPI-encrypted JSON store |
| Platform client | `shared/services/platform_client.py` | httpx + auto-refresh on 401 |
| Platform API | `shared/services/platform_api.py` | Auth + dashboard + progress + license |
| Platform models | `shared/models/platform.py` | Dashboard, progress, license DTOs |
| Data workers | `shared/workers/data_workers.py` | Dashboard + progress fetch threads |
| Auth models | `shared/models/auth.py` | Pydantic DTOs |

## Shell pages (Phase 3)

| Module | Path | Notes |
|--------|------|-------|
| Dashboard | `features/dashboard/views/dashboard_view.py` | KPIs, usage chart, quotas, activity table |
| Profile | `features/profile/views/profile_view.py` | Account, membership, profiles table, activity |
| Profile widgets | `features/profile/widgets/` | MembershipMetricBar, section cards |
| Progress | `features/progress/views/progress_view.py` | Filters, stats, runtime overlay, manual sync, download queue |
| Progress widgets | `features/progress/widgets/` | Stats row, operational table, download queue |
| Music | `features/music/views/music_view.py` | Batch composer, draft/polish, generate, history |
| Music widgets | `features/music/widgets/` | Settings strip, song editor, channels, automation, history |
| Music download coordinator | `shared/services/music_download_coordinator.py` | Background Suno MP3 downloads |
| Image | `features/image/views/image_view.py` | Job queue, prompts, previews |
| Image widgets | `features/image/widgets/` | Controls/queue card, preview cards |
| Settings | `features/settings/views/settings_view.py` | 8-tab workspace (profiles, YouTube, publication, etc.) |
| Workflow | `features/workflow/views/workflow_view.py` | Lanes, stage board, desktop runtime overlay |
| Workflow widgets | `features/workflow/widgets/` | Filter, lanes, selected run, stage cards |
| Video runtime | `shared/lib/video_runtime_inspection.py` | MP4 directory inspection + presentation map |

## Shared UI

| Module | Path | Notes |
|--------|------|-------|
| Theme | `shared/themes/deep_blue.py` | AutoDistroKid-style QSS |
| Sidebar | `shared/widgets/sidebar_nav.py` | Button nav, no scroll |
| Page header | `shared/widgets/page_header.py` | Eyebrow + title + description |
| Placeholder page | `shared/widgets/placeholder_page.py` | Remaining routes |
| Stat card | `shared/widgets/stat_card.py` | KPI cards |
| Metric bar | `shared/widgets/metric_bar.py` | Quota progress bars |
| Data table | `shared/widgets/data_table.py` | Styled QTableWidget helper |
| Usage chart | `shared/widgets/usage_chart.py` | Weekly usage line chart |
| Pollable page | `shared/widgets/pollable_page.py` | Page-gated polling mixin |

## Tests

| File | Covers |
|------|--------|
| `tests/test_navigation.py` | Shell route constants |
| `tests/test_application.py` | App shell + router smoke |
| `tests/test_session.py` | Token parsing |
| `tests/test_platform_models.py` | Dashboard/progress DTO parsing |
| `tests/test_platform_api.py` | Extended API methods (mocked) |
| `tests/test_dashboard_view.py` | Dashboard loading, error, bind, activity |
| `tests/test_profile_view.py` | Profile loading, error, bind, empty profiles |
| `tests/test_workflow_view.py` | Workflow loading, error, bind, stage board |
| `tests/test_workflow_steps.py` | Step derivation + current focus |
| `tests/test_video_runtime_inspection.py` | MP4 inspection + runtime overlay |

---

# Route Status (`camxora_python`)

| Route | Electron | PySide6 status |
|-------|----------|----------------|
| `/startup` | Yes | **Done** — splash + bootstrap |
| `/auth/login` | Yes | **Done** — live API login |
| `/auth/register` | Yes | **Done** — register + auto-login |
| `/onboarding/welcome` | Yes | **Stub** — message only |
| `/onboarding/wizard/*` | Yes | **Stub** — Phase 8 / full wizard later |
| `/app/home` | Yes | **Done ✅** — [requirements](pages/03_DASHBOARD_REQUIREMENTS.md) |
| `/app/profile` | Yes | **Done ✅** — [requirements](pages/04_PROFILE_REQUIREMENTS.md) |
| `/app/workflow` | Yes | **Done ✅** — [requirements](pages/05_WORKFLOW_REQUIREMENTS.md) |
| `/app/progress` | Yes | Sketch (~50%) — Phase 6 |
| `/app/music` | Yes | **Done ✅** — [requirements](pages/07_MUSIC_REQUIREMENTS.md) |
| `/app/image` | Yes | **Done ✅** — [requirements](pages/08_IMAGE_REQUIREMENTS.md) |
| `/app/video` | Yes | Placeholder → Phase 6 |
| `/app/settings` | Yes | **Done ✅** — 8-tab settings workspace |
| `/app/merger` | Placeholder | Placeholder |
| `/app/log` | Placeholder | Placeholder |

---

# Phase 6 — Progress (Next)

Gather Electron `ProgressPage.tsx` → write requirements doc → build to 100% (includes desktop IPC for downloads/recovery).

---

# Phase 5 — Workflow (Complete ✅)

Implemented per [05_WORKFLOW_REQUIREMENTS.md](pages/05_WORKFLOW_REQUIREMENTS.md):

- `features/workflow/views/workflow_view.py`
- `features/workflow/widgets/` — filter, lanes, selected run, stage board
- `shared/lib/video_runtime_inspection.py` — desktop MP4 inspection
- `tests/test_workflow_view.py`, `tests/test_video_runtime_inspection.py`

---

# Phase 4 — Profile (Complete ✅)

Implemented per [04_PROFILE_REQUIREMENTS.md](pages/04_PROFILE_REQUIREMENTS.md):

- `features/profile/views/profile_view.py`
- `features/profile/widgets/` — MembershipMetricBar, Account/Membership/Profiles/Activity cards
- `tests/test_profile_view.py` — T-1 through T-5

---

# Phase 3 — Dashboard (Complete ✅)

Implemented per [03_DASHBOARD_REQUIREMENTS.md](pages/03_DASHBOARD_REQUIREMENTS.md):

- `features/dashboard/views/dashboard_view.py`
- `features/dashboard/widgets/` — KPI, error banner, weekly usage, remaining month, activity
- `tests/test_dashboard_view.py` — T-1 through T-6

---

# Dependencies (installed)

```text
PySide6>=6.7.0
httpx>=0.27
pydantic>=2.0
cryptography>=42.0
```

Python **3.11+** (tested on 3.11.9).

---

# External requirements

| Service | Required for | How to start |
|---------|--------------|--------------|
| `platform_api` | Login, all API pages | `uvicorn platform_api.main:app --port 8000` |
| PostgreSQL | platform_api backend | Via `.env` in `platform_api/` |
| Redis | platform_api rate limit | Local Redis on 6379 |

---

# Revision History

| Date | Change |
|------|--------|
| 2026-07-07 | **Workflow 100%** — lanes, stage board, video runtime inspection, tests |
| 2026-07-07 | **Profile 100%** — widgets, tests, requirements checklist |
| 2026-07-07 | **Dashboard 100%** — widgets, tests, requirements checklist |
| 2026-07-07 | Page-by-page strategy; Dashboard requirements doc |
| 2026-07-07 | Initial status doc; Phases 0–2 complete |
