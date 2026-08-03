"""File-scoped sandbox hotfix: Suno blocklist hyphen/space variants."""
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

FILES = [
    "platform_api/services/suno_lyrics_sanitize.py",
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

    archive = Path(tempfile.mkdtemp(prefix="suno-blocklist-hotfix-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno-blocklist-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/suno-blocklist-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api/services/suno_lyrics_sanitize.py "
            "$REPO/platform_api/CHANGELOG.md; "
            "systemctl restart camxora-api; "
            "sleep 2; "
            "systemctl is-active camxora-api; "
            "grep -n blocked_term_pattern "
            "$REPO/platform_api/services/suno_lyrics_sanitize.py | head -3; "
            "echo SUNO_BLOCKLIST_HOTFIX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err.strip():
            print("STDERR", err[-2000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
