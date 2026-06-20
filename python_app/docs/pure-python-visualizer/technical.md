## Pure Python: Visualizer Migration - Technical

### Current State (Verified)
- Python app imports `visualizer` directly:
  - [python_app/main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L24-L29)
  - [components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py#L11-L15)
- Export subprocess runs:
  - [video_export.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/video_export.py#L54-L85)
  - `sys.executable -m visualizer.main ...`
- `visualizer/**` uses package-relative imports internally, so it can be moved with minimal change.

### Target State
- `visualizer/` becomes `python_app/visualizer/`.
- Import updates:
  - `python_app/main.py`: `from visualizer...` → `from .visualizer...`
  - `python_app/views/components.py`: `from visualizer...` → `from ..visualizer...`
- Export subprocess updated:
  - `-m visualizer.main` → `-m python_app.visualizer.main`

### Risks
- If any runtime code still imports `visualizer.*` by the old name, imports will fail after the move.
- Subprocess `cwd` must remain repo root so `python_app` is importable.

### Verification
- `python -m compileall -q python_app`
- `python -c "import python_app.main"`
- `python -c "import python_app.visualizer.main"`
