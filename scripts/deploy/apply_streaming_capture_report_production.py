#!/usr/bin/env python3
"""Production-only surgical hotfix: web-music MP3 capture + hourly Telegram report.

Production streaming files have diverged from every branch (extra WAV hotfixes
that were never committed). This script therefore does NOT overwrite them from
the repo. Instead it:

  1. Downloads prod's CURRENT streaming_repo.py / streaming_upload_service.py /
     main.py over SFTP.
  2. Extracts the new blocks from THIS branch's files and inserts them at unique
     anchors (purely additive; asserts each anchor is unique).
  3. Uploads the patched files plus the new streaming_health_report.py.
  4. Backs up, py_compiles, import dry-runs (incl. platform_api.main), restarts
     camxora-api, health-checks, and restores backups if the import fails.

Refuses non-production. Requires --i-mean-production.
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
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_SVC = "platform_api/services/streaming_upload_service.py"
REMOTE_REPO = "platform_api/repositories/streaming_repo.py"
REMOTE_MAIN = "platform_api/main.py"
REMOTE_HEALTH = "platform_api/services/streaming_health_report.py"
LOCAL_HEALTH = ROOT / "platform_api/services/streaming_health_report.py"

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
API=$REPO/platform_api
STAMP="%STAMP%"

echo "--- 1. backups ---"
for rel in services/streaming_upload_service.py repositories/streaming_repo.py main.py services/streaming_health_report.py; do
  if [ -f "$API/$rel" ]; then
    cp -p "$API/$rel" "$API/$rel.pre-capture-$STAMP.bak"
    echo "backed up $rel"
  fi
done
chown -R camxora:camxora $API/services/streaming_upload_service.py $API/repositories/streaming_repo.py $API/main.py $API/services/streaming_health_report.py

echo "--- 2. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile services/streaming_upload_service.py repositories/streaming_repo.py main.py services/streaming_health_report.py"
echo COMPILE_OK

echo "--- 3. import dry-run incl. platform_api.main (restore on failure, no restart) ---"
cat > /tmp/import_check_capture.py <<'PY'
import os
from pathlib import Path

path = Path("/opt/camxora/repo/platform_api/.env")
for line in path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip())

import platform_api.repositories.streaming_repo  # noqa: E402,F401
import platform_api.services.streaming_upload_service as s  # noqa: E402,F401
import platform_api.services.streaming_health_report  # noqa: E402,F401
import platform_api.main  # noqa: E402,F401
assert hasattr(s.StreamingUploadService, "run_web_music_mp3_recovery_pass")
assert hasattr(s.StreamingUploadService, "run_backfill_sweep")
assert hasattr(s, "run_streaming_auto_retry_loop")
print("IMPORT_OK")
PY
if ! (cd /opt/camxora/repo && env PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -B /tmp/import_check_capture.py); then
  echo IMPORT_FAILED_RESTORING
  for rel in services/streaming_upload_service.py repositories/streaming_repo.py main.py services/streaming_health_report.py; do
    if [ -f "$API/$rel.pre-capture-$STAMP.bak" ]; then
      cp -p "$API/$rel.pre-capture-$STAMP.bak" "$API/$rel"
    else
      rm -f "$API/$rel"
    fi
  done
  chown -R camxora:camxora $API
  exit 1
fi

echo "--- 4. restart camxora-api ---"
systemctl restart camxora-api
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL

echo "--- 5. startup log (report loop / tracebacks) ---"
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "health report|auto-retry|Traceback|ImportError|Started server|Uvicorn running" | tail -15 || true
echo APPLY_CAPTURE_DONE
'''


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def _slice(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def _insert_once(text: str, anchor: str, block: str, *, before: bool) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SystemExit(f"Remote anchor not unique ({count}): {anchor[:70]!r}")
    if before:
        return text.replace(anchor, block + anchor, 1)
    return text.replace(anchor, anchor + block, 1)


def build_service(prod: str) -> str:
    br = _read(ROOT / "platform_api/services/streaming_upload_service.py")
    env = _slice(br, "# Web-music MP3 capture.", "def _now_iso() -> str:")
    method = _slice(
        br,
        "    async def run_web_music_mp3_recovery_pass(",
        "    async def start_web_music_asset_recovery(",
    )
    loop = _slice(
        br,
        "        try:\n            web_recovered = await service.run_web_music_mp3_recovery_pass()",
        "        try:\n            started = await service.start_web_music_asset_recovery()",
    )
    prod = _insert_once(
        prod,
        '_ASSET_SRT_ENABLED = os.getenv("WEB_MUSIC_ASSET_SRT_ENABLED", "1") != "0"\n',
        "\n" + env,
        before=False,
    )
    prod = _insert_once(
        prod,
        "    async def start_web_music_asset_recovery(self) -> dict[str, Any]:",
        method,
        before=True,
    )
    prod = _insert_once(
        prod,
        '            logger.exception("Streaming auto-retry pass failed (non-fatal)")\n',
        loop,
        before=False,
    )
    return prod


def build_repo(prod: str) -> str:
    br = _read(ROOT / "platform_api/repositories/streaming_repo.py")
    consts = _slice(
        br,
        "# Periodic streaming-capture health report",
        "\n\nclass StreamingRepository:",
    )
    methods = _slice(
        br,
        "    async def count_failed_mp3_jobs_since(",
        "    async def list_web_music_asset_tasks(",
    )
    prod = _insert_once(
        prod,
        "ASSET_RECOVERY_ADVISORY_LOCK_ID = 730000003\n",
        "\n" + consts + "\n",
        before=False,
    )
    prod = _insert_once(
        prod,
        "    async def get_or_create_album(",
        methods,
        before=True,
    )
    return prod


def build_main(prod: str) -> str:
    br = _read(ROOT / "platform_api/main.py")
    block = _slice(
        br,
        "        # --- Streaming capture health report (Telegram, hourly) ---",
        "        # --- Warm Key Pool Redis cache ---",
    )
    return _insert_once(
        prod,
        "        # --- Warm Key Pool Redis cache ---",
        block,
        before=True,
    )


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Refusing: surgical hotfix for PRODUCTION streaming capture + report.\n"
            "  python scripts/deploy/apply_streaming_capture_report_production.py "
            "--i-mean-production"
        )
        return 2
    if not LOCAL_HEALTH.is_file():
        raise FileNotFoundError(LOCAL_HEALTH)
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== surgical streaming capture/report hotfix on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()

        def download(rel: str) -> str:
            with sftp.file(f"/opt/camxora/repo/{rel}", "r") as fh:
                return fh.read().decode("utf-8").replace("\r\n", "\n")

        print("Downloading prod sources...")
        prod_svc = download(REMOTE_SVC)
        prod_repo = download(REMOTE_REPO)
        prod_main = download(REMOTE_MAIN)

        print("Building additive patches...")
        patched = {
            REMOTE_SVC: build_service(prod_svc),
            REMOTE_REPO: build_repo(prod_repo),
            REMOTE_MAIN: build_main(prod_main),
            REMOTE_HEALTH: _read(LOCAL_HEALTH),
        }
        for rel, text in patched.items():
            with sftp.file(f"/opt/camxora/repo/{rel}", "wb") as fh:
                fh.write(text.encode("utf-8"))
            print(f"Uploaded {rel}")
        sftp.close()

        _, stdout, stderr = client.exec_command(
            REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=False, timeout=600
        )
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-3000:] + "\n")
        if "IMPORT_OK" not in out:
            print("\nImport dry-run FAILED - backups restored, API NOT restarted.")
            return 1
        if "APPLY_CAPTURE_DONE" not in out:
            print("\nHotfix did not finish cleanly.")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
