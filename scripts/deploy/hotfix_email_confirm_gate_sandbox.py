#!/usr/bin/env python3
"""File-scoped sandbox hotfix: lock unconfirmed users behind email confirmation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"

FILES = [
    "platform_api/middleware/auth.py",
    "platform_api/repositories/user_repo.py",
    "user_portal/src/components/auth/portal-marketing-shell.tsx",
    "user_portal/src/app/onboarding/wizard.tsx",
    "user_portal/src/components/dashboard/control-panel-provider.tsx",
    "user_portal/src/app/login/login-form.tsx",
    "user_portal/src/app/page.tsx",
    "music_web/src/lib/auth-api.ts",
    "music_web/src/app/confirm/page.tsx",
    "music_web/src/components/app-chrome.tsx",
    "music_web/src/app/layout.tsx",
    "music_web/src/components/site-header.tsx",
    "music_web/src/app/login/page.tsx",
    "music_web/src/app/register/page.tsx",
    "music_web/src/components/likes-provider.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Email confirm gate -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown -R camxora:camxora \
  $REPO/platform_api/middleware/auth.py \
  $REPO/platform_api/repositories/user_repo.py \
  $REPO/user_portal/src \
  $REPO/music_web/src

systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"

sudo -u camxora bash -lc 'cd /opt/camxora/repo/user_portal && npm run build'
systemctl restart camxora-portal
sleep 2
systemctl is-active camxora-portal

sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music

grep -n "Confirm your email before using Camxora" $REPO/platform_api/middleware/auth.py
test -f $REPO/music_web/src/app/confirm/page.tsx
echo EMAIL_CONFIRM_GATE_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        try:
            print(out)
        except UnicodeEncodeError:
            print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            try:
                print(err)
            except UnicodeEncodeError:
                print(err.encode("ascii", errors="replace").decode("ascii"))
        if "EMAIL_CONFIRM_GATE_DONE" not in out:
            raise SystemExit("Sandbox email confirm gate deploy did not finish cleanly.")
        log_path = DEPLOY / "deploy-email-confirm-gate-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
