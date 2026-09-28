#!/usr/bin/env python3
"""File-scoped sandbox hotfix: Simple prompt follows Suno V5 limits."""

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
    "platform_api/routers/web_music.py",
    "platform_api/services/web_music_service.py",
    "music_web/src/components/create-page-client.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Simple prompt Suno limits -> sandbox ({host}) ===")

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
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/music_web/src/components/create-page-client.tsx
echo '=== verify limits ==='
grep -n 'prompt: str = Field(default="", max_length=5000)' $REPO/platform_api/routers/web_music.py | head -5
grep -n 'truncate_suno_style(safe_prompt)' $REPO/platform_api/services/web_music_service.py
grep -n 'WEB_MUSIC_STYLE_MAX' $REPO/music_web/src/components/create-page-client.tsx | head -10
systemctl restart camxora-api
sleep 4
systemctl is-active camxora-api
sudo -u camxora bash -lc 'export HOME=/home/camxora; cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 5
systemctl is-active camxora-music
echo SIMPLE_PROMPT_SUNO_LIMITS_DONE
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
        log_path = SCRIPT_DIR / "deploy-simple-prompt-suno-limits-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
        if "SIMPLE_PROMPT_SUNO_LIMITS_DONE" not in out:
            raise SystemExit("Sandbox simple-prompt limit deploy did not finish cleanly.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
