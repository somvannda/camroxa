"""Sandbox-only: music web Free card no longer advertises Desktop studio."""

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
    "music_web/CHANGELOG.md",
    "music_web/src/components/pricing-page-client.tsx",
    "music_web/src/components/pricing-modal.tsx",
    "music_web/src/components/available-plans-grid.tsx",
    "music_web/src/lib/subscription-api.ts",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Music web Free bullets -> sandbox ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as handle:
                handle.write(local.read_bytes().replace(b"\r\n", b"\n"))
            print(f"uploaded {rel}")
        sftp.close()
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing production host
  exit 1
fi
chown -R camxora:camxora /opt/camxora/repo/music_web/src/components/pricing-page-client.tsx \
  /opt/camxora/repo/music_web/src/components/pricing-modal.tsx \
  /opt/camxora/repo/music_web/src/components/available-plans-grid.tsx \
  /opt/camxora/repo/music_web/src/lib/subscription-api.ts \
  /opt/camxora/repo/music_web/CHANGELOG.md
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
grep -n 'FREE_CARD_BULLETS' /opt/camxora/repo/music_web/src/lib/subscription-api.ts
echo MUSIC_WEB_FREE_BULLETS_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if "MUSIC_WEB_FREE_BULLETS_DONE" not in out:
            raise SystemExit("Music web Free-bullets sandbox deploy did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
