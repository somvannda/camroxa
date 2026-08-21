# Camxora Product Scope

**Status:** Active policy for feature specs and implementation planning.

This document defines which codebases are **in scope** for new work versus **excluded** legacy trees.

---

## In scope

| Surface | Path | Role |
|---------|------|------|
| **Desktop app (primary)** | `camxora_python/` | Main PySide6 desktop client — music, video, settings, batch automation |
| **Platform API** | `platform_api/` | Backend: generation, billing, streaming upload, image jobs, admin APIs |
| **Admin portal** | `admin_portal/` | Internal ops: routing, sample packs, streaming catalog, marketplace |
| **User portal** | `user_portal/` | Customer account, plan, wallet, channel management |
| **Music web** | `music_web/` | Public streaming site (`music.camxora.com`) |
| **Website** | `website/` | Marketing / landing (when a feature touches public web) |
| **Deploy scripts** | `scripts/deploy/` | Sandbox/production sync, probes, migrations |

**Desktop policy:** Treat **`camxora_python` as the only desktop client** for new features, UI changes, and QA. Release docs: [`DESKTOP_RELEASE.md`](./DESKTOP_RELEASE.md).

**Integration model:** `camxora_python` talks to **`platform_api`**. Portals and `music_web` are separate frontends on the same API. Admin workflows (uploads, catalog, routing) go through **`admin_portal` → `platform_api`**.

**Changelogs:** Each surface has its own release log. See [`CHANGELOG_GUIDE.md`](./CHANGELOG_GUIDE.md).

---

## Out of scope (excluded)

| Surface | Path | Notes |
|---------|------|-------|
| **Electron app** | `camxora/` | Legacy desktop — **no new features, no parity work, no cleanup PRs** unless explicitly revived |
| **Legacy Python app** | `python_app/` | Older PySide6 tree — **excluded**; do not port features or maintain sample-pack / music UI here |

Do not add “Electron parity” or `python_app` parity items to feature specs. If legacy code still exists in the repo, it may remain untouched until a separate archival decision.

---

## How to use this in specs

When writing or updating feature docs under `docs/`:

1. List **camxora_python** for desktop UI/workers/settings.
2. List **platform_api** for backend/API/migrations.
3. List **admin_portal**, **user_portal**, **music_web** when the feature has admin, account, or public-web surfaces.
4. Do **not** schedule work under `camxora/` or `python_app/` unless the user explicitly overrides this policy.

Feature docs that follow this policy:

- [`AI_STRUCTURE_FREE_LYRICS.md`](./AI_STRUCTURE_FREE_LYRICS.md)
- [`AI_STRUCTURE_FREE_PROVIDER_PROBE.md`](./AI_STRUCTURE_FREE_PROVIDER_PROBE.md)
- [`STREAMING_CATALOG_ENHANCEMENT.md`](./STREAMING_CATALOG_ENHANCEMENT.md)
- [`PROTECTED_PLAYBACK_FAST_START.md`](./PROTECTED_PLAYBACK_FAST_START.md)
- [`SAMPLE_PACK_VPS_MIGRATION.md`](./SAMPLE_PACK_VPS_MIGRATION.md)
