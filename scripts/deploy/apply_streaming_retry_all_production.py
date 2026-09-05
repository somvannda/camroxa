#!/usr/bin/env python3
"""Production-only: add admin "retry all failed mp3" background sweep (API).

Additive patch to 3 files (verified identical to HEAD on prod except these
additions): streaming_repo.list_failed_mp3_job_ids, streaming_upload_service
retry-sweep manager, streaming_admin /upload-jobs/retry-all + /status.

Backs up, uploads, py_compiles, import dry-runs on the prod venv, and ONLY
restarts camxora-api if the dry-run passes. Refuses non-production hosts.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

FILES = [
    ("platform_api/repositories/streaming_repo.py", "streaming_repo.py"),
    ("platform_api/services/streaming_upload_service.py", "streaming_upload_service.py"),
    ("platform_api/routers/streaming_admin.py", "streaming_admin.py"),
]

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
API=$REPO/platform_api
STAMP="%STAMP%"

echo "--- 1. backups ---"
for rel in repositories/streaming_repo.py services/streaming_upload_service.py routers/streaming_admin.py; do
  cp -p $API/$rel $API/$rel.pre-retryall-$STAMP.bak
done
chown -R camxora:camxora $API/repositories $API/services $API/routers

echo "--- 2. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile repositories/streaming_repo.py services/streaming_upload_service.py routers/streaming_admin.py"
echo COMPILE_OK

echo "--- 3. import dry-run on prod venv (no restart if this fails) ---"
sudo -u camxora env PYTHONPATH=$REPO $API/.venv/bin/python -c "import platform_api.services.streaming_upload_service, platform_api.repositories.streaming_repo, platform_api.routers.streaming_admin; print('IMPORT_OK')"

echo "--- 4. route registration check ---"
sudo -u camxora env PYTHONPATH=$REPO $API/.venv/bin/python -c "from platform_api.routers.streaming_admin import router; paths = sorted({r.path for r in router.routes if 'upload-jobs' in getattr(r, 'path', '')}); print('ROUTES:', paths)"
echo ROUTE_CHECK_DONE

echo "--- 5. restart camxora-api ---"
systemctl restart camxora-api
sleep 6
systemctl is-active camxora-api
echo "--- api process/health ---"
ss -ltn 2>/dev/null | grep ':8100' || echo NO_LISTENER
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL
echo "--- workers ---"
systemctl cat camxora-api 2>/dev/null | grep -iE '^ExecStart|workers' || true
echo "--- log tail ---"
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Application startup|Uvicorn running|Started server" | tail -8 || true
echo APPLY_RETRYALL_API_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Refusing to run: this patches the PRODUCTION API.\n"
            "  python scripts/deploy/apply_streaming_retry_all_production.py --i-mean-production"
        )
        return 2
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== apply streaming retry-all patch on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel, _name in FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel}"
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {local.as_posix()} -> {remote}")
        sftp.close()
        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "IMPORT_OK" not in out:
            print("\nImport dry-run FAILED - API was NOT restarted. Restore with backups .pre-retryall-*.bak")
            return 1
        if "APPLY_RETRYALL_API_DONE" not in out:
            print("\nDeploy did not finish cleanly.")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
