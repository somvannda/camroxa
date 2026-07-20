"""Unit tests for native encode bridge loader (mocked ctypes / missing DLL)."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from features.video.services import native_encode_bridge as neb


@pytest.fixture(autouse=True)
def _reset_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    neb.reset_loader_state()
    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE", raising=False)
    monkeypatch.delenv("CAMXORA_ENCODE_BRIDGE_DLL", raising=False)
    yield
    neb.reset_loader_state()


def test_is_available_false_when_env_off() -> None:
    assert neb.is_available() is False
    assert neb.load_error() == "CAMXORA_NATIVE_ENCODE not set"
    assert neb.probe() == ""


def test_is_available_false_when_dll_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")
    missing = tmp_path / "nope.dll"
    monkeypatch.setenv("CAMXORA_ENCODE_BRIDGE_DLL", str(missing))

    with patch.object(neb, "_candidate_dll_paths", return_value=[missing]):
        assert neb.is_available() is False
    assert neb.load_error() == "DLL not found or failed to load"


def _probe_stub(buf: Any, length: int) -> int:
    name = b"stub\0"
    ctypes.memmove(buf, name, min(len(name), length))
    return neb.CAMXORA_EB_OK


def test_is_available_true_with_mocked_dll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")

    fake_lib = MagicMock()
    fake_lib.camxora_eb_version.return_value = 1
    fake_lib.camxora_eb_probe.side_effect = _probe_stub

    fake_path = Path("C:/fake/camxora_encode_bridge.dll")

    def fake_try_load(path: Path) -> Any:
        if path == fake_path:
            return fake_lib
        return None

    with (
        patch.object(neb, "_candidate_dll_paths", return_value=[fake_path]),
        patch.object(neb, "_try_load_dll", side_effect=fake_try_load),
    ):
        assert neb.is_available() is True
        assert neb.probe() == "stub"


def test_session_raises_not_implemented_on_create(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")

    fake_lib = MagicMock()
    fake_lib.camxora_eb_version.return_value = 1
    fake_lib.camxora_eb_create.return_value = neb.CAMXORA_EB_ERR_NOT_IMPLEMENTED
    fake_path = Path("C:/fake/camxora_encode_bridge.dll")

    with (
        patch.object(neb, "_candidate_dll_paths", return_value=[fake_path]),
        patch.object(neb, "_try_load_dll", return_value=fake_lib),
    ):
        with pytest.raises(NotImplementedError, match="NVENC not implemented"):
            with neb.NativeEncodeSession(
                width=1920, height=1080, fps=24, output_path="out.mp4"
            ):
                pass


def test_session_submit_raises_not_implemented() -> None:
    fake_lib = MagicMock()
    fake_lib.camxora_eb_submit_rgba.return_value = neb.CAMXORA_EB_ERR_NOT_IMPLEMENTED
    fake_lib.camxora_eb_destroy.return_value = None
    fake_lib._camxora_api_version = 1

    session = neb.NativeEncodeSession(
        width=64, height=64, fps=24, output_path="out.mp4"
    )
    session._lib = fake_lib
    session._session = ctypes.c_void_p(0xABCD)

    with pytest.raises(NotImplementedError, match="submit_rgba"):
        session.submit_rgba(b"\x00" * (64 * 64 * 4), 64 * 4)

    session.__exit__(None, None, None)
    fake_lib.camxora_eb_destroy.assert_called()


def test_session_submit_nv12_success() -> None:
    fake_lib = MagicMock()
    fake_lib.camxora_eb_submit_nv12.return_value = neb.CAMXORA_EB_OK
    fake_lib.camxora_eb_destroy.return_value = None
    fake_lib._camxora_api_version = 2
    # Ensure hasattr sees a real callable attribute for supports_nv12.
    fake_lib.camxora_eb_submit_nv12 = MagicMock(return_value=neb.CAMXORA_EB_OK)

    session = neb.NativeEncodeSession(
        width=64, height=64, fps=24, output_path="out.h264"
    )
    session._lib = fake_lib
    session._session = ctypes.c_void_p(0xABCD)

    assert session.supports_nv12() is True
    nv12 = b"\x00" * ((64 * 64 * 3) // 2)
    session.submit_nv12(nv12, 64)
    fake_lib.camxora_eb_submit_nv12.assert_called()
    session.__exit__(None, None, None)


def test_session_submit_nv12_unavailable_on_api_v1() -> None:
    fake_lib = MagicMock()
    fake_lib._camxora_api_version = 1

    session = neb.NativeEncodeSession(
        width=64, height=64, fps=24, output_path="out.h264"
    )
    session._lib = fake_lib
    session._session = ctypes.c_void_p(0xABCD)

    assert session.supports_nv12() is False
    with pytest.raises(RuntimeError, match="API < 2"):
        session.submit_nv12(b"\x00" * ((64 * 64 * 3) // 2), 64)
    session.__exit__(None, None, None)


def test_session_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")

    fake_lib = MagicMock()
    fake_lib.camxora_eb_version.return_value = 1
    fake_lib.camxora_eb_create.return_value = neb.CAMXORA_EB_OK
    fake_lib.camxora_eb_submit_rgba.return_value = neb.CAMXORA_EB_OK
    fake_lib.camxora_eb_finish.return_value = neb.CAMXORA_EB_OK
    fake_lib.camxora_eb_destroy.return_value = None

    def create(cfg: Any, out: Any) -> int:
        # ctypes.byref(c_void_p) exposes the original via ._obj
        getattr(out, "_obj").value = 0x1234
        return neb.CAMXORA_EB_OK

    fake_lib.camxora_eb_create.side_effect = create
    fake_path = Path("C:/fake/camxora_encode_bridge.dll")

    with (
        patch.object(neb, "_candidate_dll_paths", return_value=[fake_path]),
        patch.object(neb, "_try_load_dll", return_value=fake_lib),
    ):
        with neb.NativeEncodeSession(
            width=64, height=64, fps=24, output_path="out.h264"
        ) as session:
            session.submit_rgba(b"\x00" * (64 * 64 * 4), 64 * 4)
            session.finish()

    fake_lib.camxora_eb_submit_rgba.assert_called()
    fake_lib.camxora_eb_finish.assert_called()
    fake_lib.camxora_eb_destroy.assert_called()


def test_try_native_encode_video_false_when_disabled() -> None:
    assert neb.try_native_encode_video(
        width=64,
        height=64,
        fps=24,
        output_path="out.h264",
        frames=[b"\x00" * (64 * 64 * 4)],
    ) is False


def test_try_native_encode_video_true_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")
    fake_lib = MagicMock()
    fake_lib.camxora_eb_version.return_value = 1

    def create(cfg: Any, out: Any) -> int:
        getattr(out, "_obj").value = 0x99
        return neb.CAMXORA_EB_OK

    fake_lib.camxora_eb_create.side_effect = create
    fake_lib.camxora_eb_submit_rgba.return_value = neb.CAMXORA_EB_OK
    fake_lib.camxora_eb_finish.return_value = neb.CAMXORA_EB_OK
    fake_path = Path("C:/fake/camxora_encode_bridge.dll")

    with (
        patch.object(neb, "_candidate_dll_paths", return_value=[fake_path]),
        patch.object(neb, "_try_load_dll", return_value=fake_lib),
    ):
        ok = neb.try_native_encode_video(
            width=64,
            height=64,
            fps=24,
            output_path="out.h264",
            frames=neb.solid_rgba_frames(64, 64, 2),
        )
    assert ok is True


def test_candidate_paths_include_env_and_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom.dll"
    custom.write_bytes(b"x")
    monkeypatch.setenv("CAMXORA_ENCODE_BRIDGE_DLL", str(custom))
    paths = neb._candidate_dll_paths()
    assert paths[0] == custom
    assert any(p.name == "camxora_encode_bridge.dll" and "encode_bridge" in str(p) for p in paths)


def _dll_present() -> bool:
    root = Path(__file__).resolve().parents[1]
    dll = root / "native" / "encode_bridge" / "build" / "Release" / "camxora_encode_bridge.dll"
    return dll.is_file()


@pytest.mark.skipif(
    os.environ.get("CAMXORA_NATIVE_ENCODE_ITEST", "").strip() != "1",
    reason="Set CAMXORA_NATIVE_ENCODE_ITEST=1 for live NVENC integration test",
)
def test_integration_nvenc_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not _dll_present():
        pytest.skip("camxora_encode_bridge.dll not built")

    monkeypatch.setenv("CAMXORA_NATIVE_ENCODE", "1")
    monkeypatch.delenv("CAMXORA_NATIVE_ENCODE_STUB", raising=False)
    neb.reset_loader_state()

    assert neb.is_available() is True
    name = neb.probe()
    assert name
    assert name != "stub"

    # NVENC minimum resolution varies by GPU/driver; 256x256 is reliably above
    # the floor on consumer cards (128x128 may fail on some adapters).
    w, h, n = 256, 256, 8
    out = tmp_path / "smoke.h264"
    ok = neb.try_native_encode_video(
        width=w,
        height=h,
        fps=24,
        output_path=out,
        frames=neb.solid_rgba_frames(w, h, n, rgba=(32, 160, 240, 255)),
        bitrate_kbps=1000,
    )
    if name == "no-nvenc":
        assert ok is False
        return
    assert ok is True
    assert out.is_file()
    assert out.stat().st_size > 0

