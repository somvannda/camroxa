#!/usr/bin/env python3
"""File-scoped production hotfix: keep GET /music/downloads/pending under 30s.

The desktop polls pending Suno MP3 downloads with a 30s httpx timeout. The
handler used to poll Suno per in-flight task and re-run image-job healing per
batch inline (plus sequential per-object B2 HEADs), which pushed the route past
30s — so clients stopped getting the list and never retried their MP3s.

Allowlisted path only. Does not sync other dirty workspace files.
Run only when explicitly asked for production.
"""
from __future__ import annotations

import sys
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
FILES = [
    "platform_api/services/batch_service.py",
    "docs/changelog/2026-10-02-pending-downloads-poll-latency.md",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== File-scoped pending-downloads latency hotfix -> production ({host}) ===")
    print(f"File source: {ROOT}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel}")
            sftp.put(str(local), remote)
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/batch_service.py \
  $REPO/docs/changelog/2026-10-02-pending-downloads-poll-latency.md
grep -n '_schedule_pending_reconcile\|_schedule_pending_image_jobs\|_PENDING_B2_RESOLVE_TIMEOUT_S' $REPO/platform_api/services/batch_service.py | head
if grep -q 'await self.reconcile_pending_suno_tasks(user_id=user_id, limit=max(limit, 10))' $REPO/platform_api/services/batch_service.py; then
  echo 'UNEXPECTED inline reconcile still present' && exit 1
fi
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
curl -sf -o /dev/null -w 'health:%{http_code}\n' https://api.camxora.com/health
echo PENDING_DOWNLOADS_HOTFIX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=90)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-2000:], file=sys.stderr)
        if "PENDING_DOWNLOADS_HOTFIX_OK" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
