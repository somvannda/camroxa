#!/usr/bin/env python3
"""Run alembic upgrade head on sandbox and print migration status."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
set -e
REPO=/opt/camxora/repo
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head'
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT table_name, column_name FROM information_schema.columns WHERE column_name='genres' AND table_name IN ('music_descriptions','stream_albums','stream_tracks') ORDER BY table_name;"
systemctl is-active camxora-api
echo ALEMBIC_UPGRADE_DONE
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
