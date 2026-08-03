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
    normalize_app_version,
    read_installed_app_version,
    versions_match,
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
        target_version="1.0.16",
        status_file=Path("C:/Users/me/AppData/Local/Camxora/updates/update-status.json"),
    )
    assert "Wait-Process -Id 1234" in script
    assert "robocopy" in script
    assert "Start-Process -FilePath" in script
    assert "Assert-CamxoraVersion" in script
    assert "1.0.16" in script


def test_build_powershell_exe_script_uses_silent_progress_and_verifies_version() -> None:
    script = SoftwareUpdateInstaller._build_powershell_exe_script(
        parent_pid=4321,
        package_path=Path("C:/Users/me/AppData/Local/Camxora/updates/CamxoraSetup-update.exe"),
        launch_exe=Path("C:/Program Files/Camxora/Camxora.exe"),
        target_version="1.0.16",
        status_file=Path("C:/Users/me/AppData/Local/Camxora/updates/update-status.json"),
    )
    assert "Wait-Process -Id 4321" in script
    assert "/SILENT" in script
    assert "/VERYSILENT" not in script
    assert "/SUPPRESSMSGBOXES" not in script
    assert "Start-Process -FilePath $setup" in script
    assert "-Wait" in script
    assert "Assert-CamxoraVersion" in script
    assert "app-version.txt" in script
    assert "1.0.16" in script
    assert "Start-Process -FilePath $exe" in script
    assert "Write-CamxoraUpdateStatus" in script


def test_normalize_and_match_versions() -> None:
    assert normalize_app_version("\ufeff1.0.16\n") == "1.0.16"
    assert versions_match("1.0.16", "1.0.16")
    assert not versions_match("1.0.14", "1.0.16")
    assert not versions_match("", "1.0.16")


def test_read_installed_app_version(tmp_path: Path) -> None:
    exe = tmp_path / "Camxora.exe"
    exe.write_bytes(b"app")
    version_path = tmp_path / "_internal" / "resources" / "app-version.txt"
    version_path.parent.mkdir(parents=True)
    version_path.write_text("1.0.16\n", encoding="utf-8")
    assert read_installed_app_version(exe) == "1.0.16"


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


@patch("shared.services.software_update_installer.popen_hidden_orphan")
def test_apply_exe_stages_durable_and_launches_helper(
    mock_popen: MagicMock,
    tmp_path: Path,
) -> None:
    package = tmp_path / "downloaded-setup.exe"
    package.write_bytes(b"setup-bytes")
    work = tmp_path / "updates"
    work.mkdir()
    launch = tmp_path / "Camxora.exe"
    launch.write_bytes(b"app")

    with (
        patch("shared.services.software_update_installer.sys.platform", "win32"),
        patch("shared.services.software_update_installer.get_updates_work_dir", return_value=work),
        patch("shared.services.software_update_installer.get_launch_executable", return_value=launch),
        patch(
            "shared.services.software_update_installer.update_status_path",
            return_value=work / "update-status.json",
        ),
    ):
        SoftwareUpdateInstaller().apply(
            str(package),
            parent_pid=99,
            target_version="1.0.16",
        )

    durable = work / "CamxoraSetup-update.exe"
    assert durable.is_file()
    assert durable.read_bytes() == b"setup-bytes"
    script = work / "apply-exe-update.ps1"
    assert script.is_file()
    body = script.read_text(encoding="utf-8")
    assert "Wait-Process -Id 99" in body
    assert "/SILENT" in body
    assert "/VERYSILENT" not in body
    assert "1.0.16" in body

    mock_popen.assert_called_once()
    args = mock_popen.call_args.args[0]
    assert args[0] == "powershell"
    assert str(script) in args


@patch("shared.services.software_update_installer.popen_hidden_orphan")
def test_apply_msi_stages_durable_and_launches_helper(
    mock_popen: MagicMock,
    tmp_path: Path,
) -> None:
    package = tmp_path / "downloaded.msi"
    package.write_bytes(b"msi-bytes")
    work = tmp_path / "updates"
    work.mkdir()
    launch = tmp_path / "Camxora.exe"
    launch.write_bytes(b"app")

    with (
        patch("shared.services.software_update_installer.sys.platform", "win32"),
        patch("shared.services.software_update_installer.get_updates_work_dir", return_value=work),
        patch("shared.services.software_update_installer.get_launch_executable", return_value=launch),
        patch(
            "shared.services.software_update_installer.update_status_path",
            return_value=work / "update-status.json",
        ),
    ):
        SoftwareUpdateInstaller().apply(str(package), parent_pid=77, target_version="1.0.16")

    durable = work / "CamxoraUpdate.msi"
    assert durable.is_file()
    mock_popen.assert_called_once()
    args = mock_popen.call_args.args[0]
    assert args[0] == "powershell"
    script = work / "apply-msi-update.ps1"
    body = script.read_text(encoding="utf-8")
    assert "Assert-CamxoraVersion" in body
    assert "1.0.16" in body
