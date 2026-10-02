#!/usr/bin/env python3
"""Production: preflight credits before enqueuing a Suno retry.

File-scoped patch to platform_api/services/batch_service.py only.

validate_song_suno_retry() gains a preflight_quotas_and_balance() call for the
music operation. Desktops were retrying failed songs on 0-credit accounts, so
every retry enqueued a job that died on InsufficientCreditsError (380 stuck
jobs). Now the endpoint fails fast with a clear error instead.

Backs up, py_compiles, import dry-runs, restarts api + workers only if the
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
cp -p $API/services/batch_service.py $API/services/batch_service.py.pre-retrycredit-$STAMP.bak

echo "--- 2. patch ---"
python3 - <<'PY'
from pathlib import Path

path = Path("/opt/camxora/repo/platform_api/services/batch_service.py")
text = path.read_text(encoding="utf-8")
needle = (
    '        if not title or not lyrics:\n'
    '            raise ValidationError(\n'
    '                "Song draft is incomplete. Retry draft generation first.",\n'
    '                details={"song_id": str(song_id)},\n'
    '            )\n'
)
count = text.count(needle)
if count != 1:
    raise SystemExit(f"PATCH_FAIL: needle count={count}")
if "preflight_quotas_and_balance" in text and "before a background Suno retry" in text and "Fail fast" in text:
    raise SystemExit("PATCH_SKIP: already patched")
insert = (
    '\n'
    '        # Fail fast when the account cannot pay for a Suno generation, instead of\n'
    '        # enqueueing a job guaranteed to fail on insufficient credits (desktops were\n'
    '        # retrying failed songs on 0-credit accounts in a loop).\n'
    '        if self._enforcement_service is not None:\n'
    '            routing_music = await self._ai_routing_service.resolve("music")\n'
    '            music_provider = str(getattr(routing_music, "provider", "") or "").strip()\n'
    '            suno_model = await self._resolve_suno_model(batch.user_id)\n'
    '            suno_price = await self._pricing_service.get_price(\n'
    '                music_provider,\n'
    '                "music",\n'
    '                self._normalize_suno_pricing_model(suno_model),\n'
    '            )\n'
    '            await self._enforcement_service.preflight_quotas_and_balance(\n'
    '                UUID(user_id),\n'
    '                batch.ok_profile_id,\n'
    '                "music",\n'
    '                min_credits=int(suno_price),\n'
    '            )\n'
)
path.write_text(text.replace(needle, needle + insert), encoding="utf-8")
print("PATCH_OK")
PY
chown camxora:camxora $API/services/batch_service.py

echo "--- 3. py_compile ---"
sudo -u camxora bash -lc "cd $API && .venv/bin/python -m py_compile services/batch_service.py"
echo COMPILE_OK

echo "--- 4. import dry-run ---"
sudo -u camxora env PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python -c "import platform_api.services.batch_service; print('IMPORT_OK')"

echo "--- 5. restart api + workers ---"
systemctl restart camxora-api
for unit in camxora-worker-draft@1 camxora-worker-draft@2 camxora-worker-draft@3 camxora-worker-draft@4 camxora-worker-suno@1 camxora-worker-suno@2 camxora-worker-images@1 camxora-worker-images@2; do
  systemctl restart "$unit" || true
done
sleep 6
systemctl is-active camxora-api
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
echo RETRY_CREDIT_PREFLIGHT_DONE
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== preflight credits before Suno retry [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
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
            print("\nImport dry-run FAILED - not restarted. Restore .pre-retrycredit-*.bak")
            return 1
        if "RETRY_CREDIT_PREFLIGHT_DONE" not in o:
            print("\nDeploy did not finish cleanly.")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
