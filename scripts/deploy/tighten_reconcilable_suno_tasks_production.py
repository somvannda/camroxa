#!/usr/bin/env python3
"""Production: stop futile re-polling in list_reconcilable_suno_tasks.

File-scoped patch to platform_api/repositories/batch_repo.py only.

The SUCCESS branch previously returned a task whenever a variant was missing a
URL and had an audio_id — even if that variant was already archived to B2. That
made every desktop poll re-poll Suno record-info forever. New condition: only
return a success task when a variant is missing its URL AND that variant has no
B2 copy yet.

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
cp -p $API/repositories/batch_repo.py $API/repositories/batch_repo.py.pre-reconcile-$STAMP.bak

echo "--- 2. patch ---"
python3 - <<'PY'
from pathlib import Path

path = Path("/opt/camxora/repo/platform_api/repositories/batch_repo.py")
text = path.read_text(encoding="utf-8")
needle = (
    '                  AND (\n'
    '                    (\n'
    "                      COALESCE(NULLIF(BTRIM(audio_url_ok), ''), NULL) IS NULL\n"
    "                      AND COALESCE(NULLIF(BTRIM(audio_url_alt), ''), NULL) IS NULL\n"
    '                    )\n'
    '                    OR (\n'
    "                      COALESCE(NULLIF(BTRIM(audio_url_ok), ''), NULL) IS NULL\n"
    "                      AND COALESCE(NULLIF(BTRIM(audio_id_ok), ''), NULL) IS NOT NULL\n"
    '                    )\n'
    '                    OR (\n'
    "                      COALESCE(NULLIF(BTRIM(audio_url_alt), ''), NULL) IS NULL\n"
    "                      AND COALESCE(NULLIF(BTRIM(audio_id_alt), ''), NULL) IS NOT NULL\n"
    '                    )\n'
    '                  )\n'
)
if text.count(needle) != 1:
    raise SystemExit(f"PATCH_FAIL: needle count={text.count(needle)}")
if "t.variant = 'ok'" in text and "list_reconcilable" in text:
    pass
replacement = (
    '                  AND (\n'
    '                    (\n'
    "                      COALESCE(NULLIF(BTRIM(audio_url_ok), ''), NULL) IS NULL\n"
    '                      AND NOT EXISTS (\n'
    '                        SELECT 1 FROM stream_tracks t\n'
    '                        WHERE t.suno_task_id = suno_tasks.id\n'
    "                          AND t.variant = 'ok'\n"
    "                          AND COALESCE(t.storage_key, '') <> ''\n"
    '                      )\n'
    '                    )\n'
    '                    OR (\n'
    "                      COALESCE(NULLIF(BTRIM(audio_url_alt), ''), NULL) IS NULL\n"
    '                      AND NOT EXISTS (\n'
    '                        SELECT 1 FROM stream_tracks t\n'
    '                        WHERE t.suno_task_id = suno_tasks.id\n'
    "                          AND t.variant = 'alt'\n"
    "                          AND COALESCE(t.storage_key, '') <> ''\n"
    '                      )\n'
    '                    )\n'
    '                  )\n'
)
path.write_text(text.replace(needle, replacement), encoding="utf-8")
print("PATCH_OK")
PY
chown camxora:camxora $API/repositories/batch_repo.py

echo "--- 3. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile repositories/batch_repo.py"
echo COMPILE_OK

echo "--- 4. import dry-run ---"
sudo -u camxora env PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python -c "import platform_api.repositories.batch_repo; print('IMPORT_OK')"

echo "--- 5. restart api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
echo RECONCILE_TIGHTEN_DONE
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== tighten list_reconcilable_suno_tasks [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
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
            print("\nImport dry-run FAILED - not restarted. Restore .pre-reconcile-*.bak")
            return 1
        if "RECONCILE_TIGHTEN_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
