"""Deploy hygiene: no script may write source into production unverified."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "deploy"
        / "check_deploy_hygiene.py"
    )
    spec = importlib.util.spec_from_file_location("check_deploy_hygiene", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_into_repo_is_flagged_unless_verified() -> None:
    module = _load()

    legacy = 'tar -xzf /tmp/camxora-src.tar.gz -C /opt/camxora/repo platform_api\n'
    findings = module.scan_text(Path("legacy.py"), legacy)
    assert len(findings) == 1
    assert findings[0].verified is False
    assert "tarball" in findings[0].reason

    verified = (
        "from deploy import build_source_bundle\n"
        "bundle = build_source_bundle(DEFAULT_SOURCE_REF)\n"
        'tar -xzf /tmp/camxora-src.tar.gz -C /opt/camxora/repo platform_api\n'
    )
    assert module.scan_text(Path("new.py"), verified)[0].verified is True


def test_sftp_put_into_repo_is_flagged() -> None:
    module = _load()
    text = 'sftp.put(str(path), "/opt/camxora/repo/admin_portal/src/App.tsx")\n'
    findings = module.scan_text(Path("push.py"), text)
    assert findings and findings[0].verified is False
    assert "sftp.put" in findings[0].reason


def test_reads_and_runtime_state_are_not_flagged() -> None:
    module = _load()
    safe = "\n".join(
        [
            'cat /opt/camxora/repo/.deployed.json',
            'grep -n proxy_read_timeout /opt/camxora/repo/platform_api/main.py',
            'sftp.put(str(env), "/opt/camxora/repo/platform_api/.env")',
            'cp -a /tmp/x /opt/camxora/repo/uploads/',
            'rm -rf /opt/camxora/repo/music_web/.next',
            'cat > /opt/camxora/repo/music_web/.env.production <<EOF',
        ]
    )
    assert module.scan_text(Path("ops.py"), safe) == []


def test_cd_then_extract_is_flagged() -> None:
    module = _load()
    text = "cd /opt/camxora/repo\nrm -rf music_web\n tar -xzf /tmp/src.tar.gz\n"
    findings = module.scan_text(Path("old.py"), text)
    assert any("in-place" in f.reason for f in findings)


def test_pathlib_edit_of_repo_source_is_flagged() -> None:
    module = _load()
    text = (
        'svc = Path("/opt/camxora/repo/platform_api/services/web_music_service.py")\n'
        'svc.write_text(svc.read_text() + "\\nPATCH = 1\\n")\n'
    )
    findings = module.scan_text(Path("patch.py"), text)
    assert findings and findings[0].verified is False


def test_strict_fails_and_changed_only_passes_clean_files(tmp_path: Path) -> None:
    module = _load()
    good = tmp_path / "clean.py"
    good.write_text(
        'bundle = build_source_bundle("origin/main")\n'
        'tar -xzf /tmp/s.tar.gz -C /opt/camxora/repo platform_api\n',
        encoding="utf-8",
    )
    assert module.scan_paths([good])[0].verified is True
