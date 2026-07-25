"""Silent software update installation strategies for the desktop app."""

from __future__ import annotations

import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from shared.lib.runtime_paths import (
    allow_zip_swap_update,
    get_install_dir,
    get_launch_executable,
    get_updates_work_dir,
)
from shared.lib.subprocess_utils import popen_hidden_orphan

logger = logging.getLogger(__name__)

PackageKind = str  # zip | exe | msi


class SoftwareUpdateInstallError(RuntimeError):
    pass


def detect_package_kind(package_path: str, download_url: str = "") -> PackageKind:
    suffix = Path(package_path).suffix.lower()
    if suffix == ".zip":
        return "zip"
    if suffix == ".msi":
        return "msi"
    if suffix == ".exe":
        return "exe"

    url_path = urlparse(download_url).path.lower()
    if url_path.endswith(".zip"):
        return "zip"
    if url_path.endswith(".msi"):
        return "msi"
    return "exe"


class SoftwareUpdateInstaller:
    """Apply a downloaded update package without showing an interactive installer."""

    def apply(self, package_path: str, *, download_url: str = "", parent_pid: int | None = None) -> None:
        kind = detect_package_kind(package_path, download_url)
        if kind == "zip":
            self._apply_zip(package_path, parent_pid=parent_pid)
            return
        if kind == "msi":
            self._apply_msi(package_path, parent_pid=parent_pid)
            return
        self._apply_exe(package_path, parent_pid=parent_pid)

    def _apply_zip(self, package_path: str, *, parent_pid: int | None) -> None:
        if not allow_zip_swap_update():
            raise SoftwareUpdateInstallError(
                "ZIP auto-updates require a packaged Camxora build. Publish an Inno/MSI installer for development builds."
            )

        install_dir = get_install_dir()
        launch_exe = get_launch_executable()
        if install_dir is None or launch_exe is None:
            raise SoftwareUpdateInstallError("Unable to locate the installed Camxora application.")

        work_dir = get_updates_work_dir()
        staging_root = work_dir / "staging"
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        staging_root.mkdir(parents=True, exist_ok=True)

        extract_dir = staging_root / "payload"
        extract_dir.mkdir(parents=True, exist_ok=True)
        self._extract_zip(package_path, extract_dir)

        source_dir = self._resolve_zip_payload_root(extract_dir)
        if launch_exe.name not in {path.name for path in source_dir.iterdir() if path.is_file()}:
            nested_exe = next(
                (
                    path
                    for path in source_dir.rglob("*.exe")
                    if path.name.lower() in {"camxora.exe", "musicgenerator.exe"}
                ),
                None,
            )
            if nested_exe is not None:
                source_dir = nested_exe.parent

        script_path = work_dir / "apply-update.ps1"
        script_path.write_text(
            self._build_powershell_zip_script(
                parent_pid=parent_pid or os.getpid(),
                source_dir=source_dir,
                target_dir=install_dir,
                launch_exe=launch_exe if launch_exe.parent == install_dir else install_dir / launch_exe.name,
            ),
            encoding="utf-8",
        )
        self._launch_powershell_script(script_path)

    def _apply_msi(self, package_path: str, *, parent_pid: int | None) -> None:
        if sys.platform != "win32":
            raise SoftwareUpdateInstallError("MSI auto-updates are only supported on Windows.")

        durable = self._stage_durable_package(package_path, preferred_name="CamxoraUpdate.msi")
        launch_exe = get_launch_executable()
        if launch_exe is None:
            raise SoftwareUpdateInstallError("Unable to locate the installed Camxora application.")

        script_path = get_updates_work_dir() / "apply-msi-update.ps1"
        script_path.write_text(
            self._build_powershell_msi_script(
                parent_pid=parent_pid or os.getpid(),
                package_path=durable,
                launch_exe=launch_exe,
            ),
            encoding="utf-8",
        )
        self._launch_powershell_script(script_path)

    def _apply_exe(self, package_path: str, *, parent_pid: int | None) -> None:
        if sys.platform != "win32":
            raise SoftwareUpdateInstallError("Silent EXE auto-updates are only supported on Windows.")

        durable = self._stage_durable_package(package_path, preferred_name="CamxoraSetup-update.exe")
        launch_exe = get_launch_executable()
        if launch_exe is None:
            raise SoftwareUpdateInstallError("Unable to locate the installed Camxora application.")

        script_path = get_updates_work_dir() / "apply-exe-update.ps1"
        script_path.write_text(
            self._build_powershell_exe_script(
                parent_pid=parent_pid or os.getpid(),
                package_path=durable,
                launch_exe=launch_exe,
            ),
            encoding="utf-8",
        )
        self._launch_powershell_script(script_path)

    @staticmethod
    def _stage_durable_package(package_path: str, *, preferred_name: str) -> Path:
        """Copy the download out of temp so cleanup cannot delete it mid-install."""
        source = Path(package_path)
        if not source.is_file():
            raise SoftwareUpdateInstallError("Update package is missing on disk.")
        work_dir = get_updates_work_dir()
        suffix = source.suffix.lower() or Path(preferred_name).suffix
        durable = work_dir / preferred_name
        if suffix and durable.suffix.lower() != suffix:
            durable = work_dir / f"{Path(preferred_name).stem}{suffix}"
        if source.resolve() != durable.resolve():
            shutil.copy2(source, durable)
        return durable

    @staticmethod
    def _extract_zip(package_path: str, extract_dir: Path) -> None:
        if not zipfile.is_zipfile(package_path):
            raise SoftwareUpdateInstallError("Update package is not a valid ZIP archive.")
        with zipfile.ZipFile(package_path, "r") as archive:
            archive.extractall(extract_dir)

    @staticmethod
    def _resolve_zip_payload_root(extract_dir: Path) -> Path:
        entries = [path for path in extract_dir.iterdir() if path.name != "__MACOSX"]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extract_dir

    @staticmethod
    def _build_powershell_zip_script(
        *,
        parent_pid: int,
        source_dir: Path,
        target_dir: Path,
        launch_exe: Path,
    ) -> str:
        source = str(source_dir).replace("'", "''")
        target = str(target_dir).replace("'", "''")
        exe = str(launch_exe).replace("'", "''")
        return f"""$ErrorActionPreference = "Stop"
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$source = '{source}'
$target = '{target}'
$exe = '{exe}'
& robocopy $source $target /MIR /COPY:DAT /R:3 /W:2 /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) {{ exit $LASTEXITCODE }}
Start-Process -FilePath $exe
"""

    @staticmethod
    def _build_powershell_exe_script(
        *,
        parent_pid: int,
        package_path: Path,
        launch_exe: Path,
    ) -> str:
        setup = str(package_path).replace("'", "''")
        exe = str(launch_exe).replace("'", "''")
        # Wait for Camxora to exit so Inno can overwrite locked files, then
        # run a fully silent install and relaunch the app.
        return f"""$ErrorActionPreference = "Stop"
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$setup = '{setup}'
$exe = '{exe}'
$args = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS','/FORCECLOSEAPPLICATIONS')
$proc = Start-Process -FilePath $setup -ArgumentList $args -PassThru -Wait
if ($null -ne $proc -and $proc.ExitCode -ne 0) {{
  exit $proc.ExitCode
}}
Start-Sleep -Seconds 1
if (Test-Path -LiteralPath $exe) {{
  Start-Process -FilePath $exe
}}
"""

    @staticmethod
    def _build_powershell_msi_script(
        *,
        parent_pid: int,
        package_path: Path,
        launch_exe: Path,
    ) -> str:
        msi = str(package_path).replace("'", "''")
        exe = str(launch_exe).replace("'", "''")
        return f"""$ErrorActionPreference = "Stop"
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$msi = '{msi}'
$exe = '{exe}'
$args = @('/i', $msi, '/quiet', '/norestart')
$proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList $args -PassThru -Wait
if ($null -ne $proc -and $proc.ExitCode -ne 0) {{
  exit $proc.ExitCode
}}
Start-Sleep -Seconds 1
if (Test-Path -LiteralPath $exe) {{
  Start-Process -FilePath $exe
}}
"""

    @staticmethod
    def _launch_powershell_script(script_path: Path) -> None:
        if sys.platform != "win32":
            raise SoftwareUpdateInstallError("Silent auto-updates are only supported on Windows.")

        # Must outlive Camxora — do not use popen_hidden (job kill-on-close).
        popen_hidden_orphan(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(script_path),
            ],
        )
