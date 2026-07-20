# Camxora Native Encode Bridge (REQ-3.5)

Optional Windows C++ DLL for hardware NVENC H.264 encode. The Python app loads it via ctypes when `CAMXORA_NATIVE_ENCODE=1`; if the DLL is missing, NVENC is unavailable, or create fails, export falls back to the existing ffmpeg pipe path.

## Status

| Symbol | Behavior |
|--------|----------|
| `camxora_eb_version` | Returns `2` |
| `camxora_eb_probe` | DXGI NVIDIA adapter name, or `"no-nvenc"` / `"stub"` |
| `camxora_eb_create` / `submit_rgba` / `submit_nv12` / `finish` | Real NVENC (CPU upload) |
| `camxora_eb_destroy` | Releases NVENC + D3D11 + file |

**Encode path today:** D3D11 device + `nvEncCreateInputBuffer` (NV12) + CPU upload. Prefer `camxora_eb_submit_nv12` when Python packs RGBA→NV12 on a writer thread (OpenCV); `submit_rgba` remains for fallback. Hardware NVENC encode (big win vs x264; removes ffmpeg pipe for video). **GL→D3D zero-copy is follow-up.** Very small frames (e.g. 64×64 / 128×128) may fail encoder init depending on GPU/driver; production export sizes are fine.

**Output:** always Annex-B elementary H.264 written to `output_path` (use a `.h264` extension). Python remuxes with audio via ffmpeg `-c:v copy` (do not re-encode).

Force stub (create returns `NOT_IMPLEMENTED`) with `CAMXORA_NATIVE_ENCODE_STUB=1`.

## Build dependencies

| Dependency | Required |
|------------|----------|
| CMake ≥ 3.16 | Yes |
| MSVC (VS 2019/2022 Build Tools) | Yes (Windows) |
| Vendored `third_party/nvidia/nvEncodeAPI.h` | Yes — Video Codec SDK **13.0** compatible header (from [FFmpeg nv-codec-headers](https://github.com/FFmpeg/nv-codec-headers) `n13.0.19.1`; matches driver max via `NvEncodeAPIGetMaxSupportedVersion`; no full SDK install) |
| Link `d3d11.lib` `dxgi.lib` | Yes |
| Link `nvEncodeAPI.lib` | **No** — runtime `LoadLibrary("nvEncodeAPI64.dll")` |
| CUDA Toolkit | **No** |
| NVIDIA driver with NVENC | Runtime only |

## How to build (Windows)

From this directory (`camxora_python/native/encode_bridge/`):

```bat
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

If `cmake` is not on PATH, use the Build Tools copy:

```bat
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" -S . -B build -G "Visual Studio 17 2022" -A x64
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build build --config Release
```

Output DLL:

```
build/Release/camxora_encode_bridge.dll
```

For packaged apps, ship under `encode/camxora_encode_bridge.dll` next to the executable.

## Runtime

- NVIDIA GPU with NVENC + recent Game Ready / Studio driver (`nvEncodeAPI64.dll` in System32).
- Without NVIDIA/NVENC: `probe` → `"no-nvenc"` / `ERR_NO_DEVICE`; app keeps ffmpeg pipe fallback.

## How Python loads the bridge

Loader: `camxora_python/features/video/services/native_encode_bridge.py`

1. Set `CAMXORA_NATIVE_ENCODE=1` to attempt load **and** use the native path on export (pipelined OpenCV RGBA→NV12 + `submit_nv12`). Optional: `CAMXORA_NATIVE_ENCODE_EXPORT=1` also enables export selection.
2. DLL search order:
   1. `CAMXORA_ENCODE_BRIDGE_DLL` (absolute path override)
   2. `camxora_python/native/encode_bridge/build/Release/camxora_encode_bridge.dll`
   3. Next to the executable: `encode/camxora_encode_bridge.dll`
3. `NativeEncodeWriter` packs on thread `camxora-native-encode` (same queue model as the ffmpeg pipe writer), then calls `submit_nv12` (API v2) or falls back to `submit_rgba` on older DLLs.
4. `NativeEncodeSession` encodes Annex-B to `output_path`; on any create/submit/finish error, callers fall back to pipe.
5. Optional helper: `try_native_encode_video(...)`.

## Layout

```
encode_bridge/
  README.md
  CMakeLists.txt
  include/camxora_encode_bridge.h
  src/encode_bridge.cpp
  src/nvenc_session.h
  src/nvenc_session.cpp
  third_party/nvidia/nvEncodeAPI.h
```

