# Native Encode Bridge — real NVENC (CPU NV12 upload)

**Date:** 2026-07-20  
**Status:** implemented (local build + smoke verified on NVIDIA GPU)

## Summary

Replaced the REQ-3.5 NativeEncodeBridge stub with a working NVENC H.264 path on Windows. The DLL creates a D3D11 device, loads `nvEncodeAPI64.dll` at runtime, converts RGBA→NV12 on the CPU (BT.601 limited), and writes Annex-B elementary bitstream. GL→D3D zero-copy remains a follow-up; Python remuxes with audio via ffmpeg `-c:v copy`.

**Performance fix (same day):** API v2 adds `camxora_eb_submit_nv12` so Python can pack with OpenCV on a writer thread and skip the naive C++ RGBA loop. `NativeEncodeWriter` is now pipelined (bounded queue + `camxora-native-encode` thread). `CAMXORA_NATIVE_ENCODE=1` again selects the native path for export.

## Product impact

- **Before:** `CAMXORA_NATIVE_ENCODE=1` loaded a scaffold DLL; `create`/`submit`/`finish` returned not-implemented and export stayed on the ffmpeg pipe. After first NVENC land, sync RGBA→NV12 on the render thread was ~143s/track vs ~30s pipe, so export was gated behind `CAMXORA_NATIVE_ENCODE_EXPORT`.
- **After:** With an NVIDIA driver that exposes NVENC, `CAMXORA_NATIVE_ENCODE=1` uses pipelined OpenCV NV12 + `submit_nv12` (API v2). Machines without NVENC still fall back cleanly (`probe` → `no-nvenc` / create errors → pipe).

## Technical impact

- Runtime dynamic NVENC API (`NvEncodeAPICreateInstance`); no link to `nvEncodeAPI.lib`.
- Vendored header only (`third_party/nvidia/nvEncodeAPI.h` from FFmpeg nv-codec-headers **n13.0.19.1** / API 13.0 — must be ≤ driver `NvEncodeAPIGetMaxSupportedVersion`); no full Video Codec SDK install required.
- Input: `nvEncCreateInputBuffer` + NV12 CPU upload (CUDA-free).
- **API v2:** `camxora_eb_submit_nv12(session, nv12, y_stride)` — memcpy Y/UV into locked input buffer (respects NVENC pitch), then EncodePicture. `submit_rgba` still works.
- Output: Annex-B H.264 to `output_path` (prefer `.h264`).
- New error codes: `CAMXORA_EB_ERR_ENCODE` (4), `CAMXORA_EB_ERR_IO` (5).
- Stub escape hatch: `CAMXORA_NATIVE_ENCODE_STUB=1`.
- Python: pipelined `NativeEncodeWriter` (pack on writer thread via `PipeFramePacker(..., "nv12")`); `NativeEncodeSession.submit_nv12`; `try_native_encode_video(...)` helper.

## Files touched

- `camxora_python/native/encode_bridge/include/camxora_encode_bridge.h`
- `camxora_python/native/encode_bridge/src/encode_bridge.cpp`
- `camxora_python/native/encode_bridge/src/nvenc_session.h`
- `camxora_python/native/encode_bridge/src/nvenc_session.cpp`
- `camxora_python/native/encode_bridge/CMakeLists.txt`
- `camxora_python/native/encode_bridge/README.md`
- `camxora_python/features/video/services/native_encode_bridge.py`
- `camxora_python/visualizer/native_encode_writer.py`
- `camxora_python/tests/test_native_encode_bridge.py`
- `camxora_python/tests/test_native_encode_writer.py`
- `docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md`
- `docs/changelog/2026-07-20-native-encode-bridge-nvenc.md`
- `CHANGELOG.md`

## Migration / deploy

- Rebuild Release DLL: `cmake -S camxora_python/native/encode_bridge -B …/build -G "Visual Studio 17 2022" -A x64` then `cmake --build … --config Release`.
- Ship `camxora_encode_bridge.dll` under `encode/` next to the app when packaging.
- Runtime: NVIDIA GPU + driver with `nvEncodeAPI64.dll` (System32). No CUDA toolkit.
- Enable with `CAMXORA_NATIVE_ENCODE=1` (primary). Optional: `CAMXORA_NATIVE_ENCODE_EXPORT=1` also enables; `CAMXORA_ENCODE_BRIDGE_DLL` overrides DLL path.
- Remux example: `ffmpeg -i video.h264 -i audio.wav -c:v copy -c:a aac out.mp4`.

## Tests

- Unit: `pytest camxora_python/tests/test_native_encode_bridge.py camxora_python/tests/test_native_encode_writer.py` (mocked loader + preferred() flags).
- Integration (optional): `CAMXORA_NATIVE_ENCODE_ITEST=1` + built DLL + GPU — encodes 8×256×256 frames to `.h264`, asserts size > 0.
- Local smoke: probe returns GPU name; 8×256×256 solid frames → non-empty `.h264` (very small sizes like 64–144 may fail NVENC init on some GPUs).

## Follow-ups

- GL→D3D11 shared texture / registered resource zero-copy (remove CPU NV12 upload).
- MP4 mux inside the bridge (optional); today remux after `.native.h264`.
- Zero-copy acceptance metrics (Video Encode % / 10× realtime) still open under REQ-3.5.
- Compare wall-clock export with `CAMXORA_NATIVE_ENCODE=1` vs pipe on a full track after this fix.

### Incident — native path slower than pipe (same day)

**User report (15:19):** With `CAMXORA_NATIVE_ENCODE=1`, Bass Drive tracks ~143s / ~163s wall vs prior Fast pipe ~26–35s.

**Cause:** Export used sync RGBA→NV12→NVENC on the render thread (naive C++ convert; no pack-on-writer overlap; larger per-frame CPU work than yuv420p pipe).

**Mitigation (interim):** Export gated behind `CAMXORA_NATIVE_ENCODE_EXPORT=1`.

**Fix (later same day):** API v2 `submit_nv12` + pipelined writer (OpenCV pack off render thread). Re-enabled export via `CAMXORA_NATIVE_ENCODE=1`.
