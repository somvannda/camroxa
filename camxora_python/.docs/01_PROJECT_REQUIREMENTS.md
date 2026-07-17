# Camxora Project Requirements

> **Version:** 2.1.0 (Draft)  
> **Status:** Phases 0–2 complete — **Phase 3: Dashboard page (page-by-page)**  
> **Page specs:** `.docs/pages/` — see [00_PAGE_BY_PAGE_STRATEGY.md](pages/00_PAGE_BY_PAGE_STRATEGY.md)  
> **Progress tracker:** `02_IMPLEMENTATION_STATUS.md`
> **Primary source:** `camxora/` (Electron desktop app — latest UX, APIs, flows)  
> **Secondary source:** `platform_api/` (FastAPI backend — business logic & persistence)  
> **Subprocess reference:** `python_app/` (GPU visualizer, FFmpeg export — where Electron still spawns Python)  
> **Target application:** `camxora_python/` (Camxora PySide6)

---

# 1. Purpose

Rebuild **Camxora** as a production-quality **PySide6** desktop application following `00_AI_SYSTEM_PROMPT.md`.

**`camxora/` (Electron) is the source of truth** for features, user flows, API integration, and latest functionality. The legacy `python_app/` (PyQt) codebase is **not** the primary reference — it is only used where the Electron app still delegates to Python subprocesses (GPU video export, optional embedded preview).

`camxora_python/` is an **API-first thin client** (same architecture as Electron): business logic and persistence live in **`platform_api`**, not in the desktop app.

Development proceeds **phase by phase**, not as a single big-bang rewrite.

### Source-of-Truth Hierarchy

| Priority | Source | Use for |
|----------|--------|---------|
| **1** | `camxora/src/renderer/` | UX flows, screen layout, feature scope, API calls |
| **2** | `camxora/src/main/` + `preload/` | Desktop-only behavior: secure storage, file I/O, subprocess spawn |
| **3** | `platform_api/` | REST endpoints, server-side business rules, database schema |
| **4** | `python_app/` | Subprocess implementations only (visualizer, merge, template JSON) |

---

# 2. Scope

## 2.1 In Scope

| Area | Requirement |
|------|-------------|
| Feature parity | Match all implemented `camxora/` Electron routes and workflows |
| API client | Port `platformEndpoints.ts` + `platformClient.ts` → Python httpx client |
| Desktop services | Secure token storage, file dialogs, downloads, subprocess orchestration |
| Background workers | Music download coordinator, auto-video pipeline, YouTube upload automation |
| UI | Rebuild Electron screens as native PySide6 widgets + deep blue QSS |
| Video export | Pipeline export via `python_app.visualizer` subprocess (same as Electron main) |
| Effect packs | Port effect pack registry from Electron main process |
| Architecture | Feature-first MVVM + Clean Architecture per master prompt |

## 2.2 Out of Scope (Explicitly Excluded)

| Area | Reason |
|------|--------|
| `python_app/design_system/` | Custom PyQt QSS — replaced by native PySide6 + `deep_blue.py` |
| `python_app/views/` | Legacy mixin UI — rebuild from Electron feature pages |
| `python_app/` coordinators as primary logic | Superseded by platform API + Electron flow patterns |
| Local embedded PostgreSQL in desktop app | Electron has no local DB; data lives in `platform_api` |
| React / Tailwind / WebGPU renderer | Widget-only PySide6; no Electron/React port |
| Electron frameless chrome | Standard `QMainWindow` with native title bar |
| Prototype-quality code | All deliverables must be production-ready |

---

# 3. Technology Stack

| Component | Requirement |
|-----------|-------------|
| Python | 3.11+ (target 3.13+) |
| UI framework | **PySide6 (Qt6) only** — no PyQt6, no additional UI frameworks |
| Database ORM | SQLAlchemy (when database layer is introduced) |
| Configuration / models | Pydantic (settings and DTOs — replace plain dicts over time) |
| Logging | Loguru |
| Testing | pytest, pytest-qt |
| Media | FFmpeg, OpenCV (when required), Pillow |
| GPU visualizer | moderngl, pygame, librosa, numpy (subprocess — same as source) |
| HTTP clients | httpx |
| Async | asyncio where appropriate |

**Do not introduce** additional UI frameworks unless explicitly requested later.

---

# 4. Architecture Requirements

## 4.1 Pattern

Use **MVVM + Clean Architecture** with a **feature-first** folder layout (see `00_AI_SYSTEM_PROMPT.md`).

Responsibilities must be separated:

- **Views / Widgets** — display data, emit signals only
- **ViewModels** — bind UI state, coordinate user actions
- **Services** — HTTP, media, external APIs
- **Coordinators** — background automation (download, auto-video, upload) — port patterns from Electron shell coordinators
- **Repositories / DB** — data access
- **Models** — Pydantic or dataclass DTOs
- **Workers** — background threads, never block UI thread

**Never mix business logic into UI widgets.**

## 4.2 Target Project Structure

Project root: **`camxora_python/`**

```text
camxora_python/
├── main.py
├── pyproject.toml
├── app/
│   ├── application.py
│   ├── bootstrap.py
│   ├── router.py
│   ├── dependency_container.py
│   └── config.py
├── features/
│   ├── dashboard/
│   ├── workflow/
│   ├── music/
│   ├── images/
│   ├── videos/
│   ├── merger/
│   ├── uploader/
│   ├── library/
│   ├── settings/
│   ├── logs/
│   └── … (other feature modules)
├── shared/
│   ├── widgets/
│   ├── dialogs/
│   ├── services/
│   ├── models/
│   ├── workers/
│   ├── utils/
│   ├── themes/          ← deep blue QSS (deep_blue.py)
│   └── constants/
├── database/
├── resources/
├── tests/
└── docs/
```

## 4.3 Architecture Model (Match Electron)

Camxora Electron is a **thin client**:

```text
PySide6 UI  →  httpx  →  platform_api (:8000)
     ↓
Local services: secure storage, QFileDialog, subprocess spawn (Python visualizer, FFmpeg)
```

The desktop app **does not embed a database**. Settings, batches, jobs, profiles, and progress are fetched/mutated via REST API (same as Electron).

## 4.4 Composition Root

- Thin `QMainWindow` application shell matching `AppShellLayout.tsx`
- Feature-owned pages matching Electron routes (`AppRouter.tsx`)
- `dependency_container.py` wires platform client + local services
- Background coordinators as headless workers (equivalent to `DesktopMusicDownloadCoordinator`, `DesktopVideoPipelineCoordinator`)

## 4.5 Source → Target Mapping

| `camxora/` (Electron) | `camxora_python/` target | Notes |
|-----------------------|--------------------------|-------|
| `features/startup/StartupPage.tsx` | `app/bootstrap.py` | Splash + session bootstrap |
| `shared/auth/bootstrap.ts` | `features/account/services/session_service.py` | Token hydrate, refresh, route decision |
| `features/auth/LoginPage.tsx`, `RegisterPage.tsx` | `features/account/views/` | Auth screens |
| `features/onboarding/` | `features/onboarding/` | Wizard steps (genre, names, logos, covers) |
| `app/layout/AppShellLayout.tsx` | `app/application.py` | Sidebar nav + stacked pages |
| `app/routes/AppRouter.tsx` | `app/router.py` | Page registration |
| `features/shell/shellNavigation.ts` | `shared/constants/navigation.py` | Nav labels and page keys |
| `features/shell/HomePage.tsx` | `features/dashboard/` | KPIs, license, usage |
| `features/shell/ProfilePage.tsx` | `features/profile/` | Account, plan, credits |
| `features/shell/WorkflowPage.tsx` | `features/workflow/` | Pipeline timeline |
| `features/shell/ProgressPage.tsx` | `features/progress/` | Progress table + polling |
| `features/music/MusicWorkspacePage.tsx` | `features/music/` | Batch composer, pools, history |
| `features/music/DesktopMusicDownloadCoordinator.tsx` | `features/music/workers/download_coordinator.py` | Suno download + API sync |
| `features/image/ImageWorkspacePage.tsx` | `features/images/` | Image job queue |
| `features/video/` (workspace + export) | `features/videos/` | Template editor, export queue |
| `features/settings/SettingsWorkspacePage.tsx` | `features/settings/` | All settings tabs |
| `shared/api/platformEndpoints.ts` | `shared/services/platform_client.py` | Full REST surface (~1000 lines TS → Python) |
| `shared/api/platformClient.ts` | `shared/services/http_client.py` | Bearer auth, auto-refresh on 401 |
| `preload/` secureStorage + files IPC | `shared/services/secure_storage.py`, `file_service.py` | DPAPI-encrypted tokens, QFileDialog |
| `main/index.ts` video/export IPC | `features/videos/services/export_service.py` | Spawn `python_app.visualizer.main` |
| `main/effectPackRegistry.ts` | `features/videos/effect_packs/` | Installable effect packs |
| `main/index.ts` local JSON stores | `shared/services/local_store.py` | Video workspace prefs, audio analysis cache |
| Placeholder: `/app/merger`, `/app/log` | `features/merger/`, `features/logs/` | Implement when Electron adds them, or port from `python_app/` |
| WebGPU preview (`features/video/preview/`) | `features/videos/preview/` | **Use ModernGL subprocess** (not WebGPU) — same as Electron's Python preview path |
| `python_app/visualizer/` | `features/videos/visualizer/` | Subprocess reference — spawn, don't rewrite GPU shaders yet |

---

# 5. UI Requirements

## 5.1 Design Philosophy

The UI must be **simple but beautiful** — inspired by clean dark desktop apps (e.g. AutoDistroKid reference):

- Native PySide6 widgets
- Standard window chrome (menu bar, title bar)
- Layout managers only — **no absolute positioning**
- High DPI support (125%–200% scaling)
- Readable spacing and grouped sections
- No custom-painted cards, glass morphism, or heavy styling

## 5.2 Preferred Widgets

Use Qt built-ins before custom implementations:

- `QMainWindow`, `QMenuBar`, `QStatusBar`
- `QSplitter`, `QStackedWidget`, `QTabWidget`
- `QListView` / `QTreeView` / `QTableView` for medium/large datasets
- `QProgressBar`, `QPlainTextEdit` (logs)
- `QFormLayout`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`
- `QPushButton`, `QCheckBox`, `QComboBox`, `QLineEdit`, `QSpinBox`
- `QFileDialog`, `QMessageBox`, `QDialog`

Avoid `QListWidget` / `QTableWidget` where Model/View scales better.

## 5.3 Theme — Deep Blue Compact (AutoDistroKid Reference)

PySide6 does **not** ship with this theme by default. Camxora uses a **compact, clean professional QSS** applied to native widgets — the same approach as the AutoDistroKid reference UI.

**Implementation:**

1. **`QApplication.setStyle("Fusion")`** — consistent cross-platform base
2. **`MAIN_STYLESHEET`** — single QSS file covering all standard widgets
3. **`COLORS` dict** — programmatic access to palette values in Python code

**Do not** port the 2000+ line token/QSS generator from `python_app/design_system/`.

Theme module: `shared/themes/deep_blue.py`

Apply at startup via:

```python
from shared.themes import apply_theme
apply_theme(app)
```

### Color Palette (`COLORS`)

| Token | Hex | Usage |
|-------|-----|-------|
| `bg_dark` | `#0f1923` | Window / main background |
| `bg_medium` | `#1a2a3c` | Inputs, tabs, progress track |
| `bg_light` | `#1a3a5c` | Buttons, selected items |
| `border` | `#2a4a6c` | Input borders, dividers |
| `accent` | `#4ac0ff` | Section titles, tab underline, focus |
| `primary` | `#1a6afe` | Selection, checked indicators, progress fill |
| `success` | `#00a86b` | Start / confirm button (`#start_button`) |
| `danger` | `#c0392b` | Stop / destructive button (`#stop_button`) |
| `text` | `#e0e0e0` | Primary text |
| `text_muted` | `#5a7a8a` | Status bar, secondary info |
| `text_dim` | `#3a5a6a` | Disabled / dim text |

### Styled Widget Conventions

| Object name | Widget | Effect |
|-------------|--------|--------|
| `start_button` | `QPushButton` | Green bold primary action |
| `stop_button` | `QPushButton` | Red stop action |
| `title` | `QLabel` | 14pt bold `#4ac0ff` heading |
| `subtitle` | `QLabel` | 8pt muted caption |

### QSS Coverage

The stylesheet styles these native widgets globally:

`QPushButton`, `QTreeWidget`, `QProgressBar`, `QTextEdit`, `QLabel`, `QLineEdit`, `QComboBox`, `QCheckBox`, `QSlider`, `QTabWidget`, `QScrollBar`, `QMenuBar`, `QMenu`, `QStatusBar`, `QSplitter`, `QGroupBox`, `QFrame`, `QToolTip`

Font: **Segoe UI 9pt** (UI), **Consolas 8pt** (log areas).

## 5.4 Layout Patterns (Reference UI)

Main workspace pages should follow patterns like:

- **Split layout** — list/queue on left, progress + log on right (`QSplitter`)
- **Settings** — `QTabWidget` with form sections (`QGroupBox` + `QFormLayout`)
- **Footer** — status summary in `QStatusBar`
- **Actions** — primary (green), secondary (blue), destructive (red) via object names + minimal QSS

## 5.5 Navigation Pages

Match Electron `AppRouter.tsx` and `shellNavigation.ts`:

| Route (Electron) | Page | Feature module | PySide6 status |
|------------------|------|----------------|----------------|
| `/startup` | Startup / splash | `app/root_window.py` | **Done** |
| `/auth/login`, `/auth/register` | Auth | `features/account/` | **Done** |
| `/onboarding/*` | Onboarding wizard | `features/onboarding/` | **Stub** (Phase 8) |
| `/app/home` | Dashboard | `features/dashboard/` | **~70%** — [spec](pages/03_DASHBOARD_PAGE_SPEC.md) |
| `/app/profile` | Profile | `features/profile/` | Sketch → Phase 4 |
| `/app/workflow` | Workflow | `features/workflow/` | Sketch → Phase 5 |
| `/app/progress` | Progress | `features/progress/` | Sketch → Phase 6 |
| `/app/music` | Music workspace | `features/music/` | Placeholder → Phase 7 |
| `/app/image` | Image workspace | `features/images/` | Placeholder → Phase 5 |
| `/app/video` | Video workspace | `features/video/` + `visualizer/` | Placeholder → Phase 9 — [requirements](pages/09_VIDEO_REQUIREMENTS.md), [Electron↔python_app integration](pages/09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md) |
| `/app/merger` | Merger | `features/merger/` | Placeholder |
| `/app/settings` | Settings | `features/settings/` | Placeholder → Phase 5 |
| `/app/log` | Log | `features/logs/` | Placeholder |

---

# 6. Functional Requirements (Parity with `camxora/` Electron)

All behavior must match the **latest Electron app** unless explicitly changed.

## 6.1 Core Application

- [x] Startup splash with session bootstrap (`StartupPage` + `bootstrap.ts` logic)
- [x] Auth routing: no tokens → login; 0 profiles → onboarding; else → home
- [x] Main window after authentication (app shell)
- [x] Proactive token refresh before API calls
- [x] Platform API default URL `http://localhost:8000/api/v1` (fixed, not user-editable)
- [x] Secure token storage (DPAPI-encrypted on Windows)
- [ ] Session keep-alive background timer
- [ ] Background coordinators (music download, auto-video pipeline)

## 6.2 Auth & Onboarding

- [x] Login and register via platform API
- [x] Login form: Enter key submits from password field
- [x] Logout clears session and returns to login
- [ ] Email verification gate for onboarding (stub welcome page only)
- [ ] Multi-step onboarding wizard: genre, names, logos, covers, overview
- [ ] License validation display (`/licenses/validate`)

## 6.3 Dashboard & Profile

- [ ] Dashboard KPIs, plan/license info, usage charts, recent activity
- [ ] Profile page: account, plan, credits, profile allowance

## 6.4 Music

- [ ] Batch composer: date range, profiles, description/structure, title/album/lyrics
- [ ] Content pool integration: claim/release/finalize (titles, albums, openings)
- [ ] Batch creation with automation flags (autoGenImage, autoGSuno, autoVideo, autoMerge, autoReel, autoUploadYouTube)
- [ ] Draft generation + lyrics polish via platform API
- [ ] History table with batch/song detail
- [ ] **DesktopMusicDownloadCoordinator:** poll pending downloads → local file save → API sync

## 6.5 Image

- [ ] Image job queue tied to music batches
- [ ] Background/thumbnail prompt settings
- [ ] Job actions: retry, clear
- [ ] Live refresh from `/image-jobs`
- [ ] Image sample packs via platform API

## 6.6 Video

- [ ] Video workspace: template selection, inspectors (background, logo, spectrum, particles, text)
- [ ] Effect pack selector and version management
- [ ] Export queue panel (manual + pipeline)
- [ ] **Pipeline export:** spawn `python -m python_app.visualizer.main` per MP3 (same as Electron main)
- [ ] **Preview:** ModernGL Python subprocess (not WebGPU — Electron's WebGPU path is not ported)
- [ ] Local stores: video workspace prefs, audio analysis cache
- [ ] **DesktopVideoPipelineCoordinator:** auto export → YouTube upload enqueue

## 6.7 YouTube

- [ ] Settings tabs: connection per profile, OAuth browser flow, channel/playlist selection
- [ ] Merge upload enqueue and run uploads via platform API
- [ ] Auto-upload after video pipeline export

## 6.8 Progress & Workflow

- [ ] Progress table: polling `/progress`, date filters, active-only mode
- [ ] Workflow timeline: music → image → convert → merge → YouTube steps
- [ ] Local filesystem inspection for MP4/merge state

## 6.9 Settings

- [ ] Full settings workspace matching Electron tabs (profiles, YouTube, Suno, pools, publication)
- [ ] PATCH `/settings` for persistence (no local settings DB)

## 6.10 Effect Packs

- [ ] Installable zip packs with manifest validation
- [ ] Enable/disable, version activate/remove
- [ ] Integrated into video workspace template draft

## 6.11 External Dependencies

- [ ] **platform_api** running on port 8000 (required — same as Electron dev setup)
- [ ] FFmpeg / ffprobe on PATH
- [ ] Python with `python_app.visualizer` available for video export
- [ ] Google OAuth (YouTube — via platform API)

---

# 7. Data & Storage Requirements

## 7.1 No Local Database in Desktop App

Match Electron architecture: **the desktop app does not embed PostgreSQL or SQLite.**

| Data | Where it lives |
|------|----------------|
| Users, profiles, batches, jobs, settings | `platform_api` (PostgreSQL on server) |
| Auth tokens, API base URL | Local encrypted store (`secure_storage.py`) |
| Video workspace prefs | Local JSON (`{userData}/camxora-video-workspace.json` equivalent) |
| Audio analysis cache | Local JSON cache (SHA1-keyed) |
| Effect packs | Local `{userData}/effect-packs/` directory |
| Downloaded music files | Local filesystem via file service |
| Video templates | Read from `python_app/video_templates_local.json` (same as Electron) |

The `database/` folder in `camxora_python/` is reserved for **optional offline cache** or future features — not primary persistence.

## 7.2 Platform API Client

Port the full REST surface from:

- `camxora/src/renderer/src/shared/api/platformEndpoints.ts` (~1,040 lines)
- `camxora/src/renderer/src/shared/api/platformClient.ts`

Use **httpx** with Bearer auth, auto-refresh on 401, Pydantic response models.

## 7.3 Local Store Strategy

| Electron store | Python equivalent |
|----------------|-------------------|
| `camxora-secure-store.json` (safeStorage) | DPAPI-encrypted JSON via `secure_storage.py` |
| `camxora-video-workspace.json` | `QStandardPaths.AppLocalDataLocation` + JSON |
| `video-audio-analysis-cache/` | Same path pattern |
| `effect-packs/` | Same path pattern |

---

# 8. Open Decisions

| # | Decision | Options | Current recommendation |
|---|----------|---------|------------------------|
| 1 | Video preview engine | ModernGL subprocess / Port WebGPU to Qt | **ModernGL subprocess** (matches Electron's Python path) |
| 2 | Merger / Log pages | Wait for Electron / Port from `python_app/` | Wait — Electron has placeholders |
| 3 | Package name | `camxora` / `music-generator` | `camxora` |
| 4 | Manual WebGPU export path | Port frame-capture export / Pipeline only | **Pipeline export only** initially |

---

# 9. Migration Phases

Phases follow **Electron implementation maturity** — port API client first, then workspaces.

## Phase 0 — Foundation ✅ Done

- [x] Project structure under `camxora_python/`
- [x] `pyproject.toml` + `pip install -e .`
- [x] `shared/themes/deep_blue.py`
- [x] `main.py` + `app/bootstrap.py`

**Exit criteria:** App launches with deep blue theme. ✅

## Phase 1 — Core Shell ✅ Done

- [x] `RootWindow` + `AppShellWidget` matching `AppShellLayout`
- [x] Sidebar nav from `shellNavigation.ts` (button-based, no scroll)
- [x] Navigation constants in `shared/constants/navigation.py`
- [x] Placeholder pages for all `/app/*` routes via `app/router.py`
- [x] Page header + status bar

**Exit criteria:** Navigate all Electron routes. ✅

## Phase 2 — Platform Client + Auth ✅ Done

- [x] `shared/services/platform_client.py` (httpx, auto-refresh on 401)
- [x] `shared/services/platform_api.py` — auth subset (`login`, `register`, `refresh`, `logout`, `get_me`, `list_profiles`)
- [x] `shared/services/secure_storage.py` + `dpapi.py`
- [x] `shared/services/session_service.py` — bootstrap routing from `bootstrap.ts`
- [x] Startup splash + `BootstrapWorker`
- [x] Login + register views (`features/account/views/auth_view.py`)
- [x] Onboarding welcome/wizard **stubs** (full wizard deferred)
- [x] Sidebar account summary after login
- [x] Tests: navigation, application, session, login API

**Exit criteria:** Full auth flow against running `platform_api`. ✅

## Phase 3 — Dashboard Page ⏳ Active

**Spec:** [`.docs/pages/03_DASHBOARD_REQUIREMENTS.md`](pages/03_DASHBOARD_REQUIREMENTS.md) (requirements) + [`.docs/pages/03_DASHBOARD_PAGE_SPEC.md`](pages/03_DASHBOARD_PAGE_SPEC.md) (technical)

- [x] Extend `platform_api.py`: dashboard stats, license validate, overview aggregator
- [x] `features/dashboard/views/dashboard_view.py` — first sketch (~70%)
- [ ] 100% checklist: KPI icons, loading `--`, layout parity, activity header, pill badges
- [ ] Dashboard-specific tests (loading, error, bind)

**Exit criteria:** All items in Dashboard spec §12 acceptance checklist.

## Phase 4 — Profile Page

**Spec:** `.docs/pages/04_PROFILE_PAGE_SPEC.md` (to be written)

- [ ] Full gather from `ProfilePage.tsx`
- [ ] 100% build vs spec

## Phase 5 — Workflow Page

**Spec:** `.docs/pages/05_WORKFLOW_PAGE_SPEC.md` (to be written)

## Phase 6 — Progress Page

**Spec:** `.docs/pages/06_PROGRESS_PAGE_SPEC.md` (to be written)

Includes desktop IPC (downloads, manual assets, video runtime) per Electron.

## Phase 7 — Music Workspace

- `MusicWorkspacePage` UI (native PySide6)
- Content pools, batch composer, history
- `DesktopMusicDownloadCoordinator` worker

**Exit criteria:** Create batch, generate, download tracks end-to-end.

## Phase 5 — Image + Settings

- `ImageWorkspacePage` UI
- `SettingsWorkspacePage` (all tabs — largest single screen in Electron)

**Exit criteria:** Image jobs visible; settings PATCH works.

## Phase 6 — Video Workspace + Export

- Video workspace UI (template, inspectors, export queue) — Electron parity
- ModernGL preview + export via ported `python_app/visualizer/` (see [integration spec](pages/09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md))
- `TemplateNormalizer`: Electron template JSON → renderer dict
- Subprocess spawn for `visualizer/main.py` + `ExportGate`
- Local video workspace store + audio analysis cache
- Effect pack registry (Electron contracts)

**Exit criteria:** Pipeline video export succeeds.

## Phase 7 — Automation Coordinators

- `DesktopVideoPipelineCoordinator` (auto export → YouTube enqueue)
- YouTube OAuth flow in settings
- Upload run automation

**Exit criteria:** Full music → video → YouTube pipeline runs unattended.

## Phase 8 — Polish + Deferred

- Merger / Log pages (when Electron implements or port from `python_app/`)
- pytest suite
- Documentation

**Exit criteria:** Production-ready; test suite green.

---

# 10. Non-Functional Requirements

## 10.1 Performance

- Lazy-load feature pages
- Never block the UI thread
- Background work via `QThread`, `QThreadPool`, or `threading` + `UiBus.ui_invoke`
- Page-gated timers (no refresh when page not visible)
- Cache expensive resources where source app already does

## 10.2 Error Handling

- Log all errors (Loguru)
- User-friendly `QMessageBox` for recoverable failures
- No silent exception swallowing
- Graceful degradation where source app already supports it

## 10.3 Code Quality

- PEP 8, type hints on public APIs
- Docstrings on public modules/classes/functions
- Single responsibility per file
- Prefer composition over inheritance
- Reuse shared widgets — no duplicated UI code

## 10.4 Testing

- Port test scenarios from Electron Vitest suite where applicable (logic/API)
- pytest-qt for widget smoke tests
- Integration tests against running `platform_api`

---

# 11. Dependencies (Full Pin List)

Derived from `python_app/pyproject.toml` plus undeclared runtime deps:

```text
# Core
PySide6>=6.7.0
pydantic>=2.0
loguru
sqlalchemy>=2.0
httpx
psutil

# Database (Phase 2 — if PostgreSQL)
psycopg2-binary

# Media / GPU
moderngl
numpy
pillow
opencv-python
pygame
librosa
glfw

# YouTube / Google
google-auth
google-auth-oauthlib
google-api-python-client

# Dev
pytest
pytest-qt
hypothesis
ruff
mypy
```

---

# 12. Acceptance Criteria (Overall Project)

The migration is complete when:

1. All functional requirements in §6 match **camxora Electron** behavior
2. UI uses native PySide6 + deep blue QSS
3. All data flows through **platform_api** (no local DB in desktop app)
4. Video export works via Python visualizer subprocess
5. Background coordinators (download, auto-video, YouTube) run correctly
6. Code is production-ready

---

# 13. References

| Document / path | Purpose |
|-----------------|---------|
| `camxora_python/.docs/00_AI_SYSTEM_PROMPT.md` | Master development prompt |
| `camxora_python/.docs/README.md` | Project vision and doc index |
| `camxora_python/.docs/01_PROJECT_REQUIREMENTS.md` | Full requirements + phase plan |
| `camxora_python/.docs/02_IMPLEMENTATION_STATUS.md` | Live progress tracker |
| `camxora_python/.docs/pages/00_PAGE_BY_PAGE_STRATEGY.md` | **Page-by-page migration strategy** |
| `camxora_python/.docs/pages/03_DASHBOARD_REQUIREMENTS.md` | **Dashboard requirements (build contract)** |
| `camxora_python/.docs/pages/03_DASHBOARD_PAGE_SPEC.md` | Dashboard technical spec + gap notes |
| **`camxora/src/renderer/`** | **Primary source — UX, features, API calls** |
| **`camxora/src/main/` + `preload/`** | Desktop services, IPC, subprocess spawn |
| **`platform_api/`** | Backend REST API, business logic, database |
| `camxora/docs/` | PRD, technical docs, feature flow specs |
| `python_app/visualizer/` | GPU export subprocess (spawn reference only) |
| `python_app/video_templates_local.json` | Video template catalog |

---

# 14. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-07-07 | Initial requirements from planning discussion |
| 1.0.2 | 2026-07-07 | Project root set to `camxora_python/`; flat package layout |
| **2.0.0** | **2026-07-07** | **Source changed to `camxora/` Electron; API-first architecture; no local DB** |
| **2.2.0** | **2026-07-07** | **Page-by-page phases; Dashboard spec; split Phase 3–6 per shell page** |
| **2.1.0** | **2026-07-07** | **Phases 0–2 marked complete; Phase 3 detailed; functional checklist updated** |
