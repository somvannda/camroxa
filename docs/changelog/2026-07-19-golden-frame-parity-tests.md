# REQ-2.7 golden frame parity tests

**Date:** 2026-07-19  
**Status:** implemented (local GPU verified)

## Summary

Adds automated preview-vs-export PNG parity tests at t=1 s and t=30 s for a low-motion golden fixture. Introduces `render_export_png()` (single-frame export path without ffmpeg) and optional `msaa_samples` / `analysis_fps` on `render_preview_png()` for aligned comparisons.

## Product impact

No user-visible change. Release/pre-release can run golden tests on Windows machines with GPU to catch preview/export drift before enabling in-process export (REQ-2.6).

## Technical impact

- `tests/test_export_golden_frames.py` — RMSE + average-hash comparison, `@pytest.mark.gpu`, skip without GLFW
- `render_export_png()` — reuses export frame loop via `run_gpu_render(single_frame_png=…)`
- `frame_integrator` — optional `wall_time` on shake/vibrate for future deterministic runs
- Baselines under `tests/fixtures/golden_frames/minimal/baselines/` when `CAMXORA_GOLDEN_UPDATE=1`

## Files touched

- `camxora_python/tests/test_export_golden_frames.py` — new
- `camxora_python/tests/fixtures/golden_frames/` — new fixture + README
- `camxora_python/visualizer/gpu_render.py` — `render_export_png`, single-frame export mode
- `camxora_python/visualizer/frame_integrator.py` — `wall_time` optional param
- `camxora_python/pyproject.toml` — `gpu` pytest marker

## Migration / deploy

None. Optional local/CI step:

```powershell
pytest camxora_python/tests/test_export_golden_frames.py -v
```

## Tests

- `pytest tests/test_frame_integrator.py` — 12 passed
- `pytest tests/test_export_golden_frames.py` — 3 passed (GPU machine)

## Follow-ups

- Add `effects` and marketplace template cases (REQ-2.7 spec: 3 templates × 3 timestamps)
- Wire `wall_time=0` in render paths when shake enabled
- Tighten RMSE threshold after REQ-2.1 unifies spectrum/particle draw paths
