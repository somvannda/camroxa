# Changelog guide — all Camxora surfaces

**Audience:** engineers, release owners, support.

This document defines **where changelogs live** for each deployable product surface. Use it whenever you ship user-visible or API-contract changes.

Related:

- [`PRODUCT_SCOPE.md`](./PRODUCT_SCOPE.md) — which codebases are in scope
- [`DESKTOP_DISTRIBUTION.md`](./DESKTOP_DISTRIBUTION.md) — desktop installer publish + download flow only
- [`DESKTOP_RELEASE.md`](./DESKTOP_RELEASE.md) — building and tagging the desktop app

---

## Surfaces at a glance

| # | Surface | Code path | Typical URL | Changelog file |
|---|---------|-----------|-------------|----------------|
| 1 | **User portal** | `user_portal/` | `app.camxora.com` | [`user_portal/CHANGELOG.md`](../user_portal/CHANGELOG.md) |
| 2 | **Music portal** | `music_web/` | `music.camxora.com` | [`music_web/CHANGELOG.md`](../music_web/CHANGELOG.md) |
| 3 | **Admin portal** | `admin_portal/` | admin host | [`admin_portal/CHANGELOG.md`](../admin_portal/CHANGELOG.md) |
| 4 | **Platform API** | `platform_api/` | `/api/v1/...` | [`platform_api/CHANGELOG.md`](../platform_api/CHANGELOG.md) |
| 5 | **Website** | `website/` | `camxora.com` | [`website/CHANGELOG.md`](../website/CHANGELOG.md) |
| 6 | **Desktop app** *(separate)* | `camxora_python/` | installed `.exe` | [`CHANGELOG.md`](../CHANGELOG.md) (repo root) |

**Music portal** is the public streaming product (`music_web/`). Do not confuse it with the user portal (account/billing) or the marketing website.

**Desktop app** (`camxora_python/`) is **not** one of the five web/API surfaces above. It has its own semver release log at the repo root because installers are versioned and distributed separately. It talks to **platform_api** and receives in-app update notifications configured in **admin portal → Software Updates**.

---

## Three documentation layers

Each layer has a different job. Do not merge them into one file.

### 1. Per-surface `CHANGELOG.md` (required on every release)

Each deployable unit above keeps its own [Keep a Changelog](https://keepachangelog.com/) file next to its code.

**When to update:** any release of that surface — sandbox deploy, production deploy, or tagged desktop build.

**Sections:** `Added`, `Changed`, `Fixed`, `Removed`, `Deprecated`, `Security`.

**Rule:** if you changed files under `user_portal/`, add an entry to `user_portal/CHANGELOG.md`. Same for the other paths.

### 2. Implementation changelogs — `docs/changelog/` (engineering)

Cross-cutting or non-trivial work gets a dated engineering note:

`docs/changelog/YYYY-MM-DD-<short-slug>.md`

Required sections: Summary, Product impact, Technical impact, Files touched, Migration/deploy, Tests, Follow-ups. See [`.cursor/rules/implementation-changelog.mdc`](../.cursor/rules/implementation-changelog.mdc).

**When to use:** billing, migrations, multi-surface features, incidents, deploy runbooks. Link the affected per-surface `CHANGELOG.md` entries from the implementation doc.

### 3. Public-facing release notes (customer/marketing)

| Channel | Managed in | Shown to |
|---------|------------|----------|
| Website **/changelog** | Admin → **Blog Posts**, category `Release notes` | Public visitors |
| Website **/download** short notes | Admin → **Software Updates** → release notes field | Download page + desktop push body |
| Desktop semver history | Root `CHANGELOG.md` + `pyproject.toml` version | Release engineers, support |

Blog posts and software-update notes are **editorial**. Per-surface `CHANGELOG.md` files are **technical release logs** for the team.

---

## What belongs in which changelog

| Change type | Primary changelog | Also update |
|-------------|-------------------|-------------|
| User portal UI, onboarding, billing pages | `user_portal/CHANGELOG.md` | `platform_api/` if API changed |
| Music player, browse, search UI | `music_web/CHANGELOG.md` | `platform_api/` if streaming API changed |
| Admin screens, ops tools | `admin_portal/CHANGELOG.md` | `platform_api/` if admin API changed |
| REST/WebSocket routes, migrations, services | `platform_api/CHANGELOG.md` | affected portal changelogs |
| Marketing pages, `/download`, `/blog` | `website/CHANGELOG.md` | `platform_api/` if new public API |
| Desktop UI, workers, packaging | Root `CHANGELOG.md` | `camxora_python/` bump in `pyproject.toml` |
| Deploy script only | `docs/changelog/YYYY-MM-DD-*.md` | surface changelog if deploy includes app changes |

**One feature, multiple surfaces:** add a bullet under `[Unreleased]` in **every** surface you touched, plus one `docs/changelog/` doc if the work is non-trivial.

---

## Desktop distribution vs the five web surfaces

Recent **desktop distribution** work touches several surfaces differently:

| Surface | Role in desktop distribution |
|---------|------------------------------|
| **platform_api** | `GET /api/v1/public/desktop-release`, software-update settings, push notifications |
| **website** | `/download` (installer link), `/changelog` (blog release notes) |
| **user portal** | Links to website `/download` — no separate installer hosting |
| **admin portal** | **Software Updates** + **Blog Posts** — where admins configure releases |
| **music portal** | **Not involved** — streaming catalog is unrelated to desktop installers |
| **camxora_python** | Receives `software_update.available` push; optional force-update gate; silent install |

So: distribution docs describe a **cross-surface workflow**, but each surface still owns its own `CHANGELOG.md`.

---

## Release workflow (checklist)

### Web/API surface (user portal, music portal, admin portal, platform_api, website)

1. Implement and test locally.
2. Append to that surface’s `CHANGELOG.md` under `[Unreleased]`.
3. If migrations or multi-surface: add `docs/changelog/YYYY-MM-DD-<slug>.md`.
4. Deploy the affected directories (see [`DEPLOYMENT_OPERATIONS.md`](./DEPLOYMENT_OPERATIONS.md)).
5. On production deploy, move `[Unreleased]` items to a dated version section in each touched `CHANGELOG.md`.

### Desktop app (`camxora_python`)

1. Follow [`DESKTOP_RELEASE.md`](./DESKTOP_RELEASE.md).
2. Update root `CHANGELOG.md` and `camxora_python/pyproject.toml` version.
3. Build installer, host file, configure **Admin → Software Updates**, **Publish**.
4. Optional: blog post with category **Release notes** for public `/changelog`.

---

## FAQ

**Does the website `/changelog` replace per-surface changelogs?**  
No. `/changelog` is public marketing content from blog posts. Engineers maintain `*/CHANGELOG.md` per surface.

**Does `docs/changelog/` replace per-surface changelogs?**  
No. Implementation docs explain *how* and *why* for complex work. Surface changelogs record *what shipped* in each app.

**We fixed a bug only in platform_api but user portal behavior changed — where do I log?**  
Both `platform_api/CHANGELOG.md` and `user_portal/CHANGELOG.md` (user-visible fix line).

**Music portal had no changes — do I add an empty entry?**  
No. Only update changelogs for surfaces you actually changed.
