#!/usr/bin/env python3
"""File-scoped sandbox hotfix: Create workspace play/title/download UX."""

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
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/lib/web-music-api.ts",
    "platform_api/services/web_music_service.py",
    "platform_api/clients/suno_client.py",
    "platform_api/services/suno_audio_resolver.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Workspace follow-playing -> sandbox ({host}) ===")

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
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/music_web/src/lib/web-music-api.ts \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/clients/suno_client.py \
  $REPO/platform_api/services/suno_audio_resolver.py
grep -n "CoverEqualizer\|_extract_suno_wav_url\|max_attempts = 30\|reject_mp4=False" \
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/platform_api/clients/suno_client.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/suno_audio_resolver.py
timeout 20 sudo -u postgres psql -d camxora_platform -c "ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS wav_task_id_ok TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS wav_task_id_alt TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS wav_url_ok TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS wav_url_alt TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS wav_status_ok TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS wav_status_alt TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS b2_wav_storage_key_ok TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS b2_wav_storage_key_alt TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS audio_id_ok TEXT; ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS audio_id_alt TEXT;"
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.clients.suno_client import parse_suno_wav_poll, extract_suno_wav_task_id; from platform_api.services.suno_audio_resolver import validate_wav_bytes; from platform_api.services.audio_origin_proxy import is_missing_range; print('IMPORT_OK', parse_suno_wav_poll({'code':404}))"
systemctl restart camxora-api
sleep 4
systemctl is-active camxora-api
sudo -u camxora bash -lc 'export HOME=/home/camxora; cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 5
systemctl is-active camxora-music
BUILD=$(cat /opt/camxora/repo/music_web/.next/BUILD_ID)
echo BUILD_ID=$BUILD
echo WORKSPACE_FOLLOW_PLAYING_DONE
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
        if "WORKSPACE_FOLLOW_PLAYING_DONE" not in out:
            raise SystemExit("Sandbox workspace follow-playing deploy did not finish cleanly.")
        log_path = DEPLOY / "deploy-music-web-workspace-follow-playing-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
