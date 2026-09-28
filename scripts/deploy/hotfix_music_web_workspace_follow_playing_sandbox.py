#!/usr/bin/env python3
"""File-scoped sandbox hotfix: Create workspace play/title/download UX."""

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
    "music_web/src/components/create-page-client.tsx",
    "platform_api/services/web_music_service.py",
    "platform_api/services/suno_audio_resolver.py",
    "platform_api/migrations/versions/106_web_music_stream_ready.py",
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
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/suno_audio_resolver.py \
  $REPO/platform_api/migrations/versions/106_web_music_stream_ready.py
grep -n "Finishing\|_ensure_stream_ready\|origin_audio_range_is_playable" \
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/suno_audio_resolver.py
timeout 20 sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c "
ALTER TABLE suno_tasks
  ADD COLUMN IF NOT EXISTS stream_ready_ok BOOLEAN,
  ADD COLUMN IF NOT EXISTS stream_ready_alt BOOLEAN;
UPDATE suno_tasks SET stream_ready_ok = TRUE
 WHERE stream_ready_ok IS NULL
   AND (NULLIF(BTRIM(COALESCE(audio_url_ok, '')), '') IS NOT NULL
        OR NULLIF(BTRIM(COALESCE(b2_storage_key_ok, '')), '') IS NOT NULL);
UPDATE suno_tasks SET stream_ready_alt = TRUE
 WHERE stream_ready_alt IS NULL
   AND (NULLIF(BTRIM(COALESCE(audio_url_alt, '')), '') IS NOT NULL
        OR NULLIF(BTRIM(COALESCE(b2_storage_key_alt, '')), '') IS NOT NULL);
"
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.services.suno_audio_resolver import origin_audio_range_is_playable, validate_wav_bytes; from platform_api.services.audio_origin_proxy import is_missing_range; print('IMPORT_OK')"
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
        log_path = SCRIPT_DIR / "deploy-music-web-workspace-follow-playing-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
