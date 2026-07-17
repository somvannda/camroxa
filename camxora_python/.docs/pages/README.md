# Shell Page Specifications

Detailed, page-by-page migration specs for `camxora_python`. Each doc is the **single source of truth** for building that page to 100% Electron/API parity.

## Strategy

Read [`00_PAGE_BY_PAGE_STRATEGY.md`](00_PAGE_BY_PAGE_STRATEGY.md) first.

## Specs

| # | Page | Route | Requirements (build contract) | Technical spec | Status |
|---|------|-------|------------------------------|----------------|--------|
| 03 | Dashboard | `/app/home` | **[03_DASHBOARD_REQUIREMENTS.md](03_DASHBOARD_REQUIREMENTS.md)** | [03_DASHBOARD_PAGE_SPEC.md](03_DASHBOARD_PAGE_SPEC.md) | **✅ Complete** |
| 04 | Profile | `/app/profile` | **[04_PROFILE_REQUIREMENTS.md](04_PROFILE_REQUIREMENTS.md)** | — | **✅ Complete** |
| 05 | Workflow | `/app/workflow` | **[05_WORKFLOW_REQUIREMENTS.md](05_WORKFLOW_REQUIREMENTS.md)** | — | **✅ Complete** |
| 06 | Progress | `/app/progress` | **[06_PROGRESS_REQUIREMENTS.md](06_PROGRESS_REQUIREMENTS.md)** | — | **✅ Complete** |
| 07 | Music | `/app/music` | **[07_MUSIC_REQUIREMENTS.md](07_MUSIC_REQUIREMENTS.md)** | — | **✅ Complete** |
| 08 | Image | `/app/image` | **[08_IMAGE_REQUIREMENTS.md](08_IMAGE_REQUIREMENTS.md)** | — | **✅ Complete** |
| 09 | Video | `/app/video` | **[09_VIDEO_IMPLEMENTATION_PLAN.md](09_VIDEO_IMPLEMENTATION_PLAN.md)** (active) · [Requirements](09_VIDEO_REQUIREMENTS.md) · [Integration](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md) · [Schema](09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md) · [Enterprise](09_VIDEO_ENTERPRISE_ARCHITECTURE.md) | — | **🔨 In progress** |

**Workflow:** Requirements doc first → implement §15 Definition of Done → sign off → next page.

## Related project docs

- [`../01_PROJECT_REQUIREMENTS.md`](../01_PROJECT_REQUIREMENTS.md) — overall requirements
- [`../02_IMPLEMENTATION_STATUS.md`](../02_IMPLEMENTATION_STATUS.md) — live progress tracker
