#!/usr/bin/env python3
"""File-scoped production hotfix: Telegram ops activity feed.

Uploads only the notifier module, inserts startup hooks into live main.py /
worker.py, writes PLATFORM_TELEGRAM_* env, restarts API/workers, and sends a
test ping to the configured group. Does not tarball-sync platform_api.

Run only when explicitly asked for production.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from urllib.request import Request, urlopen

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
ENV_PATH = "/opt/camxora/repo/platform_api/.env"
FILES = [
    "platform_api/services/telegram_ops_alert_service.py",
]


def _secret(secrets: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (os.environ.get(key) or secrets.get(key) or "").strip()
        if value:
            return value
    return ""


def _send_test_ping(token: str, chat_id: str) -> None:
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": (
                "✅ CAMXORA production Telegram ops feed is on.\n"
                "This bot posts only to this group: signups, payments, "
                "and every credit spend (music / lyric / other), labeled FREE vs PAID.\n"
                "Turn off with PLATFORM_TELEGRAM_OPS_ENABLED=false."
            ),
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8", errors="replace")
    if '"ok":true' not in body.replace(" ", ""):
        raise SystemExit(f"Telegram test ping failed: {body[:300]}")
    print("Telegram test ping sent to Camxora Activities.")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    token = _secret(secrets, "TELEGRAM_BOT_TOKEN", "PLATFORM_TELEGRAM_BOT_TOKEN")
    chat_id = _secret(secrets, "TELEGRAM_CHAT_ID", "PLATFORM_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in "
            ".deploy/secrets.production.env"
        )

    print(f"=== Telegram ops feed -> production ({host}) chat={chat_id} ===")
    quoted_token = shlex.quote(token)
    quoted_chat = shlex.quote(chat_id)

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

        cmd = rf"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/platform_api/services/telegram_ops_alert_service.py
python3 -m py_compile $REPO/platform_api/services/telegram_ops_alert_service.py
python3 - <<'PY'
from pathlib import Path
path = Path("/opt/camxora/repo/platform_api/config.py")
text = path.read_text(encoding="utf-8")
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
    path.write_text(text.replace(needle, insert, 1), encoding="utf-8")
    print("Patched platform_api/config.py telegram settings")
else:
    print("config.py already has telegram fields")
PY
python3 -m py_compile $REPO/platform_api/config.py
chown camxora:camxora $REPO/platform_api/config.py
python3 - <<'PY'
from pathlib import Path

MAIN_MARKER = "install_telegram_ops_hooks"
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
ENV={ENV_PATH}
touch "$ENV"
upsert() {{
  key="$1"
  val="$2"
  if grep -q "^${{key}}=" "$ENV"; then
    sed -i "s|^${{key}}=.*|${{key}}=${{val}}|" "$ENV"
  else
    echo "${{key}}=${{val}}" >> "$ENV"
  fi
}}
upsert PLATFORM_TELEGRAM_BOT_TOKEN {quoted_token}
upsert PLATFORM_TELEGRAM_CHAT_ID {quoted_chat}
upsert PLATFORM_TELEGRAM_OPS_ENABLED true
grep -E '^PLATFORM_TELEGRAM_(CHAT_ID|OPS_ENABLED)=' "$ENV"
grep -n "install_telegram_ops_hooks" $REPO/platform_api/main.py $REPO/platform_api/worker.py
systemctl restart camxora-api
systemctl list-units 'camxora-worker*' --type=service --state=running,failed,inactive --no-pager --no-legend \
  | awk '{{print $1}}' | while read -r unit; do
  case "$unit" in
    *.service) systemctl restart "$unit" || true ;;
  esac
done
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  for port in 8000 8100; do
    code=$(curl -sS -m 3 -o /tmp/prod_tg_health.json -w '%{{http_code}}' http://127.0.0.1:$port/health || true)
    echo api_attempt_$i port=$port health=$code
    if [ "$code" = "200" ]; then
      echo HEALTH_OK
      cat /tmp/prod_tg_health.json
      echo
      break 2
    fi
  done
  sleep 2
done
test "$code" = "200"
systemctl is-active camxora-api
echo TELEGRAM_OPS_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
        if "TELEGRAM_OPS_PRODUCTION_DONE" not in out:
            return 1
        code = stdout.channel.recv_exit_status()
        if code != 0:
            return code
    finally:
        client.close()

    _send_test_ping(token, chat_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
