#!/usr/bin/env python3
"""File-scoped sandbox hotfix: package_plaintext lock + skip-if-ready."""

from __future__ import annotations

import sys
import time
from pathlib import Path

FILL_GAPS = Path(r"D:\Development\Projects\Electron\MusicGenerator-fill-gaps")
CODE_ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = Path(r"D:\Development\Projects\Electron\MusicGenerator")
if not (HOST_REPO / ".deploy" / "secrets.sandbox.env").is_file():
    HOST_REPO = CODE_ROOT
DEPLOY = HOST_REPO / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

SANDBOX_HOST = "46.250.235.83"
REL = "platform_api/services/audio_package_service.py"
LOCAL = FILL_GAPS / REL


def _run(client, cmd: str, timeout: int = 120) -> str:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    return stdout.read().decode("utf-8", errors="replace") + stderr.read().decode(
        "utf-8", errors="replace"
    )


def main() -> int:
    if not LOCAL.is_file():
        raise SystemExit(f"missing {LOCAL}")
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== package lock -> sandbox ({host}) ===", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        backup = _run(
            client,
            "test -f /opt/camxora/repo/platform_api/services/audio_package_service.py.bak-play-key "
            "|| cp -a /opt/camxora/repo/platform_api/services/audio_package_service.py "
            "/opt/camxora/repo/platform_api/services/audio_package_service.py.bak-play-key; "
            "wc -l /opt/camxora/repo/platform_api/services/audio_package_service.py; "
            "grep -c pg_advisory_lock /opt/camxora/repo/platform_api/services/audio_package_service.py || true",
        )
        print(backup, flush=True)
        sftp = client.open_sftp()
        remote = f"/opt/camxora/repo/{REL}"
        payload = LOCAL.read_bytes().replace(b"\r\n", b"\n")
        with sftp.file(remote, "wb") as rf:
            rf.write(payload)
        sftp.close()
        print(f"Uploaded {REL}", flush=True)
        out = _run(
            client,
            r"""
set -e
chown camxora:camxora /opt/camxora/repo/platform_api/services/audio_package_service.py
python3 -m py_compile /opt/camxora/repo/platform_api/services/audio_package_service.py
grep -n 'pg_advisory_lock\|_package_plaintext_body' /opt/camxora/repo/platform_api/services/audio_package_service.py | head
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
echo PACKAGE_LOCK_SANDBOX_DONE
""",
            timeout=90,
        )
        sys.stdout.write(out)
        if "PACKAGE_LOCK_SANDBOX_DONE" not in out:
            raise SystemExit("Sandbox hotfix did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
