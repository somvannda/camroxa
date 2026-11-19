# Page Index

> Part of the Camxora Desktop (Electron) planning pack.
> Release target: **Camxora Desktop 2.0.0**. Vizzy is the only video engine; the automation
> pipeline is part of 2.0.0.

| Doc | Page | Route | Source of truth | Phase |
|---|---|---|---|---|
| [`01-LOGIN.md`](01-LOGIN.md) | Login, auth, onboarding, update gate | `/auth`, `/onboarding` | `camxora_python/features/account`, `app/root_window.py`, `shared/services/session_service.py` | P1 |
| [`02-DASHBOARD.md`](02-DASHBOARD.md) | Dashboard | `/app/home` | `camxora_python/features/dashboard`, `03_DASHBOARD_REQUIREMENTS.md` | P2 |
| [`03-PROFILE.md`](03-PROFILE.md) | Profile | `/app/profile` | `camxora_python/features/profile`, `04_PROFILE_REQUIREMENTS.md` | P2 |
| [`04-PROGRESS.md`](04-PROGRESS.md) | Progress | `/app/progress` | `camxora_python/features/progress`, `06_PROGRESS_REQUIREMENTS.md` | P3 |
| [`05-MUSIC.md`](05-MUSIC.md) | Music | `/app/music` | `camxora_python/features/music`, `07_MUSIC_REQUIREMENTS.md` | P4 |
| [`06-IMAGE.md`](06-IMAGE.md) | Image | `/app/image` | `camxora_python/features/image`, `08_IMAGE_REQUIREMENTS.md` | P5 |
| [`07-VIZZY.md`](07-VIZZY.md) | Vizzy + pipeline | `/app/vizzy` | `G:\Developments\Rea\editor` + `docs/UI-PARITY.md` + [`../09-PIPELINE-AUTOMATION.md`](../09-PIPELINE-AUTOMATION.md) | P7 |
| [`08-MARKETPLACE.md`](08-MARKETPLACE.md) | Marketplace | `/app/marketplace` | `camxora_python/features/marketplace` | P6 |
| [`09-SETTINGS.md`](09-SETTINGS.md) | Settings | `/app/settings` | `camxora_python/features/settings` | P2/P8 |
| [`10-SHELL-AND-SERVICES.md`](10-SHELL-AND-SERVICES.md) | Shell, auth/session, updates, coordinators, diagnostics | global | `app/application.py`, `app/root_window.py`, `shared/services` | P0/P1 |

## Priority key

| Key | Meaning |
|---|---|
| `P0` | Required for the page to be considered complete |
| `P1` | Required for the 2.0.0 release but can land after the page's first pass |
| `P2` | Nice-to-have / follow-up; explicitly deferred |

## Feature ID prefixes

| Prefix | Area |
|---|---|
| `SH-` | Shell and services |
| `LG-` | Login/auth/onboarding |
| `DB-` | Dashboard |
| `PR-` | Profile |
| `PG-` | Progress |
| `MU-` | Music |
| `IM-` | Image |
| `VZ-` | Vizzy |
| `MK-` | Marketplace |
| `ST-` | Settings |
| `PL-` | Pipeline automation |
| `QA-` | Cross-cutting QA |
| `PK-` | Packaging/release |

## Page completion rule

A page is complete only when:

- every `P0` feature is `☑`;
- loading, empty, error and stale states are verified;
- the page's acceptance tests in [`../04-QA-ACCEPTANCE.md`](../04-QA-ACCEPTANCE.md) pass;
- the visual baseline is approved;
- the page appears in [`../07-TRACEABILITY.md`](../07-TRACEABILITY.md) with no orphan features.
