"""Visible-progress software update installation strategies for the desktop app."""

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
from shared.lib.software_update_persistence import (
    PHASE_DONE,
    PHASE_FAILED,
    PHASE_INSTALLING,
    PHASE_VERIFYING,
    PHASE_WAITING,
    update_status_path,
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


def normalize_app_version(raw: str | None) -> str:
    return str(raw or "").strip().lstrip("\ufeff").strip()


def read_installed_app_version(launch_exe: Path | None = None) -> str:
    """Read app-version.txt next to the installed Camxora.exe."""
    exe = launch_exe or get_launch_executable()
    if exe is None:
        return ""
    install_dir = exe.parent
    for relative in (
        Path("_internal") / "resources" / "app-version.txt",
        Path("resources") / "app-version.txt",
    ):
        path = install_dir / relative
        try:
            if path.is_file():
                return normalize_app_version(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return ""


def versions_match(installed: str, target: str) -> bool:
    left = normalize_app_version(installed)
    right = normalize_app_version(target)
    if not left or not right:
        return False
    return left == right


class SoftwareUpdateInstaller:
    """Apply a downloaded update package, showing Inno progress for EXE setups."""

    def apply(
        self,
        package_path: str,
        *,
        download_url: str = "",
        parent_pid: int | None = None,
        target_version: str = "",
    ) -> None:
        kind = detect_package_kind(package_path, download_url)
        if kind == "zip":
            self._apply_zip(package_path, parent_pid=parent_pid, target_version=target_version)
            return
        if kind == "msi":
            self._apply_msi(package_path, parent_pid=parent_pid, target_version=target_version)
            return
        self._apply_exe(package_path, parent_pid=parent_pid, target_version=target_version)

    def _apply_zip(
        self,
        package_path: str,
        *,
        parent_pid: int | None,
        target_version: str,
    ) -> None:
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
                target_version=target_version,
                status_file=update_status_path(),
            ),
            encoding="utf-8",
        )
        self._launch_powershell_script(script_path)

    def _apply_msi(
        self,
        package_path: str,
        *,
        parent_pid: int | None,
        target_version: str,
    ) -> None:
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
                target_version=target_version,
                status_file=update_status_path(),
            ),
            encoding="utf-8",
        )
        self._launch_powershell_script(script_path)

    def _apply_exe(
        self,
        package_path: str,
        *,
        parent_pid: int | None,
        target_version: str,
    ) -> None:
        if sys.platform != "win32":
            raise SoftwareUpdateInstallError("EXE auto-updates are only supported on Windows.")

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
                target_version=target_version,
                status_file=update_status_path(),
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
    def _ps_literal(value: str | Path) -> str:
        return str(value).replace("'", "''")

    @classmethod
    def _build_status_helpers(cls, status_file: Path) -> str:
        status = cls._ps_literal(status_file)
        return f"""function Write-CamxoraUpdateStatus([string]$Phase, [int]$ExitCode = 0, [string]$Installed = '', [string]$ErrorText = '') {{
  $payload = @{{
    phase = $Phase
    exit_code = $ExitCode
    installed_version = $Installed
    error = $ErrorText
  }} | ConvertTo-Json -Compress
  Set-Content -LiteralPath '{status}' -Value $payload -Encoding UTF8
}}
function Read-CamxoraInstalledVersion([string]$ExePath) {{
  $dir = Split-Path -Parent $ExePath
  $candidates = @(
    (Join-Path $dir '_internal\\resources\\app-version.txt'),
    (Join-Path $dir 'resources\\app-version.txt')
  )
  foreach ($candidate in $candidates) {{
    if (Test-Path -LiteralPath $candidate) {{
      return ((Get-Content -LiteralPath $candidate -Raw) -replace '^\\uFEFF', '').Trim()
    }}
  }}
  return ''
}}
function Assert-CamxoraVersion([string]$ExePath, [string]$TargetVersion) {{
  $installed = Read-CamxoraInstalledVersion $ExePath
  if (-not $TargetVersion) {{
    Write-CamxoraUpdateStatus '{PHASE_DONE}' 0 $installed
    return $installed
  }}
  if ($installed -ne $TargetVersion) {{
    $msg = "Installed version '$installed' does not match required '$TargetVersion'."
    Write-CamxoraUpdateStatus '{PHASE_FAILED}' 1 $installed $msg
    throw $msg
  }}
  Write-CamxoraUpdateStatus '{PHASE_DONE}' 0 $installed
  return $installed
}}
"""

    @classmethod
    def _build_powershell_zip_script(
        cls,
        *,
        parent_pid: int,
        source_dir: Path,
        target_dir: Path,
        launch_exe: Path,
        target_version: str = "",
        status_file: Path | None = None,
    ) -> str:
        source = cls._ps_literal(source_dir)
        target = cls._ps_literal(target_dir)
        exe = cls._ps_literal(launch_exe)
        version = cls._ps_literal(normalize_app_version(target_version))
        status = status_file or update_status_path()
        helpers = cls._build_status_helpers(status)
        return f"""$ErrorActionPreference = "Stop"
{helpers}
Write-CamxoraUpdateStatus '{PHASE_WAITING}'
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$source = '{source}'
$target = '{target}'
$exe = '{exe}'
$targetVersion = '{version}'
Write-CamxoraUpdateStatus '{PHASE_INSTALLING}'
& robocopy $source $target /MIR /COPY:DAT /R:3 /W:2 /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) {{
  Write-CamxoraUpdateStatus '{PHASE_FAILED}' $LASTEXITCODE '' "robocopy failed with exit $LASTEXITCODE"
  exit $LASTEXITCODE
}}
Write-CamxoraUpdateStatus '{PHASE_VERIFYING}'
Assert-CamxoraVersion $exe $targetVersion | Out-Null
Start-Process -FilePath $exe
"""

    @classmethod
    def _build_powershell_exe_script(
        cls,
        *,
        parent_pid: int,
        package_path: Path,
        launch_exe: Path,
        target_version: str = "",
        status_file: Path | None = None,
    ) -> str:
        setup = cls._ps_literal(package_path)
        exe = cls._ps_literal(launch_exe)
        version = cls._ps_literal(normalize_app_version(target_version))
        status = status_file or update_status_path()
        helpers = cls._build_status_helpers(status)
        # /SILENT shows Inno progress (not fully invisible /VERYSILENT).
        return f"""$ErrorActionPreference = "Stop"
{helpers}
Write-CamxoraUpdateStatus '{PHASE_WAITING}'
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$setup = '{setup}'
$exe = '{exe}'
$targetVersion = '{version}'
Write-CamxoraUpdateStatus '{PHASE_INSTALLING}'
$args = @('/SILENT','/NORESTART','/CLOSEAPPLICATIONS','/FORCECLOSEAPPLICATIONS')
$proc = Start-Process -FilePath $setup -ArgumentList $args -PassThru -Wait
if ($null -ne $proc -and $proc.ExitCode -ne 0) {{
  Write-CamxoraUpdateStatus '{PHASE_FAILED}' $proc.ExitCode '' "Setup exited with code $($proc.ExitCode)"
  exit $proc.ExitCode
}}
Start-Sleep -Seconds 1
Write-CamxoraUpdateStatus '{PHASE_VERIFYING}'
Assert-CamxoraVersion $exe $targetVersion | Out-Null
if (Test-Path -LiteralPath $exe) {{
  Start-Process -FilePath $exe
}}
"""

    @classmethod
    def _build_powershell_msi_script(
        cls,
        *,
        parent_pid: int,
        package_path: Path,
        launch_exe: Path,
        target_version: str = "",
        status_file: Path | None = None,
    ) -> str:
        msi = cls._ps_literal(package_path)
        exe = cls._ps_literal(launch_exe)
        version = cls._ps_literal(normalize_app_version(target_version))
        status = status_file or update_status_path()
        helpers = cls._build_status_helpers(status)
        return f"""$ErrorActionPreference = "Stop"
{helpers}
Write-CamxoraUpdateStatus '{PHASE_WAITING}'
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$msi = '{msi}'
$exe = '{exe}'
$targetVersion = '{version}'
Write-CamxoraUpdateStatus '{PHASE_INSTALLING}'
$args = @('/i', $msi, '/quiet', '/norestart')
$proc = Start-Process -FilePath 'msiexec.exe' -ArgumentList $args -PassThru -Wait
if ($null -ne $proc -and $proc.ExitCode -ne 0) {{
  Write-CamxoraUpdateStatus '{PHASE_FAILED}' $proc.ExitCode '' "msiexec exited with code $($proc.ExitCode)"
  exit $proc.ExitCode
}}
Start-Sleep -Seconds 1
Write-CamxoraUpdateStatus '{PHASE_VERIFYING}'
Assert-CamxoraVersion $exe $targetVersion | Out-Null
if (Test-Path -LiteralPath $exe) {{
  Start-Process -FilePath $exe
}}
"""

    @staticmethod
    def _launch_powershell_script(script_path: Path) -> None:
        if sys.platform != "win32":
            raise SoftwareUpdateInstallError("Auto-updates are only supported on Windows.")

        # Must outlive Camxora — do not use popen_hidden (job kill-on-close).
        # Hidden PowerShell console; Inno /SILENT still shows its own progress UI.
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
