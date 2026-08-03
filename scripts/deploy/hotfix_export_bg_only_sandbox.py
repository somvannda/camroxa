"""File-scoped sandbox hotfix: export ready when background exists (no TH wait)."""
from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

# Only export-readiness surfaces — not unrelated dirty working-tree files.
FILES = [
    "platform_api/services/channel_asset_service.py",
    "platform_api/routers/progress.py",
    "platform_api/services/batch_service.py",
    "platform_api/CHANGELOG.md",
]


def load_sandbox() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.sandbox.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != "46.250.235.83":
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="export-bg-only-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/export-bg-only-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/export-bg-only-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora "
            "$REPO/platform_api/services/channel_asset_service.py "
            "$REPO/platform_api/routers/progress.py "
            "$REPO/platform_api/services/batch_service.py "
            "$REPO/platform_api/CHANGELOG.md; "
            "systemctl restart camxora-api; "
            "for i in 1 2 3 4 5 6 7 8 9 10; do "
            "  code=$(curl -sS -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health || true); "
            "  if [ \"$code\" = \"200\" ]; then echo health_ok_$i; break; fi; "
            "  sleep 2; "
            "done; "
            "systemctl is-active camxora-api; "
            "grep -n 'thumbnail is YouTube-only' "
            "$REPO/platform_api/services/channel_asset_service.py | head -3; "
            "grep -n 'Export can start once the background' "
            "$REPO/platform_api/routers/progress.py | head -2; "
            "echo EXPORT_BG_ONLY_HOTFIX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR", err[-2000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
