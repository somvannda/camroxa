# Export crash: "FFmpeg pipe closed unexpectedly: (OS Error: [Errno 22] Invalid argument)"

**Date:** 2026-11-04
**Status:** fixed

## Summary

GPU export could abort near the end with a PyInstaller "Unhandled exception in script"
dialog:

```
File "visualizer\encode_pipeline.py", line 206, in _writer_loop
OSError: [Errno 22] Invalid argument
RuntimeError: FFmpeg pipe closed unexpectedly: (OS Error: [Errno 22] Invalid argument)
```

The message was empty of any ffmpeg stderr output because **ffmpeg had already exited
successfully**. `-shortest` made the *audio* track decide when the output ends, so ffmpeg
stopped (exit 0, empty stderr) at the audio tail while the render loop / encode queue was
still writing frames. The next `stdin.write()` hit a dead pipe. Windows reports a dead
child pipe as `EINVAL (22)` instead of `EPIPE (32)`, which is why the error looked like an
"invalid argument" bug rather than a broken pipe.

## Reproduction (ffmpeg 8.0.1, 3.0 s mp3, 60 fps rawvideo pipe)

| command | frames pushed | frames accepted | exit | stderr |
|---|---|---|---|---|
| with `-shortest` | 180 (= audio length) | 180 | 0 | empty |
| with `-shortest` | 240 (> audio length) | 199 | 0 | empty → **write fails** |
| without `-shortest` | 240 | 240 | 0 | empty |

Writing to the stdin of an already-exited child on Windows:

```
OSError errno=22 winerror=None msg=[Errno 22] Invalid argument
```

## Root cause

1. `visualizer/gpu_render.py` `_start_ffmpeg()` passed `-shortest` on the rawvideo pipe
   path. The video length is defined by `ceil(audio_duration * fps)` from the analyzer, so
   the audio track must not be able to end the encode.
2. `PipelinedEncodeWriter` had no encoder-liveness check and treated every `OSError` on
   `stdin.write()` as "pipe closed unexpectedly", even when the encoder had exited 0.
3. Nothing cleaned up on failure: ffmpeg kept running (output file locked, process leak in
   daemon/in-process mode), the stderr log handle stayed open, and the
   `ffmpeg_error_*.log` was never deleted on success either.
4. The one-shot visualizer subprocess had no failure handler, so a frozen build showed the
   raw PyInstaller traceback dialog instead of a message in the export progress view.

## Fix

- **No `-shortest` on the rawvideo pipe** (`gpu_render._start_ffmpeg`, `main.py` CPU path).
  stdin EOF defines the video end; the audio keeps its own length. This removes the race
  entirely instead of hiding it.
- **Encoder liveness + exit classification** (`encode_pipeline.py`):
  - `poll()` before each write; `is_pipe_closed_error()` recognises `EPIPE` **and**
    Windows `EINVAL`.
  - exit 0 → graceful stop, frames counted as dropped, `finish()` does not raise.
  - non-zero exit → `FFmpeg exited (code N) before the export finished (x/y frames
    written): <stderr tail> [stderr log: …]`.
  - a stuck writer now terminates ffmpeg instead of hanging `finish()`/`enc.wait()`.
  - `stats()` gains `framesDropped` / `encoderExitedEarly`; gpu_render emits a `warning`
    MG_EVENT when frames were dropped so a short MP4 is never silent.
- **Cleanup** (`gpu_render.py`): encoders are tracked per export; `run_gpu_render()`
  aborts them if the render raises, so daemon/in-process failures no longer leak ffmpeg.
  The stderr log is deleted on success and kept (path in the error) on failure.
- **No more raw crash dialog** (`main.py`): export exceptions are logged to
  `<logs>/export-crash.log` and emitted as a `failed` MG_EVENT, so the ExportJob shows a
  real message and returns exit code 2.

## Files touched

- `camxora_python/visualizer/encode_pipeline.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/main.py`
- `camxora_python/tests/test_encode_pipeline.py`

## Tests

```powershell
pytest camxora_python/tests/test_encode_pipeline.py camxora_python/tests/test_export_cancel.py `
       camxora_python/tests/test_export_coordinator.py camxora_python/tests/test_in_process_export.py `
       camxora_python/tests/test_native_encode_writer.py camxora_python/tests/test_export_readback.py -q
```

85 passed. New regression tests cover: Windows `EINVAL` classification, clean encoder exit
(no crash), non-zero exit reporting, stuck-writer termination, and "the pipe command has no
`-shortest`".

## Follow-ups

- `visualizer/native_encode_writer.py` duplicates the queue/writer lifecycle; share a base
  class so both paths get the same exit handling.
- `studio/export/ffmpeg_export.py` still passes `-shortest` with a rawvideo pipe (it raises
  `ExportError` instead of crashing, but can still truncate the tail).
- `analyzer.duration_sec` (decoded length) vs ffprobe header duration can differ by
  seconds for some MP3s; consider logging both at export start.
