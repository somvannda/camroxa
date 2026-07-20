# NativeEncodeBridge scaffold (REQ-3.5)

**Date:** 2026-07-20  
**Status:** implemented (scaffold only; real NVENC follow-up)

## Summary

Started the optional Windows C++ encode bridge without deferring on Phase 2 benchmarks. Ships a CMake stub DLL (version + probe; encode returns `NOT_IMPLEMENTED`), a ctypes Python loader gated by `CAMXORA_NATIVE_ENCODE`, and unit tests that mock ctypes / missing DLL. Export continues to use the ffmpeg pipe until real NVENC is wired.

## Product impact

- **Before:** No native encode plugin path; all export uses pipe → ffmpeg.
- **After:** App can detect/load `camxora_encode_bridge.dll` when enabled; encode still falls back to pipe (stub does not produce video). No user-visible change unless the env flag is set for development.

## Technical impact

- New C API in `camxora_python/native/encode_bridge/` (MSVC + CMake; NVIDIA Video Codec SDK **not** required for stub).
- Python loader: `features/video/services/native_encode_bridge.py` — search order env override → build/Release → `encode/` next to exe.
- Docs: REQ-3.5 marked scaffold in progress (not deferred); Phase 2 work remains in parallel.

## Files touched

- `camxora_python/native/encode_bridge/README.md`
- `camxora_python/native/encode_bridge/CMakeLists.txt`
- `camxora_python/native/encode_bridge/include/camxora_encode_bridge.h`
- `camxora_python/native/encode_bridge/src/encode_bridge.cpp`
- `camxora_python/features/video/services/native_encode_bridge.py`
- `camxora_python/tests/test_native_encode_bridge.py`
- `docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md`
- `docs/changelog/2026-07-20-native-encode-bridge-scaffold.md`
- `CHANGELOG.md`

## Migration / deploy

- No DB/API migrations.
- Optional: build DLL with CMake+MSVC (see native README); ship under `dist/Camxora/encode/` when packaging.
- Env: `CAMXORA_NATIVE_ENCODE=1` to attempt load; `CAMXORA_ENCODE_BRIDGE_DLL` for absolute path override.
- Real NVENC later needs NVIDIA Video Codec SDK headers/libs (documented in README).

## Tests

- `pytest camxora_python/tests/test_native_encode_bridge.py` — mocked ctypes / missing DLL (no real DLL required in CI).

## Follow-ups

- Implement NVENC session in `encode_bridge.cpp` (D3D11/CUDA → NVENC).
- Wire loader into export pipeline with explicit pipe fallback on `NotImplementedError` / missing DLL.
- Package DLL in installer optional component; acceptance metrics (Video Encode %, 10× RTF).
