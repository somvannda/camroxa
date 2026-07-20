# REQ-2.4 pipelined encode writer thread

**Date:** 2026-07-19  
**Status:** implemented (local)

## Summary

Decouples GPU export frame submission from ffmpeg stdin writes using a bounded queue (2–3 frames) and a dedicated writer thread. Render loop no longer blocks on slow NVENC ingest; back-pressure applies when the queue fills. Disable with `CAMXORA_PIPELINED_ENCODE=0` for synchronous writes.

## Product impact

**Before:** Each exported frame could stall the render loop while ffmpeg consumed raw/NV12 pipe data.  
**After:** Render submits frames to a pipelined writer; export throughput improves when encode ingest lags GPU readback. Cancel still terminates the ffmpeg subprocess from the export job.

## Technical impact

- New `visualizer/encode_pipeline.py` — `PipelinedEncodeWriter`, `pipelined_encode_enabled()`, `stats()` with p95 block times
- `gpu_render.run_gpu_render()` — uses pipelined writer by default; optional `CAMXORA_ENCODE_METRICS=1` emits `encodePipeMetrics` on final MG_EVENT
- Unit tests in `tests/test_encode_pipeline.py` (no GPU)

## Files touched

- `camxora_python/visualizer/encode_pipeline.py` — new
- `camxora_python/visualizer/gpu_render.py` — wire pipelined writer
- `camxora_python/tests/test_encode_pipeline.py` — new

## Migration / deploy

None. Optional env:

| Variable | Default | Effect |
|----------|---------|--------|
| `CAMXORA_PIPELINED_ENCODE` | `1` | `0` = sync stdin write (legacy) |
| `CAMXORA_ENCODE_METRICS` | off | `1` = log p95 submit/stdin block ms in MG_EVENT |

## Tests

```powershell
pytest camxora_python/tests/test_encode_pipeline.py camxora_python/tests/test_frame_integrator.py camxora_python/tests/test_export_golden_frames.py camxora_python/tests/test_export_readback.py -q
```

29 passed (local).

## Follow-ups

- REQ-2.2 in-process export should call `pipe_writer.cancel()` on coordinator cancel
- REQ-3.3 benchmark JSON: ingest `encodePipeMetrics` from MG_EVENT stream
