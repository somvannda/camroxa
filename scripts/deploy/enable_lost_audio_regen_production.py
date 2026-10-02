#!/usr/bin/env python3
"""Production: allow retry-suno for songs whose audio is permanently lost.

File-scoped patch to platform_api/services/batch_service.py only:
  _assert_song_allows_suno_retry() gains a terminal-lost allowance. A song whose
  latest Suno task has download_unavailable_ok/alt=true (Suno link gone, no B2
  copy) may be regenerated.

Backs up, py_compiles, import dry-runs, and only restarts camxora-api if the
dry-run passes. Refuses non-production hosts. Pass --apply.
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
cp -p $API/services/batch_service.py $API/services/batch_service.py.pre-lostregen-$STAMP.bak

echo "--- 2. patch ---"
python3 - <<'PY'
from pathlib import Path

path = Path("/opt/camxora/repo/platform_api/services/batch_service.py")
text = path.read_text(encoding="utf-8")
needle = (
    '        raise ValidationError(\n'
    '            "Only songs with draft_ready or suno_failed status can submit Suno.",\n'
    '            details={"status": song.status},\n'
    '        )'
)
count = text.count(needle)
if count != 1:
    raise SystemExit(f"PATCH_FAIL: needle count={count} (expected 1)")
if "download_unavailable_ok" in text and "_lost_row" in text:
    raise SystemExit("PATCH_SKIP: already patched")
insert = (
    '        # Lost audio (Suno link expired, no durable B2 copy) may be regenerated.\n'
    '        try:\n'
    '            from platform_api.dependencies import get_db_pool\n'
    '\n'
    '            _lost_row = await get_db_pool().fetchrow(\n'
    '                "SELECT download_unavailable_ok, download_unavailable_alt "\n'
    '                "FROM suno_tasks WHERE song_id = $1 ORDER BY created_at DESC LIMIT 1",\n'
    '                song.id,\n'
    '            )\n'
    '        except Exception:\n'
    '            _lost_row = None\n'
    '        if _lost_row is not None and (\n'
    '            bool(_lost_row["download_unavailable_ok"])\n'
    '            or bool(_lost_row["download_unavailable_alt"])\n'
    '        ):\n'
    '            return\n'
)
path.write_text(text.replace(needle, insert + needle), encoding="utf-8")
print("PATCH_OK")
PY
chown camxora:camxora $API/services/batch_service.py

echo "--- 3. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile services/batch_service.py"
echo COMPILE_OK

echo "--- 4. import dry-run ---"
sudo -u camxora env PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python -c "import platform_api.services.batch_service; print('IMPORT_OK')"

echo "--- 5. restart camxora-api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Application startup|Started server" | tail -5 || true
echo LOST_REGEN_PATCH_DONE
'''

VERIFY_CMD = r'''
cd /opt/camxora/repo/platform_api
python3 - <<'PY'
from pathlib import Path
text = Path("services/batch_service.py").read_text(encoding="utf-8")
print("HAS_LOST_ALLOWANCE", "download_unavailable_ok" in text and "_lost_row" in text)
PY
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== enable lost-audio regen [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, out, err = client.exec_command(VERIFY_CMD, timeout=60)
        print(out.read().decode("utf-8", errors="replace"))
        if not apply:
            print("DRY-RUN only; pass --apply to patch and restart camxora-api.")
            return 0
        _, stdout, stderr = client.exec_command(REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=False, timeout=300)
        o = stdout.read().decode("utf-8", errors="replace")
        e = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(o.encode("utf-8", errors="replace"))
        if e.strip():
            sys.stderr.write(e[-3000:] + "\n")
        if "IMPORT_OK" not in o:
            print("\nImport dry-run FAILED - API was NOT restarted. Restore .pre-lostregen-*.bak")
            return 1
        if "LOST_REGEN_PATCH_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
