#!/usr/bin/env python3
"""Backfill empty Music product tags and tag users on Music plan activation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
SUB_SVC = ROOT / ".dbg" / "sandbox_subscription_service.py"


def main() -> int:
    if not SUB_SVC.is_file():
        raise SystemExit(f"missing {SUB_SVC}")
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Backfill music_web tags -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote = "/opt/camxora/repo/platform_api/services/v2/subscription_service.py"
        with sftp.file(remote, "wb") as remote_file:
            remote_file.write(SUB_SVC.read_bytes())
        print(f"Uploaded {SUB_SVC.name}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/platform_api/services/v2/subscription_service.py
python3 -m py_compile $REPO/platform_api/services/v2/subscription_service.py
sudo -u postgres psql -d camxora_platform -c "
UPDATE users u
SET products = (
      SELECT ARRAY(
        SELECT DISTINCT unnest(COALESCE(u.products, '{}'::text[]) || ARRAY['music_web']::text[])
      )
    ),
    updated_at = NOW()
WHERE cardinality(COALESCE(u.products, '{}')) = 0
  AND EXISTS (
    SELECT 1 FROM web_subscriptions ws
    WHERE ws.user_id = u.id
  );
"
sudo -u postgres psql -d camxora_platform -c "SELECT email, products FROM users WHERE email='kongsomvannda1987@gmail.com';"
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
grep -n "ARRAY\['music_web'\]" $REPO/platform_api/services/v2/subscription_service.py | head
echo MUSIC_WEB_TAG_BACKFILL_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        stdout.channel.settimeout(120)
        sys.stdout.buffer.write(stdout.read())
        err = stderr.read()
        if err.strip():
            sys.stderr.buffer.write(err[-2000:] + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
