# CAMXORA — Project Rules

## Canonical checkout (mandatory)
- `G:\Developments\Projects\Camxora` is the **canonical `main` checkout**. It must stay on `main`, clean, and contain the latest merged code.
- Feature work happens on short-lived branches. Use a worktree when parallel agents share the repo; never treat a worktree as the long-lived source of truth.
- **After every merge**, clean up: delete the merged branch, remove only worktrees that are clean and fully merged, run `git worktree prune`, then sync the main checkout with `git switch main && git pull --ff-only`.
- Never remove a worktree that has uncommitted or unpushed work. Check `git status` and `git log origin/main..HEAD` first.
- Do not leave stale `*-apex`, `*-dev`, or temporary worktrees behind after their branch is merged.

## Shipping / multi-agent (mandatory)
- One task → one git branch (prefer worktrees when parallel agents share this repo).
- Commit / push / merge / production deploy only when the user explicitly asks.
- Do not ship unrelated dirty work: path-scope commits and file-scoped production hotfixes when the tree is mixed.
- Full rules: `.cursor/rules/branch-isolation-and-ship-gates.mdc` and `.cursor/rules/sandbox-first-deploy.mdc`.

## Session & Git Workflow (mandatory)
- One commit = one logical change. **Commit before switching tasks** — never leave work from two tasks in the same uncommitted state.
- Start each session from a clean `main` on a fresh branch: `git fetch origin && git switch -c <task>/<short-name> origin/main`.
- Commit early and often, even incomplete checkpoints (prefix rough ones `WIP:`) — never wait for a task to be "fully done" before the first commit.
- When a related task/bug arrives mid-session, ask 3 questions and act:
  - **Blocking** the current task → fix it first, in its own small commit.
  - **Small + same code area** → fold in as a separate commit on the same branch (2 commits, not 1).
  - **Big or unrelated** → park it: record as a TODO, finish the current task, commit + push, then start a new branch from `main`.
- End of session: push the branch and **leave the worktree clean** (no uncommitted changes left behind).
- Parallel work: one worktree per active task, **one agent per worktree**. Never run two agents in the same directory/worktree simultaneously.
- Never accumulate uncommitted changes across many worktrees "for later".

## App Identity
- App name: **CAMXORA** (never "AI", "NEXORA AI", or other names)
- Canonical web app: **`camxora.com/`**, Next.js 16 at `localhost:3103`
- Core API: **`musicapi/`**, Fastify 5 + TypeScript at `localhost:4003`
- Platform API: **`platform_api/`**, FastAPI at `localhost:8100`
- Admin console: **`admin_portal/`**, React + Vite at `localhost:5173`
- Database: PostgreSQL, local DB `platform_db` / `sunoapi`; migrations in `platform_api/migrations` and `musicapi/migrations`
- Optional Redis job queue (`QUEUE_DRIVER=redis`)
- Legacy trees (reference only, **not** the active product): `python_app/` + `camxora_python/` (PyQt6 desktop), `music_web/` (Next.js), `camxora/` + `archive/electron-app/` (Electron)
- See [README.md](README.md) and [musicapi/README.md](musicapi/README.md) for the runbook.

## Conventions for the active product
- Web API calls go through the `lib/*-api.ts` helpers and the relative `/api/v3/*` rewrite; never hardcode the backend origin in the browser.
- Core API routes live in `musicapi/src/server.ts`; shared infra in `musicapi/src/`
  (`config.ts`, `db.ts`, `pool.ts`, `jobQueue.ts`) — do not add a second route module.
- Credit **costs belong to the `pricing` table**, edited via the admin console
  (`/admin/pricing`) — never hardcode a price in a route.
- New schema changes ship as a new ordered migration file; never edit an applied migration.

## Legacy design system (Python/Electron only — NOT the active product)

The rules below apply only to the legacy PyQt6 desktop app. Do not apply them to `musicapi/`.

> **Obsolete paths (2026-10):** this section refers to `python_app/` and
> `python_app/design_system/…`, neither of which exists in this checkout. The
> PyQt6 tree that ships here is `camxora_python/`, and it has its own design
> system (e.g. `camxora_python/shared/lib/ui_font.py`). Treat the section below
> as historical reference only — do NOT create `python_app/`, and follow
> `camxora_python/`'s existing conventions instead.

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

### Legacy desktop app conventions
- Views go in `python_app/views/`
- Services go in `python_app/services/`
- UI updates must use `_ui_invoke()` for thread safety
- Network calls run on daemon threads, never on main thread
- Login/register flow: signals → controller → worker thread → UI invoke

### Legacy backend conventions
- Routers go in `platform_api/routers/`
- Services go in `platform_api/services/`
- Repos go in `platform_api/repositories/`
- Domain models in `platform_api/models/domain.py` (dataclasses)
- All endpoints use proper dependency injection via `wire_dependencies.py`
- Error responses use `PlatformAPIError` subclasses with standard JSON envelope

### Legacy admin portal conventions
- Pages go in `admin_portal/src/pages/`
- Hooks go in `admin_portal/src/hooks/`
- Types in `admin_portal/src/types/`
- Use React Query for data fetching
- Use shadcn/ui components (Button, Input, Dialog, Table, etc.)
- Tailwind for styling — no inline styles
