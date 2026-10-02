#!/usr/bin/env python3
"""READ-ONLY: confirm suno_tasks columns used by asset recovery exist on prod."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

CMD = r'''
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT column_name FROM information_schema.columns WHERE table_name='suno_tasks' AND column_name IN ('b2_storage_key_ok','b2_storage_key_alt','b2_wav_storage_key_ok','b2_wav_storage_key_alt','wav_task_id_ok','wav_task_id_alt','wav_status_ok','wav_status_alt','b2_lrc_storage_key_ok','b2_lrc_storage_key_alt','package_status_ok','package_status_alt','instrumental','user_id','created_at','song_title') ORDER BY column_name;"
echo COLUMN_CHECK_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-1000:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
