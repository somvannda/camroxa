#!/usr/bin/env python3
"""Map prod ingest worker + asset upload/encryption code + systemd units."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r'''
set +e
echo '=== [1] systemd camxora units + active state ==='
systemctl list-units --type=service --all 2>/dev/null | grep -i camxora | head -15
echo
echo '=== [2] running python processes (workers?) ==='
ps aux | grep -iE 'worker|job|celery|rq|uvicorn|batch' | grep -v grep | head -20
echo
echo '=== [3] B2/upload/package/encrypt code sites (prod repo) ==='
REPO=/opt/camxora/repo/platform_api
grep -rn 'def schedule_web_music\|def schedule_.*upload\|b2_wav_storage\|b2_lrc_storage\|packaged_storage_key\|package_status\|def _encrypt\|def encrypt\|encrypt_suno\|camxora_ciphertext\|aes\|def _package' $REPO/services $REPO/jobs $REPO/workers 2>/dev/null | grep -v '.bak' | grep -iE 'def |class |encrypt|package|upload' | head -50
echo
echo '=== [4] files that likely run the worker ==='
ls $REPO/jobs 2>/dev/null; ls $REPO/workers 2>/dev/null; ls $REPO/scripts 2>/dev/null | head -20
echo MAP_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
