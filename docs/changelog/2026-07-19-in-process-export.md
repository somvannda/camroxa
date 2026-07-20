# REQ-2.2 in-process export from preview GL

**Date:** 2026-07-19  
**Status:** implemented (local)

## Summary

Manual Video tab export can run in-process on a shared OpenGL context when `CAMXORA_INPROCESS_EXPORT=1`, reusing the warm preview session’s audio analyzer and skipping the visualizer subprocess. Subprocess export (via daemon or one-shot) remains the default and the fallback when the flag is off, preview is not warm, or in-process fails (non-zero exit or exception).

## Product impact

**Before:** Every manual export spawned a cold subprocess and re-ran audio analysis unless disk cache hit.  
**After:** With the env flag, export for the currently loaded preview track reuses preview GL sharing + analyzer; preview shows an “Exporting…” overlay while the worker thread encodes via the existing NV12 pipelined ffmpeg path.

## Technical impact

- New `features/video/services/in_process_export.py` — env flag, preview match, `InProcessExportSession`
- `visualizer/gpu_render.run_gpu_render()` — optional shared context, event callback, existing analyzer, cancel hooks
- `features/video/workers/manual_export_worker.py` — backend routing + subprocess fallback
- `visualizer/preview_widget.py` — export overlay
- `features/video/widgets/stage_panel.py` — `preview_widget()` accessor
- `features/video/views/video_view.py` — passes preview into manual export worker

## Files touched

- `camxora_python/features/video/services/in_process_export.py` — new
- `camxora_python/features/video/workers/manual_export_worker.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/widgets/stage_panel.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/tests/test_in_process_export.py` — new

## Migration / deploy

Optional env (default off):

| Variable | Default | Effect |
|----------|---------|--------|
| `CAMXORA_INPROCESS_EXPORT` | `0` | `1` = try in-process manual export when preview matches MP3/template/assets |

## Tests

```powershell
pytest camxora_python/tests/test_in_process_export.py camxora_python/tests/test_encode_pipeline.py -q
```

Full suite: run existing camxora_python tests (29+).

## Follow-ups

- REQ-2.5 ExportCoordinator: unify pipeline + manual backend selection
- Reuse compiled preview shaders at export resolution (avoid re-compile in shared context)
- Golden frame parity sign-off before default-on in production
