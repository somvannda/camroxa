"""ctypes loader for the optional Camxora Native Encode Bridge (REQ-3.5).

Enable with ``CAMXORA_NATIVE_ENCODE=1``. When the DLL is missing or encode
fails, callers should fall back to the ffmpeg pipe path.

Output is Annex-B elementary H.264 (use a ``.h264`` path). Remux with audio
via ffmpeg ``-c:v copy``.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union

logger = logging.getLogger(__name__)

CAMXORA_EB_OK = 0
CAMXORA_EB_ERR_NOT_IMPLEMENTED = 1
CAMXORA_EB_ERR_NO_DEVICE = 2
CAMXORA_EB_ERR_LOAD = 3
CAMXORA_EB_ERR_ENCODE = 4
CAMXORA_EB_ERR_IO = 5

_ENV_ENABLE = "CAMXORA_NATIVE_ENCODE"
_ENV_DLL = "CAMXORA_ENCODE_BRIDGE_DLL"
_DLL_NAME = "camxora_encode_bridge.dll"

_lib: Optional[ctypes.CDLL] = None
_load_attempted = False
_load_error: Optional[str] = None
_api_version: int = 0


class CamxoraEncodeConfig(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("fps", ctypes.c_int),
        ("bitrate_kbps", ctypes.c_int),
        ("output_path", ctypes.c_char_p),
    ]


def _env_enabled() -> bool:
    return os.environ.get(_ENV_ENABLE, "").strip().lower() in {"1", "true", "yes", "on"}


def _candidate_dll_paths() -> list[Path]:
    paths: list[Path] = []
    override = os.environ.get(_ENV_DLL, "").strip()
    if override:
        paths.append(Path(override))

    # Repo / editable install: camxora_python/native/encode_bridge/build/Release/
    here = Path(__file__).resolve()
    # .../features/video/services/native_encode_bridge.py → camxora_python/
    camxora_root = here.parents[3]
    paths.append(
        camxora_root
        / "native"
        / "encode_bridge"
        / "build"
        / "Release"
        / _DLL_NAME
    )

    # Packaged: next to executable under encode/
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path(sys.argv[0]).resolve().parent if sys.argv else Path.cwd()
    paths.append(exe_dir / "encode" / _DLL_NAME)

    return paths


def _bind_api(lib: ctypes.CDLL, version: int) -> None:
    lib.camxora_eb_version.argtypes = []
    lib.camxora_eb_version.restype = ctypes.c_int

    lib.camxora_eb_probe.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.camxora_eb_probe.restype = ctypes.c_int

    lib.camxora_eb_create.argtypes = [
        ctypes.POINTER(CamxoraEncodeConfig),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    lib.camxora_eb_create.restype = ctypes.c_int

    lib.camxora_eb_submit_rgba.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    lib.camxora_eb_submit_rgba.restype = ctypes.c_int

    # API v2+: pre-packed NV12 submit (skips RGBA convert in the DLL).
    if version >= 2 and hasattr(lib, "camxora_eb_submit_nv12"):
        lib.camxora_eb_submit_nv12.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        lib.camxora_eb_submit_nv12.restype = ctypes.c_int

    lib.camxora_eb_finish.argtypes = [ctypes.c_void_p]
    lib.camxora_eb_finish.restype = ctypes.c_int

    lib.camxora_eb_destroy.argtypes = [ctypes.c_void_p]
    lib.camxora_eb_destroy.restype = None


def _try_load_dll(path: Path) -> Optional[ctypes.CDLL]:
    if not path.is_file():
        return None
    try:
        lib = ctypes.CDLL(str(path))
        # Bind version first so we can gate optional symbols.
        lib.camxora_eb_version.argtypes = []
        lib.camxora_eb_version.restype = ctypes.c_int
        version = int(lib.camxora_eb_version())
        if version < 1:
            logger.warning("encode bridge at %s reported version %s", path, version)
            return None
        _bind_api(lib, version)
        lib._camxora_api_version = version  # type: ignore[attr-defined]
        logger.info("loaded encode bridge %s (api v%s)", path, version)
        return lib
    except OSError as exc:
        logger.debug("failed to load encode bridge %s: %s", path, exc)
        return None
    except AttributeError as exc:
        logger.warning("encode bridge %s missing symbols: %s", path, exc)
        return None


def reset_loader_state() -> None:
    """Clear cached load state (tests only)."""
    global _lib, _load_attempted, _load_error, _api_version
    _lib = None
    _load_attempted = False
    _load_error = None
    _api_version = 0


def _ensure_loaded() -> Optional[ctypes.CDLL]:
    global _lib, _load_attempted, _load_error, _api_version
    if _load_attempted:
        return _lib
    _load_attempted = True
    _load_error = None
    _api_version = 0

    if not _env_enabled():
        _load_error = f"{_ENV_ENABLE} not set"
        return None

    for path in _candidate_dll_paths():
        lib = _try_load_dll(path)
        if lib is not None:
            _lib = lib
            _api_version = int(getattr(lib, "_camxora_api_version", 1))
            return _lib

    _load_error = "DLL not found or failed to load"
    logger.debug("native encode bridge unavailable: %s", _load_error)
    return None


def bridge_api_version() -> int:
    """Loaded bridge API version, or 0 if unavailable."""
    if _ensure_loaded() is None:
        return 0
    return int(_api_version)


def is_available() -> bool:
    """Return True when CAMXORA_NATIVE_ENCODE is on and the DLL loads."""
    return _ensure_loaded() is not None


def probe() -> str:
    """Return GPU name, ``no-nvenc``, or ``stub``. Empty string if unavailable."""
    lib = _ensure_loaded()
    if lib is None:
        return ""
    buf = ctypes.create_string_buffer(256)
    rc = int(lib.camxora_eb_probe(buf, len(buf)))
    if rc != CAMXORA_EB_OK:
        return ""
    return buf.value.decode("utf-8", errors="replace")


def load_error() -> Optional[str]:
    """Last load failure reason (after ``is_available`` / ``probe``)."""
    _ensure_loaded()
    return _load_error


class NativeEncodeSession:
    """Context manager for a native NVENC encode session.

    Writes Annex-B H.264 to ``output_path``. On create/submit/finish failure,
    raises ``RuntimeError`` or ``NotImplementedError`` (stub mode) so callers
    can fall back to the ffmpeg pipe path.
    """

    def __init__(
        self,
        *,
        width: int,
        height: int,
        fps: int,
        output_path: str,
        bitrate_kbps: int = 0,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.output_path = output_path
        self.bitrate_kbps = bitrate_kbps
        self._session: Optional[ctypes.c_void_p] = None
        self._lib: Optional[ctypes.CDLL] = None

    def __enter__(self) -> NativeEncodeSession:
        lib = _ensure_loaded()
        if lib is None:
            raise RuntimeError(
                load_error() or "native encode bridge unavailable"
            )
        cfg = CamxoraEncodeConfig(
            width=self.width,
            height=self.height,
            fps=self.fps,
            bitrate_kbps=self.bitrate_kbps,
            output_path=self.output_path.encode("utf-8"),
        )
        out = ctypes.c_void_p()
        rc = int(lib.camxora_eb_create(ctypes.byref(cfg), ctypes.byref(out)))
        if rc == CAMXORA_EB_ERR_NOT_IMPLEMENTED:
            raise NotImplementedError(
                "native encode bridge stub: NVENC not implemented "
                "(use ffmpeg pipe fallback)"
            )
        if rc != CAMXORA_EB_OK or not out.value:
            raise RuntimeError(f"camxora_eb_create failed: {rc}")
        self._lib = lib
        self._session = out
        return self

    def supports_nv12(self) -> bool:
        """True when the loaded DLL exposes ``camxora_eb_submit_nv12`` (API ≥ 2)."""
        return (
            self._lib is not None
            and hasattr(self._lib, "camxora_eb_submit_nv12")
            and int(getattr(self._lib, "_camxora_api_version", 0)) >= 2
        )

    @staticmethod
    def _buffer_ptr(buf: Any) -> tuple[Any, Any]:
        """Return (c_void_p, keep_alive). keep_alive must outlive the C call."""
        if isinstance(buf, (bytes, bytearray, memoryview)):
            raw = bytes(buf)
            arr = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
            return ctypes.cast(arr, ctypes.c_void_p), arr
        data_as = getattr(getattr(buf, "ctypes", None), "data_as", None)
        if callable(data_as):
            return data_as(ctypes.c_void_p), buf
        return buf, buf

    def submit_rgba(self, rgba: Any, stride_bytes: int) -> None:
        if self._lib is None or self._session is None:
            raise RuntimeError("session not open")
        ptr, keep = self._buffer_ptr(rgba)
        rc = int(
            self._lib.camxora_eb_submit_rgba(
                self._session, ptr, int(stride_bytes)
            )
        )
        del keep
        if rc == CAMXORA_EB_ERR_NOT_IMPLEMENTED:
            raise NotImplementedError(
                "native encode bridge stub: submit_rgba not implemented"
            )
        if rc != CAMXORA_EB_OK:
            raise RuntimeError(f"camxora_eb_submit_rgba failed: {rc}")

    def submit_nv12(self, nv12: Any, y_stride: int) -> None:
        """Submit one contiguous NV12 frame (Y then interleaved UV)."""
        if self._lib is None or self._session is None:
            raise RuntimeError("session not open")
        if not self.supports_nv12():
            raise RuntimeError(
                "camxora_eb_submit_nv12 not available (API < 2); use submit_rgba"
            )
        ptr, keep = self._buffer_ptr(nv12)
        rc = int(
            self._lib.camxora_eb_submit_nv12(
                self._session, ptr, int(y_stride)
            )
        )
        del keep
        if rc == CAMXORA_EB_ERR_NOT_IMPLEMENTED:
            raise NotImplementedError(
                "native encode bridge stub: submit_nv12 not implemented"
            )
        if rc != CAMXORA_EB_OK:
            raise RuntimeError(f"camxora_eb_submit_nv12 failed: {rc}")

    def finish(self) -> None:
        if self._lib is None or self._session is None:
            raise RuntimeError("session not open")
        rc = int(self._lib.camxora_eb_finish(self._session))
        if rc == CAMXORA_EB_ERR_NOT_IMPLEMENTED:
            raise NotImplementedError(
                "native encode bridge stub: finish not implemented"
            )
        if rc != CAMXORA_EB_OK:
            raise RuntimeError(f"camxora_eb_finish failed: {rc}")

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._lib is not None and self._session is not None:
            self._lib.camxora_eb_destroy(self._session)
        self._session = None
        self._lib = None


def try_native_encode_video(
    *,
    width: int,
    height: int,
    fps: int,
    output_path: Union[str, Path],
    frames: Iterable[Union[bytes, bytearray, memoryview]],
    bitrate_kbps: int = 0,
    stride_bytes: Optional[int] = None,
) -> bool:
    """Encode RGBA frames with the native bridge.

    Returns ``True`` on success. Returns ``False`` (caller should use ffmpeg
    pipe) when the bridge is disabled, missing, stubbed, or encode fails.
    """
    if not is_available():
        return False
    out = str(output_path)
    stride = int(stride_bytes) if stride_bytes is not None else width * 4
    try:
        with NativeEncodeSession(
            width=width,
            height=height,
            fps=fps,
            output_path=out,
            bitrate_kbps=bitrate_kbps,
        ) as session:
            for frame in frames:
                session.submit_rgba(frame, stride)
            session.finish()
        return True
    except (NotImplementedError, RuntimeError, OSError) as exc:
        logger.info("native encode unavailable, use pipe fallback: %s", exc)
        return False


def solid_rgba_frames(
    width: int,
    height: int,
    count: int,
    *,
    rgba: Sequence[int] = (0, 128, 255, 255),
) -> list[bytes]:
    """Helper for smoke tests: ``count`` solid-color RGBA frames."""
    r, g, b, a = (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))
    pixel = bytes((r & 0xFF, g & 0xFF, b & 0xFF, a & 0xFF))
    frame = pixel * (width * height)
    return [frame for _ in range(count)]

