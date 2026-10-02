#!/usr/bin/env python3
"""Read-only: map the production Telegram ops subsystem for the blocklist button hotfix."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
echo '=== telegram-ish files ==='
ls /opt/camxora/repo/platform_api/services 2>/dev/null | grep -iE 'telegram|notify|bot'
ls /opt/camxora/repo/platform_api 2>/dev/null | grep -iE 'telegram|bot'
echo '=== where does SIGNUP text live ==='
grep -rn "SIGNUP" /opt/camxora/repo/platform_api --include=*.py | head -10
echo '=== signup notify callers ==='
grep -rn "notify_.*signup\|SIGNUP" /opt/camxora/repo/platform_api/routers/auth.py | head
echo '=== telegram service: bot entry points (defs) ==='
python3 - <<'PY'
from pathlib import Path
import re
for rel in ["services/telegram_ops_alert_service.py", "services/telegram_bot.py", "services/telegram_alert.py"]:
    p = Path("/opt/camxora/repo/platform_api") / rel
    if not p.exists():
        print(rel, "MISSING")
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    print("=== ", rel, "lines=", len(t.splitlines()))
    for i, line in enumerate(t.splitlines(), 1):
        if re.match(r"^(async )?def |^class |InlineKeyboard|CallbackQuery|callback_query|CommandHandler|MessageHandler|Updater|start_polling|setWebhook|send_message|edit_message|@router|APIRouter|answerCallbackQuery", line.strip()):
            print(i, line[:150])
PY
echo '=== signup alert function in telegram service ==='
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/services/telegram_ops_alert_service.py")
if p.exists():
    t = p.read_text(encoding="utf-8", errors="replace")
    for kw in ["def notify", "def format_ops_message", "SIGNUP", "signup", "kind ==", "kind in", "kind == 'signup'", "inline", "button", "reply_markup"]:
        idx = 0
        while True:
            i = t.find(kw, idx)
            if i == -1:
                break
            ln = t.count("\n", 0, i) + 1
            print(f"line {ln}: {t[i:i+120]!r}")
            idx = i + 1
PY
echo '=== telegram env knobs present? ==='
grep -E "TELEGRAM" /opt/camxora/repo/platform_api/.env | sed 's/=.*/=***/' | head -20
"""


def run_cmd(client, cmd: str, timeout: int = 60) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535)
            if not chunk:
                break
            out += chunk
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=60), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
