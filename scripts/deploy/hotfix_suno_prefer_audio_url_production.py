"""File-scoped production hotfix: prefer Suno callback audioUrl.

Allowlisted paths only. Does not sync the rest of platform_api.
Run only when explicitly asked for production.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/clients/suno_client.py",
    "docs/changelog/2026-08-29-suno-prefer-callback-audio-url.md",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== File-scoped Suno audioUrl hotfix -> production ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel}")
            sftp.put(str(local), remote)
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/clients/suno_client.py \
  $REPO/docs/changelog/2026-08-29-suno-prefer-callback-audio-url.md
python3 - <<'PY'
from pathlib import Path
text = Path("/opt/camxora/repo/platform_api/clients/suno_client.py").read_text()
needle = '''    for key in (
        "audio_url",
        "audioUrl",
        "source_audio_url",
        "sourceAudioUrl",
    ):'''
if needle not in text:
    raise SystemExit("VERIFY_FAIL: audioUrl is not preferred in suno_client.py")
print("VERIFY_OK: audioUrl preferred over sourceAudioUrl")
PY
systemctl restart camxora-api camxora-worker-suno@1 camxora-worker-suno@2
sleep 4
systemctl is-active camxora-api camxora-worker-suno@1 camxora-worker-suno@2
curl -sf -o /dev/null -w 'health:%{http_code}\n' https://api.camxora.com/health
echo SUNO_AUDIO_URL_PROD_HOTFIX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-2000:], file=sys.stderr)
        if "SUNO_AUDIO_URL_PROD_HOTFIX_OK" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
