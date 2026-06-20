# MusicGenerator (Python App)

This repository is now **Python-first**.

## Run (Python)

From repo root:

```bash
python -m python_app
```

## Configuration

- Create `python_app/.env` by copying `python_app/.env.example` and filling in your local Postgres credentials.

## Renderer Dependency

The Python app includes its renderer under `python_app/visualizer/**` for spectrum preview and GPU export.

## Archived Electron App

The previous Electron/React/Vite app (and its build outputs and legacy docs) has been moved to:

- `archive/electron-app/`
