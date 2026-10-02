#!/usr/bin/env python3
"""READ-ONLY: check prod telegram ops files + hook install + config."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DBG = ROOT / ".dbg" / "live-probe"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set +e
REPO=/opt/camxora/repo/platform_api
echo '=== services dir telegram files ==='
ls -la $REPO/services/ | grep -i telegram
echo
echo '=== alert service present? ==='
if [ -f $REPO/services/telegram_ops_alert_service.py ]; then echo ALERT_YES; wc -l $REPO/services/telegram_ops_alert_service.py; else echo ALERT_NO; fi
echo
echo '=== where hooks installed (main.py refs) ==='
grep -n 'install_telegram_ops_hooks\|telegram_ops_alert_service\|schedule_ops_message\|notify_' $REPO/main.py | head -20
echo
echo '=== does web_music_service import/use telegram ops? ==='
grep -n 'telegram' $REPO/services/web_music_service.py | head -10
echo
echo '=== config telegram keys ==='
grep -nE 'telegram|TELEGRAM' $REPO/config.py | head -20
echo TGPROBE_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=90)
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
