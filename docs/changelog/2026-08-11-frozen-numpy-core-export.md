# 2026-08-11 — Frozen export: bundle numpy._core

## Summary

Camxora **1.2.4** Manual Export could crash in the frozen installer:

```text
ImportError: numpy._core.multiarray failed to import
```

SciPy 1.17’s compiled extensions import `numpy._core.*`. NumPy 1.26 still
provides that as an on-disk compatibility package, but the PyInstaller
recipe only pulled enough of `numpy.core` — so frozen workers failed during
`visualizer.audio` STFT analysis.

## Changes

- `Camxora.spec`: `collect_all` / submodules for `numpy` and `scipy`, plus
  explicit `numpy._core*` / `scipy.signal*` hiddenimports.
- `visualizer/audio.py`: NumPy-only STFT fallback if SciPy import/STFT fails.
- `verify-desktop-dist.py`: require `_internal/numpy/_core/`.

## Surfaces

- Desktop installer only. Rebuild `CamxoraSetup-1.2.5.exe`.
