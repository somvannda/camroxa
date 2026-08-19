#!/usr/bin/env python3
"""Restore Telegram ops /stats after a later main.py/config.py overwrite.

Re-uploads the notifier + command poller, re-inserts config fields and the
main.py startup hook, then restarts the API. File-scoped; no full tree sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "platform_api/services/telegram_ops_alert_service.py",
    "platform_api/services/telegram_ops_commands.py",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== Restore Telegram /stats -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/telegram_ops_alert_service.py \
  $REPO/platform_api/services/telegram_ops_commands.py
python3 -m py_compile \
  $REPO/platform_api/services/telegram_ops_alert_service.py \
  $REPO/platform_api/services/telegram_ops_commands.py
python3 - <<'PY'
from pathlib import Path

cfg_path = Path("/opt/camxora/repo/platform_api/config.py")
text = cfg_path.read_text(encoding="utf-8")
needle = '    cutluy_webhook_secret: str = ""\n'
insert = '''    cutluy_webhook_secret: str = ""

    # --- Ops Telegram activity feed ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_ops_enabled: bool = True
'''
if "telegram_bot_token" not in text:
    if needle not in text:
        raise SystemExit("Could not find cutluy_webhook_secret insert point in config.py")
    cfg_path.write_text(text.replace(needle, insert, 1), encoding="utf-8")
    print("Patched platform_api/config.py telegram settings")
else:
    print("config.py already has telegram fields")

MAIN_MARKER = "install_telegram_ops_hooks"
main_path = Path("/opt/camxora/repo/platform_api/main.py")
mtext = main_path.read_text(encoding="utf-8")
if MAIN_MARKER not in mtext:
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
    if old not in mtext:
        raise SystemExit("Could not find abuse-alert insert point in main.py")
    main_path.write_text(mtext.replace(old, new, 1), encoding="utf-8")
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
python3 -m py_compile $REPO/platform_api/config.py $REPO/platform_api/main.py $REPO/platform_api/worker.py
chown camxora:camxora $REPO/platform_api/config.py $REPO/platform_api/main.py $REPO/platform_api/worker.py
grep -n "telegram_bot_token\|install_telegram_ops_hooks\|start_telegram_ops_command_poller" \
  $REPO/platform_api/config.py \
  $REPO/platform_api/main.py \
  $REPO/platform_api/worker.py \
  $REPO/platform_api/services/telegram_ops_alert_service.py | head -20
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_tg_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then
    echo HEALTH_OK
    break
  fi
  sleep 2
done
test "$code" = "200"
journalctl -u camxora-api -n 80 --no-pager | grep -iE 'Telegram ops' | tail -10
echo TELEGRAM_STATS_RESTORED
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err[-1500:].encode("ascii", "replace").decode("ascii"))
        if "TELEGRAM_STATS_RESTORED" not in out:
            return 1
        if "HEALTH_OK" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
