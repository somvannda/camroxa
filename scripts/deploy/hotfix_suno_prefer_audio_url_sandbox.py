"""File-scoped sandbox hotfix: prefer Suno callback audioUrl."""
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
    "platform_api/clients/suno_client.py",
    "docs/changelog/2026-08-29-suno-prefer-callback-audio-url.md",
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

    archive = Path(tempfile.mkdtemp(prefix="suno-audio-url-hotfix-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno-audio-url-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/suno-audio-url-api.tar.gz -C $REPO
chown camxora:camxora \
  $REPO/platform_api/clients/suno_client.py \
  $REPO/docs/changelog/2026-08-29-suno-prefer-callback-audio-url.md
grep -n 'audio_url' $REPO/platform_api/clients/suno_client.py | head -8
systemctl restart camxora-api camxora-worker-suno@1 camxora-worker-suno@2
sleep 3
systemctl is-active camxora-api camxora-worker-suno@1 camxora-worker-suno@2
echo api_http=$(curl -sS -o /dev/null -w '%{http_code}' https://api.sandbox.camxora.com/health)
echo SUNO_AUDIO_URL_HOTFIX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=90)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-2000:], file=sys.stderr)
        if "SUNO_AUDIO_URL_HOTFIX_OK" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
