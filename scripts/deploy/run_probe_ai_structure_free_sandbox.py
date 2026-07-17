#!/usr/bin/env python3
"""Run AI Structure Free lyric provider probe on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTE_JSON = "/opt/camxora/repo/docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.json"
REMOTE_PROBE = "/opt/camxora/repo/platform_api/scripts/probe_ai_structure_free_lyrics.py"
LOCAL_JSON = REPO_ROOT / "docs" / "AI_STRUCTURE_FREE_PROVIDER_PROBE.json"
LOCAL_PROBE = REPO_ROOT / "platform_api" / "scripts" / "probe_ai_structure_free_lyrics.py"

REMOTE = rf"""
sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && unset PLATFORM_CORS_ORIGINS && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python platform_api/scripts/probe_ai_structure_free_lyrics.py --output {REMOTE_JSON}'
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    sftp = client.open_sftp()
    sftp.put(str(LOCAL_PROBE), REMOTE_PROBE)
    sftp.close()

    _, stdout, stderr = client.exec_command(REMOTE, timeout=900)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("STDERR:", err)
    code = stdout.channel.recv_exit_status()

    sftp = client.open_sftp()
    LOCAL_JSON.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(REMOTE_JSON, str(LOCAL_JSON))
        print(f"Downloaded probe results to {LOCAL_JSON}")
    except OSError as exc:
        print(f"Failed to download probe JSON: {exc}")
        sftp.close()
        client.close()
        return code or 1
    sftp.close()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
