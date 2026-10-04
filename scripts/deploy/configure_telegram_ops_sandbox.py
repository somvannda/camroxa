#!/usr/bin/env python3
"""Write Telegram ops bot env on sandbox, restart API, optionally send a ping.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from .deploy/secrets.sandbox.env
(or the process environment). Never prints the token.

Note: the ops feed is production-only at runtime
(`platform_api.services.telegram_ops_alert_service`), so configuring sandbox no
longer makes it post. The test ping is therefore opt-in: set
SANDBOX_TELEGRAM_PING=1 to deliberately send one message to the shared channel.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

SANDBOX_HOST = "46.250.235.83"
ENV_PATH = "/opt/camxora/repo/platform_api/.env"


def _secret(secrets: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (os.environ.get(key) or secrets.get(key) or "").strip()
        if value:
            return value
    return ""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")

    token = _secret(secrets, "TELEGRAM_BOT_TOKEN", "PLATFORM_TELEGRAM_BOT_TOKEN")
    chat_id = _secret(secrets, "TELEGRAM_CHAT_ID", "PLATFORM_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in "
            ".deploy/secrets.sandbox.env (or environment)."
        )
        print(
            "Create a bot with @BotFather, add it to the group, disable privacy, "
            "then add those two keys and re-run."
        )
        return 1

    print(f"=== Telegram ops feed -> sandbox ({host}) chat={chat_id} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    quoted_token = shlex.quote(token)
    quoted_chat = shlex.quote(chat_id)
    cmd = f"""
set -e
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
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
echo TELEGRAM_OPS_ENV_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    if code != 0:
        return code

    # The runtime no longer posts from sandbox; only ping when explicitly asked
    # so this script cannot silently spam the shared production ops channel.
    if (os.environ.get("SANDBOX_TELEGRAM_PING") or "").strip() not in {"1", "true", "yes"}:
        print(
            "Sandbox Telegram ops delivery stays off (production-only runtime gate). "
            "Set SANDBOX_TELEGRAM_PING=1 to send one test message anyway."
        )
        return 0

    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": "✅ CAMXORA sandbox Telegram ops feed test ping (manual).",
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
    print("Telegram test ping sent.")
    if '"ok":true' not in body.replace(" ", ""):
        print(body[:300])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
