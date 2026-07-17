from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shared.lib.runtime_paths import allow_zip_swap_update
from shared.services.software_update_installer import (
    SoftwareUpdateInstallError,
    SoftwareUpdateInstaller,
    detect_package_kind,
)


def test_detect_package_kind_from_path_and_url() -> None:
    assert detect_package_kind("/tmp/update.zip") == "zip"
    assert detect_package_kind("/tmp/update.msi") == "msi"
    assert detect_package_kind("/tmp/update.exe") == "exe"
    assert detect_package_kind("/tmp/update", "https://cdn.example.com/Camxora-2.0.zip") == "zip"
    assert detect_package_kind("/tmp/update", "https://cdn.example.com/Camxora-2.0.msi") == "msi"
    assert detect_package_kind("/tmp/update", "https://cdn.example.com/Camxora-2.0") == "exe"


def test_resolve_zip_payload_root_single_folder(tmp_path: Path) -> None:
    extract_dir = tmp_path / "payload"
    extract_dir.mkdir()
    nested = extract_dir / "Camxora"
    nested.mkdir()
    (nested / "Camxora.exe").write_bytes(b"binary")

    resolved = SoftwareUpdateInstaller._resolve_zip_payload_root(extract_dir)
    assert resolved == nested


def test_build_powershell_zip_script_contains_robocopy() -> None:
    script = SoftwareUpdateInstaller._build_powershell_zip_script(
        parent_pid=1234,
        source_dir=Path("C:/staging/Camxora"),
        target_dir=Path("C:/Program Files/Camxora"),
        launch_exe=Path("C:/Program Files/Camxora/Camxora.exe"),
    )
    assert "Wait-Process -Id 1234" in script
    assert "robocopy" in script
    assert "Start-Process -FilePath" in script


def test_allow_zip_swap_update_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_ALLOW_ZIP_UPDATE", raising=False)
    with patch("shared.lib.runtime_paths.is_frozen_runtime", return_value=False):
        assert not allow_zip_swap_update()
    monkeypatch.setenv("CAMXORA_ALLOW_ZIP_UPDATE", "1")
    with patch("shared.lib.runtime_paths.is_frozen_runtime", return_value=False):
        assert allow_zip_swap_update()


def test_apply_zip_requires_packaged_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package_path = tmp_path / "update.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("Camxora.exe", b"binary")

    monkeypatch.delenv("CAMXORA_ALLOW_ZIP_UPDATE", raising=False)
    with patch("shared.services.software_update_installer.allow_zip_swap_update", return_value=False):
        with pytest.raises(SoftwareUpdateInstallError, match="packaged Camxora build"):
            SoftwareUpdateInstaller().apply(str(package_path))


@patch("shared.services.software_update_installer.popen_hidden")
def test_apply_exe_launches_silent_flags(mock_popen: MagicMock) -> None:
    with patch("shared.services.software_update_installer.sys.platform", "win32"):
        SoftwareUpdateInstaller().apply("C:/tmp/Camxora.exe")

    mock_popen.assert_called_once()
    args = mock_popen.call_args.args[0]
    assert args[0] == "C:/tmp/Camxora.exe"
    assert "/VERYSILENT" in args


@patch("shared.services.software_update_installer.popen_hidden")
def test_apply_msi_launches_msiexec_quiet(mock_popen: MagicMock) -> None:
    with patch("shared.services.software_update_installer.sys.platform", "win32"):
        SoftwareUpdateInstaller().apply("C:/tmp/Camxora.msi")

    mock_popen.assert_called_once()
    args = mock_popen.call_args.args[0]
    assert args[:3] == ["msiexec", "/i", "C:/tmp/Camxora.msi"]
    assert "/quiet" in args
