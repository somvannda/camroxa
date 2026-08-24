#!/usr/bin/env python3
"""File-scoped sandbox hotfix: music-web checkout/top-up security tightening."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
SIBLING_VENV = ROOT.parent / "MusicGenerator" / "scripts" / "deploy" / ".venv" / "Lib" / "site-packages"
for candidate in (DEPLOY / ".venv" / "Lib" / "site-packages", SIBLING_VENV):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"

FILES = [
    "music_web/src/components/available-plans-grid.tsx",
    "music_web/src/components/pricing-modal.tsx",
    "music_web/src/components/pricing-page-client.tsx",
    "music_web/src/lib/subscription-api.ts",
]

def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Music web checkout security -> sandbox ({host}) ===")

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
chown camxora:camxora \
  $REPO/platform_api/services/v2/subscription-api.ts \
  $REPO/platform_api/services/v2/subscription_service.py \
  $REPO/platform_api/services/v2/topup_service.py \
  $REPO/platform_api/services/shared/cutluy_service.py \
  $REPO/platform_api/routers/v2_subscriptions.py \
  $REPO/platform_api/routers/v2_topups.py \
  $REPO/platform_api/middleware/rate_limit.py \
  $REPO/music_web/src/lib/subscription-api.ts \
  $REPO/music_web/src/components/cutluy-checkout-modal.tsx

echo skip_api_restart
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"

sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music

grep -n "external_subscription_id" $REPO/platform_api/services/v2/subscription_service.py | head
grep -n "isAllowedCutluyCheckoutUrl" $REPO/music_web/src/lib/subscription-api.ts
echo MUSIC_PRICING_DAILY_DONE
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
        if "MUSIC_PRICING_DAILY_DONE" not in out:
            raise SystemExit("Music pricing deploy did not finish cleanly.")
        log_path = DEPLOY / "deploy-music-web-pricing-daily-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
