#!/usr/bin/env python3
"""Production: fix the Suno callback URL path (v3 -> v1).

suno_client.py and suno_audio_resolver.py build callbacks as
``/api/v3/callbacks/...`` but the API only serves ``/api/v1/callbacks/...``,
so Suno's callbacks 404 and are retried forever. Replace the prefix in both
files. File-scoped; backs up, py_compiles, import dry-runs, restarts api +
workers only if the dry-run passes. Pass --apply.
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
echo "--- 1. backups + patch ---"
python3 - <<'PY'
from pathlib import Path

stamp = "%STAMP%"
targets = [
    Path("/opt/camxora/repo/platform_api/clients/suno_client.py"),
    Path("/opt/camxora/repo/platform_api/services/suno_audio_resolver.py"),
]
total = 0
for path in targets:
    text = path.read_text(encoding="utf-8")
    count = text.count("/api/v3/callbacks/")
    if count == 0:
        print("SKIP", path.name, "no v3 callback refs")
        continue
    (path.parent / (path.name + ".pre-cburl-" + stamp + ".bak")).write_text(text, encoding="utf-8")
    path.write_text(text.replace("/api/v3/callbacks/", "/api/v1/callbacks/"), encoding="utf-8")
    total += count
    print("PATCHED", path.name, "replacements", count)
print("TOTAL_REPLACEMENTS", total)
if total == 0:
    raise SystemExit("PATCH_FAIL: nothing replaced")
PY
chown camxora:camxora $API/clients/suno_client.py $API/services/suno_audio_resolver.py

echo "--- 2. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile clients/suno_client.py services/suno_audio_resolver.py"
echo COMPILE_OK

echo "--- 3. import dry-run ---"
sudo -u camxora env PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python -c "import platform_api.clients.suno_client, platform_api.services.suno_audio_resolver; print('IMPORT_OK')"

echo "--- 4. verify no v3 callback refs remain ---"
python3 - <<'PY'
from pathlib import Path
bad = []
for rel in ("clients/suno_client.py", "services/suno_audio_resolver.py"):
    t = Path("/opt/camxora/repo/platform_api/" + rel).read_text(encoding="utf-8")
    if "/api/v3/callbacks/" in t:
        bad.append(rel)
print("REMAINING_V3", bad)
PY

echo "--- 5. restart api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
echo CALLBACK_URL_FIX_DONE
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== fix suno callback URL v3->v1 [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
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
            print("\nImport dry-run FAILED - not restarted. Restore .pre-cburl-*.bak")
            return 1
        if "CALLBACK_URL_FIX_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
