#!/usr/bin/env python3
"""File-scoped sandbox hotfix: require confirmed email to play/stream."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path(r"G:\Developments\Projects\Camxora\MusicGenerator")
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
    "platform_api/middleware/auth.py",
    "music_web/src/components/player-provider.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Confirmed-email listen gate -> sandbox ({host}) ===")

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
  $REPO/platform_api/middleware/auth.py \
  $REPO/music_web/src/components/player-provider.tsx
grep -n "_is_unconfirmed_play_path\|email_confirmed === false" \
  $REPO/platform_api/middleware/auth.py \
  $REPO/music_web/src/components/player-provider.tsx || true
test -z "$(grep -n _is_unconfirmed_play_path $REPO/platform_api/middleware/auth.py || true)"
grep -n "redirectToVerifyEmail" $REPO/music_web/src/components/player-provider.tsx
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/sandbox_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
systemctl is-active camxora-api
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
echo CONFIRMED_LISTEN_GATE_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        log_path = SCRIPT_DIR / "deploy-confirmed-listen-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        try:
            print(out)
            if err.strip():
                print(err)
        except UnicodeEncodeError:
            print(out.encode("ascii", errors="replace").decode("ascii"))
            if err.strip():
                print(err.encode("ascii", errors="replace").decode("ascii"))
        if "CONFIRMED_LISTEN_GATE_DONE" not in out:
            raise SystemExit("Sandbox confirmed-listen deploy did not finish cleanly.")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
