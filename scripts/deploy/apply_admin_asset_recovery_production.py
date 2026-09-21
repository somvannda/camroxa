#!/usr/bin/env python3
"""Production-only: rebuild admin portal with web-music asset recovery UI.

Uploads the two changed source files (v1-flavored stage copies from
.dbg/prod-admin-build, matching prod's pre-cutover /api/v1 API), backs up,
runs `npm run build` in /opt/camxora/repo/admin_portal, restarts
camxora-admin and verifies the new bundle contains the recover route.

Refuses non-production hosts. NO git commit / merge.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
STAGE = ROOT / ".dbg" / "prod-admin-build"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

FILES = [
    (STAGE / "src__hooks__use-streaming.ts", "admin_portal/src/hooks/use-streaming.ts"),
    (STAGE / "src__pages__streaming__upload-jobs.tsx", "admin_portal/src/pages/streaming/upload-jobs.tsx"),
]

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
ADMIN=$REPO/admin_portal
STAMP="%STAMP%"

echo "--- 1. backups ---"
cp -p $ADMIN/src/hooks/use-streaming.ts $ADMIN/src/hooks/use-streaming.ts.pre-assetrec-ui-$STAMP.bak
cp -p $ADMIN/src/pages/streaming/upload-jobs.tsx $ADMIN/src/pages/streaming/upload-jobs.tsx.pre-assetrec-ui-$STAMP.bak
chown -R camxora:camxora $ADMIN/src/hooks/use-streaming.ts $ADMIN/src/pages/streaming/upload-jobs.tsx

echo "--- 2. build admin ---"
sudo -u camxora bash -lc "cd $ADMIN && npm run build"
echo ADMIN_BUILD_OK

echo "--- 3. restart camxora-admin ---"
systemctl restart camxora-admin || true
sleep 3
systemctl is-active camxora-admin || true

echo "--- 4. verify bundle has recover route ---"
DIST=$(systemctl cat camxora-admin 2>/dev/null | grep -oE '[^ ]*dist' | head -1 || echo "$ADMIN/dist")
if grep -rl 'web-music-assets/recover' $DIST/assets/ 2>/dev/null | head -3; then
  echo BUNDLE_HAS_RECOVER
else
  echo BUNDLE_MISSING_RECOVER
fi
echo APPLY_ADMIN_ASSETREC_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Refusing to run: this rebuilds the PRODUCTION admin portal.\n"
            "  python scripts/deploy/apply_admin_asset_recovery_production.py --i-mean-production"
        )
        return 2
    for local, _rel in FILES:
        if not local.is_file():
            raise FileNotFoundError(local)
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== apply admin asset-recovery rebuild on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {local.as_posix()} -> {remote}")
        sftp.close()
        _, stdout, stderr = client.exec_command(
            REMOTE_CMD.replace("%STAMP%", STAMP), get_pty=True, timeout=1200
        )
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-2500:].encode("utf-8", errors="replace") + b"\n")
        if "APPLY_ADMIN_ASSETREC_DONE" not in out:
            print("\nAdmin rebuild did not finish cleanly.")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
