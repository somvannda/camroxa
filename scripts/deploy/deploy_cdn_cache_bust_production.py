#!/usr/bin/env python3
"""Production: file-scoped deploy of CDN cache-busting for desktop MP3 downloads.

Uploads only storage_service.py + batch_service.py, sourced from a git ref
(default HEAD) so unrelated dirty working-tree edits are never shipped. Backs
up, py_compiles, import dry-runs, restores on failure, then restarts and health
checks. Refuses non-production hosts.

Usage:
  python deploy_cdn_cache_bust_production.py                 # dry-run
  python deploy_cdn_cache_bust_production.py --apply         # upload + restart
  python deploy_cdn_cache_bust_production.py --ref origin/main --apply
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")
FILES = (
    "platform_api/services/storage_service.py",
    "platform_api/services/batch_service.py",
)

REMOTE_CMD = r'''
set -e
API=/opt/camxora/repo/platform_api
STAMP="%STAMP%"

echo "--- 1. backup ---"
for f in services/storage_service.py services/batch_service.py; do
  cp -p "$API/$f" "$API/$f.pre-cdnbust-$STAMP.bak"
done

echo "--- 2. chown ---"
chown camxora:camxora "$API/services/storage_service.py" "$API/services/batch_service.py"

echo "--- 3. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile services/storage_service.py services/batch_service.py"
echo COMPILE_OK

echo "--- 4. import dry-run ---"
if ! sudo -u camxora env PYTHONPATH=/opt/camxora/repo "$API/.venv/bin/python" -c \
  "import platform_api.services.storage_service, platform_api.services.batch_service; print('IMPORT_OK')"; then
  echo "IMPORT_FAILED - restoring backups"
  for f in services/storage_service.py services/batch_service.py; do
    cp -p "$API/$f.pre-cdnbust-$STAMP.bak" "$API/$f"
  done
  chown camxora:camxora "$API/services/storage_service.py" "$API/services/batch_service.py"
  echo RESTORED
  exit 1
fi

echo "--- 5. restart camxora-api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Application startup|Started server" | tail -5 || true
echo CDNBUST_DEPLOY_DONE
'''


def _git_bytes(ref: str, rel: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{ref}:{rel}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout


def main() -> int:
    apply = "--apply" in sys.argv
    ref = "HEAD"
    if "--ref" in sys.argv:
        idx = sys.argv.index("--ref")
        if idx + 1 < len(sys.argv):
            ref = sys.argv[idx + 1]

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== CDN cache-bust prod deploy [{'APPLY' if apply else 'DRY-RUN'}] {host} ref={ref} ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        if not apply:
            for rel in FILES:
                print(f"{rel}: {len(_git_bytes(ref, rel))} bytes (from {ref})")
            print("DRY-RUN only; pass --apply to upload + restart.")
            return 0

        sftp = client.open_sftp()
        for rel in FILES:
            data = _git_bytes(ref, rel)
            print(f"Uploading {rel} ({len(data)} bytes)")
            with sftp.file(f"/opt/camxora/repo/{rel}", "wb") as remote_file:
                remote_file.write(data)
        sftp.close()

        _, stdout, stderr = client.exec_command(
            REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=False, timeout=300
        )
        o = stdout.read().decode("utf-8", errors="replace")
        e = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(o.encode("utf-8", errors="replace"))
        if e.strip():
            sys.stderr.write(e[-3000:] + "\n")
        if "IMPORT_OK" not in o:
            print("\nImport dry-run FAILED - API was NOT restarted. Backups restored.")
            return 1
        if "CDNBUST_DEPLOY_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
