#!/usr/bin/env python3
"""File-scoped sandbox hotfix: embed Khmer OS Siemreap on music_web."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
SCRIPT_DIR = Path(__file__).resolve().parent
_DEPLOY_CANDIDATES = [PRIMARY / "scripts" / "deploy", SCRIPT_DIR]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "music_web/package.json",
    "music_web/package-lock.json",
    "music_web/tailwind.config.js",
    "music_web/src/app/layout.tsx",
    "music_web/src/app/globals.css",
    "music_web/src/lib/khmer-text.ts",
    "music_web/src/components/synced-lyrics.tsx",
    "music_web/src/components/track-row.tsx",
    "music_web/src/components/player-bar.tsx",
    "music_web/src/components/now-playing-rail.tsx",
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/components/playlist-detail-page-client.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Khmer OS Siemreap font -> sandbox ({host}) ===")

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
  $REPO/music_web/package.json \
  $REPO/music_web/package-lock.json \
  $REPO/music_web/tailwind.config.js \
  $REPO/music_web/src/app/layout.tsx \
  $REPO/music_web/src/app/globals.css \
  $REPO/music_web/src/lib/khmer-text.ts \
  $REPO/music_web/src/components/synced-lyrics.tsx \
  $REPO/music_web/src/components/track-row.tsx \
  $REPO/music_web/src/components/player-bar.tsx \
  $REPO/music_web/src/components/now-playing-rail.tsx \
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/music_web/src/components/playlist-detail-page-client.tsx
grep -n "siemreap\|Siemreap\|khmer-text" \
  $REPO/music_web/package.json \
  $REPO/music_web/src/app/layout.tsx \
  $REPO/music_web/src/app/globals.css \
  $REPO/music_web/tailwind.config.js \
  $REPO/music_web/src/lib/khmer-text.ts
sudo -u camxora bash -lc 'export HOME=/home/camxora; cd /opt/camxora/repo/music_web && npm install --no-audit --no-fund && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
python3 - <<'PY'
import subprocess, time
for _ in range(8):
    try:
        html = subprocess.check_output(["curl", "-sf", "http://127.0.0.1:3102/"], text=True)
        print("local_home_ok", len(html) > 200)
        break
    except subprocess.CalledProcessError:
        time.sleep(1)
else:
    raise SystemExit("music_web not responding on :3102")
PY
echo KHMER_SIEMREAP_SANDBOX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        log_path = SCRIPT_DIR / "deploy-khmer-siemreap-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        try:
            print(out)
            if err.strip():
                print(err)
        except UnicodeEncodeError:
            print(out.encode("ascii", errors="replace").decode("ascii"))
            if err.strip():
                print(err.encode("ascii", errors="replace").decode("ascii"))
        if "KHMER_SIEMREAP_SANDBOX_DONE" not in out:
            raise SystemExit("Sandbox Khmer font deploy did not finish cleanly.")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
