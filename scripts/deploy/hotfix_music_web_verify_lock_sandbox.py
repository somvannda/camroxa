#!/usr/bin/env python3
"""Restore sandbox music_web auth files and lock verify-email without the sidebar."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DBG = ROOT / ".dbg" / "sandbox_music_web_auth"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"

UPLOADS = [
    (DBG / "auth-api.sandbox-original.ts", "music_web/src/lib/auth-api.ts"),
    (DBG / "layout.tsx.orig", "music_web/src/app/layout.tsx"),
    (DBG / "login-page.orig.tsx", "music_web/src/app/login/page.tsx"),
    (DBG / "register-page.orig.tsx", "music_web/src/app/register/page.tsx"),
    (DBG / "site-header.tsx.orig", "music_web/src/components/site-header.tsx"),
    (DBG / "likes-provider.tsx.orig", "music_web/src/components/likes-provider.tsx"),
    (DBG / "shell-switcher.patched.tsx", "music_web/src/components/shell-switcher.tsx"),
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Restore + lock verify-email -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, rel in UPLOADS:
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel} from {local.name}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
rm -f $REPO/music_web/src/components/app-chrome.tsx
rm -rf $REPO/music_web/src/app/confirm
chown -R camxora:camxora $REPO/music_web/src
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
grep -n "LockedAuthHeader\|needsConfirm" $REPO/music_web/src/components/shell-switcher.tsx
echo MUSIC_WEB_VERIFY_LOCK_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
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
        if "MUSIC_WEB_VERIFY_LOCK_DONE" not in out:
            raise SystemExit("Sandbox music_web verify lock did not finish cleanly.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
