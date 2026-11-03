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


# ---------------------------------------------------------------------------
# Live drift detection (the "my hotfix disappeared" case, surfaced up front)
# ---------------------------------------------------------------------------


def test_live_source_status_ok_drift_and_missing() -> None:
    module = _load_guards()
    assert module.live_source_status(_FakeClient(marker=b"{}", exit_code=0), "/repo")[0] == "ok"
    assert module.live_source_status(_FakeClient(marker=b"{}", exit_code=1), "/repo")[0] == "drift"
    assert module.live_source_status(_FakeClient(marker=None), "/repo")[0] == "no-manifest"


def test_verify_live_source_raises_on_drift_and_missing() -> None:
    module = _load_guards()
    for client in (_FakeClient(marker=b"{}", exit_code=1), _FakeClient(marker=None)):
        try:
            module.verify_live_source(client, "/repo")
        except SystemExit:
            continue
        raise AssertionError("expected SystemExit for a live checkout that cannot be verified")


class _FakeOut:
    def __init__(self, text: str, code: int) -> None:
        self._text = text
        self.channel = self
        self._code = code

    def read(self) -> bytes:
        return self._text.encode("utf-8")

    def recv_exit_status(self) -> int:
        return self._code


class _FakeSftp:
    def __init__(self, marker: bytes | None) -> None:
        self.marker = marker
        self._data = b""

    def file(self, _path: str, _mode: str):
        if self.marker is None:
            raise OSError("missing")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self) -> bytes:
        return self.marker or b""

    def put(self, *_args, **_kwargs) -> None:
        return None

    def chmod(self, *_args, **_kwargs) -> None:
        return None

    def close(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *, marker: bytes | None, exit_code: int = 0) -> None:
        self._sftp = _FakeSftp(marker)
        self._code = exit_code

    def open_sftp(self):
        return self._sftp

    def exec_command(self, _cmd: str):
        return (None, _FakeOut("DEPLOY_VERIFY_OK", self._code), _FakeOut("", 0))


def _load_guards():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "deploy"
        / "check_deploy_guards.py"
    )
    spec = importlib.util.spec_from_file_location("check_deploy_guards", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
