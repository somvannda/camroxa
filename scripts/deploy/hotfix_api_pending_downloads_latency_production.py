#!/usr/bin/env python3
"""File-scoped production hotfix: unstick desktop Suno MP3 downloads.

Two related fixes:

1. ``GET /music/downloads/pending`` stayed under the desktop's 30s timeout by
   moving Suno reconcile + image-job healing to debounced background tasks and
   capping concurrent B2 URL resolution.
2. The reseller's ``audiostream.api.box`` "durable" host now answers 200
   audio/mpeg with a 0-byte body, so stored/stream URLs are rewritten to the
   working ``tempfile.aiquickdraw.com/r/<id>.mp3`` sibling and the dead host is
   blocklisted.

Allowlisted paths only. Does not sync other dirty workspace files.
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
    "platform_api/clients/suno_client.py",
    "platform_api/services/suno_audio_resolver.py",
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
  $REPO/platform_api/clients/suno_client.py \
  $REPO/platform_api/services/suno_audio_resolver.py \
  $REPO/docs/changelog/2026-10-02-pending-downloads-poll-latency.md
grep -n '_schedule_pending_reconcile\|_schedule_pending_image_jobs\|_PENDING_B2_RESOLVE_TIMEOUT_S' $REPO/platform_api/services/batch_service.py | head
if grep -q 'await self.reconcile_pending_suno_tasks(user_id=user_id, limit=max(limit, 10))' $REPO/platform_api/services/batch_service.py; then
  echo 'UNEXPECTED inline reconcile still present' && exit 1
fi
grep -n '_STREAM_HOST_MARKER' $REPO/platform_api/clients/suno_client.py | head
grep -n 'audiostream.api.box' $REPO/platform_api/services/suno_audio_resolver.py | head
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
