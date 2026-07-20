# Desktop release (camxora_python)

Build **separate installers** per environment. End users cannot switch API URLs in Settings on release builds.

## Versioning

| Source | Location |
|--------|----------|
| App version | `camxora_python/pyproject.toml` → `[project].version` |
| Changelog | `CHANGELOG.md` (repo root) |
| Git tag | `v0.2.0`, `v0.2.1-sandbox`, etc. |

Before each release:

1. Bump `pyproject.toml` version
2. Move `[Unreleased]` items in `CHANGELOG.md` under the new version + date
3. Commit: `release: desktop v0.2.0 sandbox`
4. Tag: `git tag -a v0.2.0 -m "Desktop 0.2.0 sandbox"`
5. Push tag when ready: `git push origin v0.2.0`

## Sandbox build (Windows)

Prerequisites on the **build machine**: Python 3.11+, Inno Setup 6 (optional, for Setup.exe), network for first-time FFmpeg/VC++ download.

```powershell
cd camxora_python
.\scripts\build-desktop.ps1 -Environment sandbox -BuildInno
```

This:

1. Downloads bundled **FFmpeg** + **VC++ redistributable** into `vendor/` (skipped when already cached)
2. Builds `dist/Camxora/Camxora.exe` with FFmpeg at `dist/Camxora/ffmpeg/`
3. (With `-BuildInno`) compiles `CamxoraSetup-<version>.exe` which silently installs VC++ during setup

### Faster rebuilds

Most rebuild time used to come from three avoidable steps: full `pip install` every run, wiping PyInstaller’s `build/` cache, and `collect_all()` on huge packages (numpy/OpenGL/…). The script now:

- Skips `pip` when deps already import (use `-ForceInstall` to refresh)
- Skips FFmpeg/VC++ download when `vendor/` is populated
- Keeps `build/` between runs (pass `-Clean` only after packaging bugs)
- Collects native libs/data selectively instead of `collect_all` on the whole GPU stack

Typical iterative rebuild:

```powershell
.\scripts\build-desktop.ps1 -Environment sandbox -BuildInno
```

First-time / broken package / dependency bump:

```powershell
.\scripts\build-desktop.ps1 -Environment sandbox -BuildInno -ForceInstall -Clean
```

Phase timings (`=== … ===` / `--- … done in Ns ---`) print during the build so you can see whether time is in pip, PyInstaller, or Inno.

End users only run the Setup.exe — no pip, no manual FFmpeg browse for the happy path.

Default media folders are auto-created under `%LOCALAPPDATA%\Camxora\Media\` and linked in Preferences (still editable).

Baked values (from `.env.sandbox.example`):

```
CAMXORA_BUILD_ENV=sandbox
CAMXORA_API_BASE_URL=https://api.sandbox.camxora.com/api/v1
CAMXORA_PORTAL_BASE_URL=https://app.sandbox.camxora.com
```

## Who installs what?

| Audience | How they get GPU preview |
|----------|--------------------------|
| **End users** | Already inside `Camxora.exe` / `dist/Camxora/` — **never run pip** |
| **Developers** | `pip install -e .` (GPU libs are now core dependencies) |
| **Build machine** | `scripts/build-desktop.ps1` installs deps, fails if GPU imports are missing, then PyInstaller bundles them |

If a shipped installer still shows “preview unavailable”, that is a packaging bug or a GPU/driver issue on the PC — not something the user fixes with pip.

The build bundles:

| Asset | Location in `dist/Camxora/` |
|-------|-----------------------------|
| App logo + window icons | `_internal/resources/` |
| Windows exe icon | baked into `Camxora.exe` + `resources/app.ico` |
| Factory video templates | `_internal/data/video_templates_local.json` |
| Sandbox/prod API env | `.env.sandbox` / `.env.production` next to exe |
| SSL CA certs | `_internal/.../certifi/cacert.pem` |
| GLFW native DLL | `_internal/.../glfw3.dll` |
| All lazy feature pages + visualizer | collected via `collect_submodules` |

`scripts/verify-desktop-dist.py` runs automatically after build and fails if any of the above are missing.

Ship the entire `dist/Camxora/` folder (or zip it) to testers — not `Camxora.exe` alone.

## Production build (later)

```powershell
cd camxora_python
copy .env.production.example .env.production
.\scripts\build-desktop.ps1 -Environment production
```

Uses `https://api.camxora.com/api/v1`. Footer **does not** show Sandbox/Local API badge.

## Footer API badge

| Build env | Footer badge |
|-----------|----------------|
| `development` + localhost | **Local API** (tooltip = full URL) |
| `development` + remote | **Dev API** |
| `sandbox` | **Sandbox API** |
| `production` | hidden |

## Local development

```powershell
cd camxora_python
$env:CAMXORA_BUILD_ENV = "development"
python main.py
```

Or create `.env` with `CAMXORA_API_BASE_URL=http://localhost:8000/api/v1`.

## Verify sandbox installer

1. Run `Camxora.exe` from `dist/Camxora/`
2. Footer shows **Sandbox API** (hover for URL)
3. Login works against sandbox portal users
4. Settings → API URL field is locked (no edit) on sandbox/production builds
