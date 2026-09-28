#!/usr/bin/env python3
"""File-scoped production hotfix: reject Range-stitch dumps of play/stream audio.

Uploads allowlisted API files only. Does not sync a full platform_api tree
and does not rebuild music_web.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path(r"G:\Developments\Projects\Camxora\MusicGenerator")
SCRIPT_DIR = Path(__file__).resolve().parent
_DEPLOY_CANDIDATES = [PRIMARY / "scripts" / "deploy", SCRIPT_DIR]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/exceptions.py",
    "platform_api/main.py",
    "platform_api/wire_dependencies.py",
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/stream_playback_guard.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_catalog_service.py",
    "platform_api/routers/web_music.py",
    "platform_api/routers/streaming_public.py",
]


def _run(client, cmd: str, timeout: int = 180) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== Stream stitch pace -> production ({host}) ===", flush=True)

    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/exceptions.py \
  $REPO/platform_api/main.py \
  $REPO/platform_api/wire_dependencies.py \
  $REPO/platform_api/services/audio_origin_proxy.py \
  $REPO/platform_api/services/stream_playback_guard.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/streaming_catalog_service.py \
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/routers/streaming_public.py
echo '=== verify guard ==='
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.services.stream_playback_guard import is_browser_audio_request, evaluate_unique_window_pace, PaceSnapshot; assert is_browser_audio_request({'Sec-Fetch-Dest': 'audio'}); d=evaluate_unique_window_pace(PaceSnapshot(frozenset(), ()), 0, now=1.0); print('IMPORT_OK', d.allowed)"
echo '=== restart api ==='
systemctl restart camxora-api
health=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  health=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$health
  if [ "$health" = "200" ]; then
    break
  fi
  sleep 2
done
test "$health" = "200"
echo STREAM_STITCH_PACE_PROD_DONE
""",
            timeout=180,
        )
        print(out.encode("ascii", errors="replace").decode("ascii"))
        log_path = SCRIPT_DIR / "deploy-stream-stitch-pace-production.log"
        log_path.write_text(out, encoding="utf-8")
        print(f"Logged full output to {log_path}", flush=True)
        print(f"exit={code}", flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
