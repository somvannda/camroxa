#!/usr/bin/env python3
"""Read-only: pull live prod telegram files + map wiring."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
STAGE = Path(__file__).resolve().parent / "_sg_stage"

CMD = r"""
echo '=== telegram_ops_commands.py head/defs ==='
python3 - <<'PY'
from pathlib import Path
import re
p = Path("/opt/camxora/repo/platform_api/services/telegram_ops_commands.py")
t = p.read_text(encoding="utf-8", errors="replace")
print("lines=", len(t.splitlines()))
for i, line in enumerate(t.splitlines(), 1):
    if re.match(r"^(async )?def |^class |getUpdates|getWebhookInfo|setWebhook|deleteWebhook|callback|CallbackQuery|CommandHandler|Message|polling|run_forever|loop|while", line.strip()):
        print(i, line[:160])
PY
echo '=== who imports/launches telegram_ops_commands ==='
grep -rn "telegram_ops_commands\|telegram_ops_alert_service" /opt/camxora/repo/platform_api --include=*.py | grep -v ".bak" | head -20
echo '=== routers with telegram/webhook ==='
grep -rln "webhook\|Telegram" /opt/camxora/repo/platform_api/routers --include=*.py | head
echo '=== main.py / lifespan telegram bits ==='
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/main.py")
t = p.read_text(encoding="utf-8", errors="replace")
for i, line in enumerate(t.splitlines(), 1):
    if "telegram" in line.lower():
        print(i, line[:160])
PY
echo '=== systemd units for a bot/commands process ==='
systemctl list-units --all 2>/dev/null | grep -iE 'telegram|camxora' | head -25
echo '=== systemd ExecStart of camxora-api (workers inline?) ==='
systemctl cat camxora-api 2>/dev/null | grep -E 'ExecStart|ExecStartPost' | head
echo '=== download the two files to stdout-checked paths (fetch locally via sftp after) ==='
ls -la /opt/camxora/repo/platform_api/services/telegram_ops_commands.py /opt/camxora/repo/platform_api/services/telegram_ops_alert_service.py
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
        sftp = client.open_sftp()
        for remote_rel, local_name in [
            ("services/telegram_ops_alert_service.py", "telegram_ops_alert_service.prod.py"),
            ("services/telegram_ops_commands.py", "telegram_ops_commands.prod.py"),
        ]:
            local = STAGE / local_name
            try:
                with sftp.open(f"/opt/camxora/repo/platform_api/{remote_rel}", "rb") as fh:
                    local.write_bytes(fh.read())
                print(f"downloaded {local_name}")
            except Exception as exc:  # noqa: BLE001
                print(f"MISS {remote_rel}: {exc}")
        sftp.close()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
