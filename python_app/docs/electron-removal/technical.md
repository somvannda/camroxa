## Electron App Removal (Archive) - Technical

### Current State (Verified)
- Python app entrypoint: [python_app/main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py) (also supports `python -m python_app` via `python_app/__main__.py`)
- Python renderer dependency: `visualizer/**`
  - `python_app/main.py` imports `visualizer.gpu_render` and `visualizer.audio`.
  - `python_app/services/video_export.py` runs `python -m visualizer.main` as a subprocess.

### Decision
- Keep `visualizer/**` in the active root for now (required by Python).
- Archive Electron/React/Vite code into `archive/electron-app/`.

### Files/Folders to Archive
- App code:
  - `electron/`
  - `src/`
  - `public/`
  - `shared/`
- Build outputs:
  - `dist/`
  - `dist-electron/`
- Electron-era docs:
  - `docs/`
  - `requirements/`
- Frontend tooling/config:
  - `package.json`, `package-lock.json`
  - `vite.config.ts`
  - `tsconfig*.json`
  - `tailwind.config.js`, `postcss.config.js`, `eslint.config.js`
  - `index.html`

### Risks
- Removing or archiving `visualizer/**` would break Python preview/export; defer until a Python-native replacement exists.
- Moving large folders should not change Python behavior, but ensure the working directory remains repo root.

### Verification
- `python -m compileall -q python_app visualizer`
- `python -c "import python_app.main"`
