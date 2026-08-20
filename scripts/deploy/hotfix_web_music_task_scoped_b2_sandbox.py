#!/usr/bin/env python3
"""File-scoped sandbox hotfix: task-scoped Create leftover B2 keys.

Uploads ingest/playability files only. Host must be 46.250.235.83.
Does not tar platform_api or touch production.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

SANDBOX_HOST = "46.250.235.83"

FILES = [
    "platform_api/exceptions.py",
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/stream_playback_guard.py",
    "platform_api/services/web_music_storage_keys.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/audio_package_service.py",
]


def _run(client, cmd: str, timeout: int = 120) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}", flush=True)

    for rel in FILES:
        if not (ROOT / rel).is_file():
            raise SystemExit(f"Missing source file: {rel}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}".replace("\\", "/")
            parent = remote.rsplit("/", 1)[0]
            _, stdout, _ = client.exec_command(f"mkdir -p {parent}")
            stdout.channel.recv_exit_status()
            print(f"Uploading {rel}", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        chown = " ".join(f"/opt/camxora/repo/{p}" for p in FILES)
        print("=== restart API ===", flush=True)
        code, out = _run(
            client,
            rf"""
set -e
chown camxora:camxora {chown}
systemctl restart camxora-api
sleep 5
systemctl is-active camxora-api
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && cd /opt/camxora/repo && /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.services.web_music_service import WebMusicService; print(\"import_ok\")"'
echo api_http=$(curl -sS -o /dev/null -w '%{{http_code}}' https://api.sandbox.camxora.com/health)
echo WEB_MUSIC_TASK_SCOPED_B2_SANDBOX_DONE
""",
            timeout=90,
        )
        text = out[-8000:] if len(out) > 8000 else out
        sys.stdout.buffer.write(text.encode("ascii", errors="replace") + b"\n")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
