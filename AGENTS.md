# CAMXORA — Project Rules

## Shipping / multi-agent (mandatory)
- One task → one git branch (prefer worktrees when parallel agents share this repo).
- Commit / push / merge / production deploy only when the user explicitly asks.
- Do not ship unrelated dirty work: path-scope commits and file-scoped production hotfixes when the tree is mixed.
- Full rules: `.cursor/rules/branch-isolation-and-ship-gates.mdc` and `.cursor/rules/sandbox-first-deploy.mdc`.

## App Identity
- App name: **CAMXORA** (never "AI", "NEXORA AI", or other names)
- Desktop music/video studio app with PyQt6 native widget UI
- Backend: FastAPI at `localhost:8000`, PostgreSQL `platform_db`, Redis
- Admin portal: React + TypeScript + Vite + Tailwind + shadcn/ui at `localhost:5173`
- Email: MailHog (`localhost:1025` SMTP / `localhost:8025` web UI)

## Design System Rules (MANDATORY for all UI)

### Must use master template for ALL controls
Every new UI element MUST use the master template factory methods from `python_app/design_system/layouts/master_template.py`. Never create raw `QLabel`, `QPushButton`, `QLineEdit` with inline styles.

**Available controls:**
| Function | Use For | Specs |
|----------|---------|-------|
| `heading_h1()` | Page titles | 24px bold |
| `heading_h2()` | Section titles | 20px bold |
| `heading_h3()` | Sub-section titles | 16px bold |
| `text_body()` | Descriptions, paragraphs | 14px regular, primary color |
| `text_secondary()` | Subtitles, secondary info | 14px regular, muted color |
| `text_muted()` | Captions, timestamps | 12px regular, muted color |
| `text_label()` | Form field labels | 13px medium |
| `text_link()` | Navigation links (QPushButton) | 14px, purple, underline on hover |
| `input_field()` | Text inputs | 48px height, purple border on focus |
| `button_primary()` | Main CTA (submit, confirm) | 48px height, purple gradient |
| `button_secondary()` | Cancel, back | 44px height, transparent + border |
| `button_ghost()` | Inline actions | 36px height, no border |
| `button_danger()` | Destructive actions | 44px height, red |
| `form_group()` | Label + input pair | Returns (label, input) |
| `form_column()` | Form vertical layout | 20px spacing |

### Typography
- **Font family**: Open Sans (variable weight, bundled at `assets/fonts/OpenSans-Variable.ttf`)
- **Never use Segoe UI or other fonts** — always `QFont("Open Sans", size, weight)`
- **Always use `setPixelSize()`** not `setPointSize()` — DPI-independent
- App font set in `bootstrap.py`: `setPixelSize(14)`

### Colors & Theme
- Background: solid `#0a0e27` (no gradient)
- Card backgrounds: `#081028` / `#0c1230`
- Primary/CTA buttons: purple gradient `#7466F1` → `#A259FF`
- Brand gradient: `#4c1d95` → `#7c3aed` → `#a855f7`
- Text primary: from `DEFAULT_DARK_THEME.colors.text_primary`
- Text secondary: from `DEFAULT_DARK_THEME.colors.text_secondary`
- Text muted: from `DEFAULT_DARK_THEME.colors.text_muted`
- Accent: `#7466F1` (secondary_accent from tokens)
- Danger: from `DEFAULT_DARK_THEME.colors.danger`

### Spacing & Layout
- Use `_SPACING` tokens from `python_app/design_system/tokens.py`
- Card padding: 20px horizontal, 16px vertical minimum
- Form spacing: 16-20px between fields
- Button height: 48px (primary), 44px (secondary), 36px (ghost)
- Border radius: 8px (buttons/inputs), 12px (cards), 16px (dialogs)

### Property-Based Styling
- Use `setProperty("uiRole", "...")` for gradient buttons: `"gradientPrimary"`
- QSS generator applies styles based on `uiRole` property
- Never hardcode QSS that duplicates design system styles

### Consistency Checklist (before shipping any UI)
- [ ] All buttons use `button_primary()`, `button_secondary()`, or `button_ghost()`
- [ ] All labels use `heading_*()`, `text_body()`, `text_secondary()`, `text_muted()`, or `text_label()`
- [ ] All inputs use `input_field()`
- [ ] Font is "Open Sans" everywhere, using `setPixelSize()`
- [ ] No raw `QFont("Segoe UI")` or other fonts
- [ ] No inline `setStyleSheet()` on buttons/labels/inputs (use master template or uiRole)
- [ ] Card backgrounds are `#081028` or `#0c1230`
- [ ] Button heights match standard (48/44/36px)

## Desktop App Conventions
- Views go in `python_app/views/`
- Services go in `python_app/services/`
- UI updates must use `_ui_invoke()` for thread safety
- Network calls run on daemon threads, never on main thread
- Login/register flow: signals → controller → worker thread → UI invoke

## Backend Conventions
- Routers go in `platform_api/routers/`
- Services go in `platform_api/services/`
- Repos go in `platform_api/repositories/`
- Domain models in `platform_api/models/domain.py` (dataclasses)
- All endpoints use proper dependency injection via `wire_dependencies.py`
- Error responses use `PlatformAPIError` subclasses with standard JSON envelope

## Admin Portal Conventions
- Pages go in `admin_portal/src/pages/`
- Hooks go in `admin_portal/src/hooks/`
- Types in `admin_portal/src/types/`
- Use React Query for data fetching
- Use shadcn/ui components (Button, Input, Dialog, Table, etc.)
- Tailwind for styling — no inline styles

## Cursor Cloud specific instructions

Scope that runs in the Linux cloud VM is the **web stack**: `platform_api` (FastAPI :8000) + `admin_portal` (Vite :5173) on PostgreSQL + Redis. The desktop app `camxora_python` / legacy `python_app` are **Windows-only** (PySide/PyQt + NVENC) per `docs/MACBOOK_DEV_SETUP.md` and are out of scope here.

### Services & how to start them
- PostgreSQL and Redis are installed as system packages but there is **no systemd/init** in this VM, so they are **not auto-started** on boot. Start them at the beginning of a session if not already running:
  - `sudo pg_ctlcluster 16 main start` (Postgres 16, user `postgres` / password `postgres`, DB `platform_db`)
  - `sudo redis-server --daemonize yes`
  - Verify: `pg_isready` and `redis-cli ping`.
- The Postgres data dir (`platform_db`, applied migrations, seeded admin) persists in the VM snapshot; you normally only need to (re)start the process, not re-create the DB.
- Backend runs in a dedicated venv at `platform_api/.venv` (created by the update script). Run Python/alembic/pytest via `platform_api/.venv/bin/...` with `PYTHONPATH=/workspace`.
- Start both services (from `/workspace`), each in its own long-lived terminal:
  - API: `PYTHONPATH=/workspace platform_api/.venv/bin/python -m uvicorn platform_api.main:app --host 0.0.0.0 --port 8000` (`--reload` optional). On startup the app **auto-runs `alembic upgrade heads`** against `platform_db`.
  - Admin portal: `npm --prefix admin_portal run dev` (Vite on :5173, proxies `/api` → `127.0.0.1:8000`; use `127.0.0.1`, not `localhost`, to match `strictPort`).
- `./start-dev.sh` is macOS-oriented (hard-codes Homebrew/darwin PATHs); prefer the explicit commands above on Linux.
- Config lives in `platform_api/.env` (git-ignored). A working dev `.env` uses `PLATFORM_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/platform_db`, `PLATFORM_REDIS_URL=redis://localhost:6379/0`, `PLATFORM_DEBUG=true`, and `PLATFORM_ENCRYPTION_MASTER_KEY` set to any non-empty string.

### Auth for local testing
- Seed/refresh a local admin: `PYTHONPATH=/workspace PLATFORM_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/platform_db platform_api/.venv/bin/python -m platform_api.scripts.seed_admin`.
- Default seeded admin: `admin@mgfaceless.com` / `112233aB!!@@`. Signup is `invite_only`, so use the seeded admin (or `platform_api/scripts/seed_admin.py`) rather than self-registration.

### Lint / test / build gotchas
- Backend tests: `PYTHONPATH=/workspace platform_api/.venv/bin/pytest tests/` (run from `platform_api/`). The bulk pass, but a set of failures are **pre-existing and environmental**, not regressions: Windows-path tests (e.g. `test_run_directory_planner.py`) fail on Linux, some tests use a stale `Plan(...)` signature, and a few router tests need the app lifespan/DB pool. Judge changes by the tests relevant to your change, not a green full suite.
- Admin portal: `npm --prefix admin_portal test` (vitest) works. **`npm run lint` is broken** — `eslint` is referenced by the script but not declared in `devDependencies`, so it errors with "eslint: not found". Don't treat that as your regression.
- External AI providers (Suno/Fal/SLAI/DeepSeek) have no keys in dev, so `GET /health` reports `degraded` and provider pools show `critical` — this is expected, the DB check is what matters (`database: true`).
