## Electron App Removal (Archive) - Tasks

### Goal
Remove Electron/React/Vite code from the active project root to keep the repo Python-first, while preserving the code in an archive folder for reference.

### Scope
- Archive Electron/React/Vite application code and related build outputs/config.
- Archive legacy Electron-era docs (`docs/`, `requirements/`) out of the active root.
- Keep Python runtime intact: `python_app/**` and `visualizer/**`.

### Out of Scope
- Replacing `visualizer/**` with a new renderer inside `python_app` (separate project).

---

## M1 - Inventory (No changes)
- [ ] Confirm which folders/files are considered Electron-related.
- [ ] Confirm Python still depends on `visualizer/**` for preview/export.

Acceptance
- A written move list exists and is codebase-verified.

---

## M2 - Archive Move (Behavior-preserving for Python)
- [ ] Create `archive/electron-app/`.
- [ ] Move Electron/React/Vite folders into `archive/electron-app/`:
  - `electron/`, `src/`, `public/`, `shared/`
  - `dist/`, `dist-electron/`
- [ ] Move Electron-era docs into `archive/electron-app/`:
  - `docs/`, `requirements/`
- [ ] Move root frontend config files into `archive/electron-app/`:
  - `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig*.json`
  - `tailwind.config.js`, `postcss.config.js`, `eslint.config.js`, `index.html`
  - other root frontend-only artifacts if present

Acceptance
- Python app can still be launched from repo root: `python -m python_app`.
- No Electron folders remain in the active root (only inside `archive/electron-app/`).

---

## M3 - Cleanup + Docs
- [ ] Update root `README.md` to remove Vite template instructions and document Python-first usage.
- [ ] Add an archive note (what was moved, where, and why).
- [ ] Add a DEVELOPMENT_LOG entry.

Acceptance
- README explains how to run the Python app and what was archived.

---

## M4 - Verification
- [ ] `python -m compileall -q python_app visualizer`
- [ ] `python -c "import python_app.main"`

Acceptance
- Compile/import checks succeed.
