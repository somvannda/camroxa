#!/usr/bin/env python3
"""Production: add an idempotency guard to _upload_mp3_variant.

File-scoped patch to platform_api/services/streaming_upload_service.py only.
Skips creating an upload job when the task+variant is already archived to B2,
which stops the repeated callback/reconcile job flood.

Backs up, py_compiles, import dry-runs, restarts camxora-api + workers only if
the dry-run passes. Refuses non-production hosts. Pass --apply.
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
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
API=/opt/camxora/repo/platform_api
STAMP="%STAMP%"
echo "--- 1. backup ---"
cp -p $API/services/streaming_upload_service.py $API/services/streaming_upload_service.py.pre-idem-$STAMP.bak

echo "--- 2. patch ---"
python3 - <<'PY'
from pathlib import Path

path = Path("/opt/camxora/repo/platform_api/services/streaming_upload_service.py")
text = path.read_text(encoding="utf-8")
needle = (
    '        job_id = await self._repo.create_upload_job(\n'
    '            user_id=user_id,\n'
    '            kind=f"mp3_{variant}",\n'
)
if text.count(needle) != 1:
    raise SystemExit(f"PATCH_FAIL: needle count={text.count(needle)}")
if "already archived to B2" in text:
    raise SystemExit("PATCH_SKIP: already guarded")
guard = (
    '        # Idempotency: skip if this task+variant is already archived to B2.\n'
    '        # Repeated callbacks/reconciles were re-creating jobs for the same track.\n'
    '        _already_archived = await self._pool.fetchval(\n'
    '            """\n'
    '            SELECT 1 FROM stream_tracks\n'
    '            WHERE suno_task_id = $1 AND variant = $2\n'
    '              AND COALESCE(storage_key, \'\') <> \'\'\n'
    '            LIMIT 1\n'
    '            """,\n'
    '            suno_task_id,\n'
    '            variant,\n'
    '        )\n'
    '        if _already_archived:\n'
    '            return\n'
    '\n'
)
path.write_text(text.replace(needle, guard + needle), encoding="utf-8")
print("PATCH_OK")
PY
chown camxora:camxora $API/services/streaming_upload_service.py

echo "--- 3. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile services/streaming_upload_service.py"
echo COMPILE_OK

echo "--- 4. import dry-run ---"
sudo -u camxora env PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python -c "import platform_api.services.streaming_upload_service; print('IMPORT_OK')"

echo "--- 5. restart api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
echo IDEM_GUARD_DONE
'''

VERIFY_CMD = r'''
cd /opt/camxora/repo/platform_api
python3 - <<'PY'
from pathlib import Path
text = Path("services/streaming_upload_service.py").read_text(encoding="utf-8")
print("HAS_IDEM_GUARD", "already archived to B2" in text)
PY
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== add upload idempotency guard [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, out, _ = client.exec_command(VERIFY_CMD, timeout=60)
        print(out.read().decode("utf-8", errors="replace"))
        if not apply:
            print("DRY-RUN only; pass --apply.")
            return 0
        _, stdout, stderr = client.exec_command(REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=False, timeout=300)
        o = stdout.read().decode("utf-8", errors="replace")
        e = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(o.encode("utf-8", errors="replace"))
        if e.strip():
            sys.stderr.write(e[-3000:] + "\n")
        if "IMPORT_OK" not in o:
            print("\nImport dry-run FAILED - not restarted. Restore .pre-idem-*.bak")
            return 1
        if "IDEM_GUARD_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
