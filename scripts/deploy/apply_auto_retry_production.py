#!/usr/bin/env python3
"""Production-only: deploy the streaming upload auto-retry (B2 capture) loop.

Files: streaming_repo.py, streaming_upload_service.py (local HEAD+feature), and
main.py built from PROD's own main.py with ONLY the auto-retry startup insertion
(see make_prod_main_patch.py / .dbg/prod-main-auto-retry.py).

Backs up, py_compiles, import dry-runs (including platform_api.main). On import
failure it restores the backups and does NOT restart. Refuses non-production.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
PATCHED_MAIN = ROOT / ".dbg" / "prod-main-auto-retry.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

FILES = [
    (ROOT / "platform_api/repositories/streaming_repo.py", "platform_api/repositories/streaming_repo.py"),
    (ROOT / "platform_api/services/streaming_upload_service.py", "platform_api/services/streaming_upload_service.py"),
    (PATCHED_MAIN, "platform_api/main.py"),
]

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
API=$REPO/platform_api
STAMP="%STAMP%"

echo "--- 1. backups ---"
for rel in repositories/streaming_repo.py services/streaming_upload_service.py main.py; do
  cp -p $API/$rel $API/$rel.pre-autoretry-$STAMP.bak
done
chown -R camxora:camxora $API/repositories/streaming_repo.py $API/services/streaming_upload_service.py $API/main.py

echo "--- 2. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile repositories/streaming_repo.py services/streaming_upload_service.py main.py"
echo COMPILE_OK

echo "--- 3. import dry-run incl. platform_api.main (restore on failure, no restart) ---"
cat > /tmp/import_check_main.py <<'PY'
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
import platform_api.services.streaming_upload_service  # noqa: E402,F401
import platform_api.main  # noqa: E402,F401
print("IMPORT_OK")
PY
if ! (cd /opt/camxora/repo && env PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -B /tmp/import_check_main.py); then
  echo IMPORT_FAILED_RESTORING
  for rel in repositories/streaming_repo.py services/streaming_upload_service.py main.py; do
    cp -p $API/$rel.pre-autoretry-$STAMP.bak $API/$rel
  done
  chown -R camxora:camxora $API
  exit 1
fi

echo "--- 4. restart camxora-api ---"
systemctl restart camxora-api
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL

echo "--- 5. auto-retry loop start log ---"
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "auto-retry|Traceback|ImportError|Started server|Uvicorn running" | tail -10 || true
echo APPLY_AUTORETRY_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Refusing: deploys the auto-retry loop to PRODUCTION.\n"
            "  python scripts/deploy/apply_auto_retry_production.py --i-mean-production"
        )
        return 2
    for local, _rel in FILES:
        if not local.is_file():
            raise FileNotFoundError(local)
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== apply streaming auto-retry on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes().replace(b"\r\n", b"\n"))
            print(f"Uploaded {rel}")
        sftp.close()
        _, stdout, stderr = client.exec_command(
            REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=False, timeout=600
        )
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-2500:] + "\n")
        if "IMPORT_OK" not in out:
            print("\nImport dry-run FAILED - backups restored, API NOT restarted.")
            return 1
        if "APPLY_AUTORETRY_DONE" not in out:
            print("\nDeploy did not finish cleanly.")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
