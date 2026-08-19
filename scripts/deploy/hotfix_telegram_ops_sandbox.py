#!/usr/bin/env python3
"""File-scoped sandbox hotfix: Telegram ops activity feed.

Uploads only the new notifier module and inserts a startup hook into the
live main.py / worker.py so newer sandbox auth/billing files are left alone.
"""

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
    "platform_api/services/telegram_ops_alert_service.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Telegram ops feed -> sandbox ({host}) ===")

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
chown camxora:camxora $REPO/platform_api/services/telegram_ops_alert_service.py
python3 - <<'PY'
from pathlib import Path

MAIN_MARKER = "install_telegram_ops_hooks"
MAIN_NEEDLE = '            logger.info("Abuse alert service configured.")'
MAIN_INSERT = '''
            logger.info("Abuse alert service configured.")
        except Exception as exc:
            logger.warning("Abuse alert service not configured (non-fatal): %s", exc)

        try:
            from platform_api.services.telegram_ops_alert_service import (
                install_telegram_ops_hooks,
            )

            install_telegram_ops_hooks()
            logger.info("Telegram ops activity feed hooks installed.")
        except Exception as exc:
            logger.warning("Telegram ops hooks not installed (non-fatal): %s", exc)
'''
# The needle above already includes the following except-block in some trees.
# Insert after the whole abuse-alert try/except instead.

main_path = Path("/opt/camxora/repo/platform_api/main.py")
text = main_path.read_text(encoding="utf-8")
if MAIN_MARKER not in text:
    old = '''            logger.info("Abuse alert service configured.")
        except Exception as exc:
            logger.warning("Abuse alert service not configured (non-fatal): %s", exc)
'''
    new = '''            logger.info("Abuse alert service configured.")
        except Exception as exc:
            logger.warning("Abuse alert service not configured (non-fatal): %s", exc)

        try:
            from platform_api.services.telegram_ops_alert_service import (
                install_telegram_ops_hooks,
            )

            install_telegram_ops_hooks()
            logger.info("Telegram ops activity feed hooks installed.")
        except Exception as exc:
            logger.warning("Telegram ops hooks not installed (non-fatal): %s", exc)
'''
    if old not in text:
        raise SystemExit("Could not find abuse-alert insert point in main.py")
    main_path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Patched platform_api/main.py")
else:
    print("main.py already has Telegram ops hooks")

worker_path = Path("/opt/camxora/repo/platform_api/worker.py")
wtext = worker_path.read_text(encoding="utf-8")
if MAIN_MARKER not in wtext:
    wold = '''        logger.exception("Worker Redis unavailable — continuing without cache/rate gates.")
'''
    wnew = '''        logger.exception("Worker Redis unavailable — continuing without cache/rate gates.")

    try:
        from platform_api.services.telegram_ops_alert_service import (
            install_telegram_ops_hooks,
        )

        install_telegram_ops_hooks()
        logger.info("Worker Telegram ops hooks installed.")
    except Exception as exc:
        logger.warning("Worker Telegram ops hooks skipped: %s", exc)
'''
    if wold not in wtext:
        raise SystemExit("Could not find worker insert point in worker.py")
    worker_path.write_text(wtext.replace(wold, wnew, 1), encoding="utf-8")
    print("Patched platform_api/worker.py")
else:
    print("worker.py already has Telegram ops hooks")
PY
chown camxora:camxora $REPO/platform_api/main.py $REPO/platform_api/worker.py
grep -n "install_telegram_ops_hooks" $REPO/platform_api/main.py $REPO/platform_api/worker.py
systemctl restart camxora-api
systemctl list-units 'camxora-worker*' --type=service --state=running,failed,inactive --no-pager --no-legend \
  | awk '{print $1}' | while read -r unit; do
  case "$unit" in
    *.service) systemctl restart "$unit" || true ;;
  esac
done
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  if [ "$code" = "200" ]; then
    echo HEALTH_OK
    cat /tmp/sbx_health.json
    echo
    break
  fi
  sleep 2
done
systemctl is-active camxora-api
echo TELEGRAM_OPS_HOTFIX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
