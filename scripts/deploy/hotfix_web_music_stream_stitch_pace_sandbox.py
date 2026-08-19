#!/usr/bin/env python3
"""File-scoped sandbox hotfix: reject Range-stitch dumps of play/stream audio."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
SCRIPT_DIR = Path(__file__).resolve().parent
_DEPLOY_CANDIDATES = [PRIMARY / "scripts" / "deploy", SCRIPT_DIR]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
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


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Stream stitch pace -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = r"""
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
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.services.stream_playback_guard import is_browser_audio_request, evaluate_unique_window_pace, PaceSnapshot; assert is_browser_audio_request({'Sec-Fetch-Dest': 'audio'}); d=evaluate_unique_window_pace(PaceSnapshot(frozenset(), ()), 0, now=1.0); print('IMPORT_OK', d.allowed)"
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/sandbox_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
systemctl is-active camxora-api
test "$code" = "200"
echo STREAM_STITCH_PACE_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
        if "STREAM_STITCH_PACE_DONE" not in out:
            raise SystemExit("Sandbox stream stitch pace deploy did not finish cleanly.")
        log_path = SCRIPT_DIR / "deploy-stream-stitch-pace-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
