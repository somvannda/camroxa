# Page-by-Page Migration Strategy

> **Last updated:** 2026-07-07  
> **Status:** Active — supersedes the old “Phase 3 = 4 pages at once” plan

---

## Why this change

The first Phase 3 pass wired **Dashboard, Profile, Progress, and Workflow** with live API data, but each page was only a **first sketch** (~60–75% parity). That makes review hard and risks rework.

**New rule:** one shell page = one delivery phase. Gather Electron source → write a detailed spec → implement to **100% acceptance checklist** → only then move on.

---

## Workflow per page

```
1. GATHER   — Read Electron component, hook, tests, API types, backend router
2. SPEC     — Write `.docs/pages/XX_<PAGE>_PAGE_SPEC.md` (this folder)
3. BUILD    — PySide6 view + widgets + workers to match spec exactly
4. VERIFY   — Manual test against live platform_api + automated tests
5. SIGN OFF — Update checklist in spec + `02_IMPLEMENTATION_STATUS.md`
6. NEXT     — Start gather/spec for the next page
```

---

## Page order (shell workspace)

| Phase | Page | Electron source | Spec doc | Build status |
|-------|------|-----------------|----------|--------------|
| **3** | **Dashboard** | `HomePage.tsx` | [`03_DASHBOARD_PAGE_SPEC.md`](03_DASHBOARD_PAGE_SPEC.md) | **In progress** — spec + gap list ready |
| 4 | Profile | `ProfilePage.tsx` | `04_PROFILE_PAGE_SPEC.md` (planned) | Sketch only |
| 5 | Workflow | `WorkflowPage.tsx` | `05_WORKFLOW_PAGE_SPEC.md` (planned) | Sketch only |
| **6** | Progress | `ProgressPage.tsx` | `06_PROGRESS_PAGE_SPEC.md` (planned) | Sketch → **Requirements ready** |
| **7** | **Music** | `MusicWorkspacePage.tsx` | **[07_MUSIC_REQUIREMENTS.md](07_MUSIC_REQUIREMENTS.md)** | **Requirements ready** |
| **8** | **Image** | `ImageWorkspacePage.tsx` | **[08_IMAGE_REQUIREMENTS.md](08_IMAGE_REQUIREMENTS.md)** | **Requirements ready** |
| 9 | Settings | `SettingsPage.tsx` | planned | Placeholder |
| 10 | Video | `VideoPage.tsx` | planned | Placeholder |
| 11+ | Automation, Onboarding wizard, Merger, Log | various | planned | Deferred |

**Note:** Profile is before Workflow/Progress because it shares the same data hook as Dashboard and is simpler (no polling, no desktop IPC).

---

## What “100% complete” means

For each page spec:

1. **Functional parity** — Same API calls, field bindings, fallbacks, and error/loading behavior as Electron
2. **Layout parity** — Same sections, column ratios, table columns, labels (native Qt widgets, not pixel-perfect CSS clone)
3. **Data parity** — Same formatting helpers (numbers, dates, percentages)
4. **No scope creep** — Desktop IPC features belong in that page’s spec only when Electron uses them on that page
5. **Tests** — Unit tests for formatters/models + smoke test for view mount/load/error states
6. **Documentation** — Spec checklist fully checked off

---

## PySide6 conventions (unchanged)

- Native widgets + `shared/themes/deep_blue.py` QSS
- API via `shared/services/platform_api.py` + `QThread` workers
- Page lifecycle via `activate_page()` / `deactivate_page()` in router
- Session hydrated on main thread before workers (Windows DPAPI)

---

## Current codebase vs this strategy

| Page | Python module | Honest status |
|------|---------------|---------------|
| Dashboard | `features/dashboard/views/dashboard_view.py` | ~70% — see Dashboard spec gap list |
| Profile | `features/profile/views/profile_view.py` | ~75% — not spec’d yet |
| Progress | `features/progress/views/progress_view.py` | ~50% — missing IPC, downloads, manual sync |
| Workflow | `features/workflow/views/workflow_view.py` | ~55% — missing video runtime overlay |

**Do not treat Phase 3 as “done” until Dashboard spec checklist is 100%.**

---

## Document index

| File | Purpose |
|------|---------|
| [`README.md`](README.md) | Index of all page specs |
| [`03_DASHBOARD_PAGE_SPEC.md`](03_DASHBOARD_PAGE_SPEC.md) | Full Dashboard gather + acceptance checklist |
| `04_PROFILE_PAGE_SPEC.md` | Created when Profile phase starts |
| `05_WORKFLOW_PAGE_SPEC.md` | Created when Workflow phase starts |
| `06_PROGRESS_PAGE_SPEC.md` | Created when Progress phase starts |
