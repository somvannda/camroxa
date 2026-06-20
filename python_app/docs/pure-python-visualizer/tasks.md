## Pure Python: Visualizer Migration - Tasks

### Goal
Make the repository 100% Python by moving `visualizer/**` into `python_app/**` and removing the root-level `visualizer/` folder, while preserving preview/export behavior.

### Scope
- Move `visualizer/` → `python_app/visualizer/` (keep same code, minimal churn).
- Update Python app imports and subprocess module path.
- Update documentation and logs.

### Out of Scope
- Rewriting the renderer architecture or changing rendering output.

---

## M1 - Inventory (Verified)
- [x] Identify python_app imports of `visualizer.*`
- [x] Identify subprocess call using `python -m visualizer.main`

---

## M2 - Migration (Minimal Churn)
- [ ] Move folder:
  - `visualizer/` → `python_app/visualizer/`
- [ ] Update imports:
  - `python_app/main.py`: `visualizer.*` → `.visualizer.*`
  - `python_app/views/components.py`: `visualizer.*` → `..visualizer.*`
  - `python_app/services/video_export.py`: `visualizer.main` → `python_app.visualizer.main`
  - `python_app/tools/*`: `visualizer.*` → `python_app.visualizer.*`
- [ ] Ensure `python_app/visualizer/__init__.py` and `python_app/visualizer/objects/__init__.py` remain valid after the move.

Acceptance
- No `visualizer/` folder exists at repo root.
- App still imports and starts from repo root.

---

## M3 - Verification
- [ ] `python -m compileall -q python_app`
- [ ] `python -c "import python_app.main"`
- [ ] `python -c "import python_app.visualizer.main as vm; print('visualizer import ok')"`

Acceptance
- All checks succeed.

---

## M4 - Documentation
- [ ] Update root `README.md` to reflect the new visualizer location.
- [ ] Add a `DEVELOPMENT_LOG` entry.
