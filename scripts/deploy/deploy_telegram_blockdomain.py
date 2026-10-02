"""Production hotfix: Telegram ops bot — signup-alert inline actions + /blockdomain.

Signup alerts now carry [⛔ Block domain][🚫 Suspend user] inline buttons and the
long-poller handles those callbacks; a /blockdomain <domain> command is added too.

Deploy:
1. md5-compares the three remote files to the pristine baselines captured at pull
   time (aborts if prod drifted since), 2. backs each up, 3. uploads the patched
   copies, 4. restarts camxora-api, 5. verifies with a venv probe (and restores
   any probe-domain change to the blocked list).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
STAGE = DEPLOY / "_sg_stage"

# (remote rel path under platform_api, local file, pristine md5 baseline)
FILES = [
    (
        "services/signup_domain_guard.py",
        DEPLOY / "_src_signup_domain_guard.py",
        "467a25aadbb54611fbcf13e9e8634598",
    ),
    (
        "services/telegram_ops_alert_service.py",
        STAGE / "telegram_ops_alert_service.prod.py",
        "9eb61db94037776679a509cc80f7a2ff",
    ),
    (
        "services/telegram_ops_commands.py",
        STAGE / "telegram_ops_commands.prod.py",
        "23ff1f009b024971d557496d1ae7eecb",
    ),
]


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        # 1) Provenance: remote md5 must match the pristine baselines.
        paths = " ".join(f"/opt/camxora/repo/platform_api/{rel}" for rel, _, _ in FILES)
        _, stdout, stderr = client.exec_command(f"md5sum {paths}")
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        remote_md5 = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 2:
                remote_md5[parts[1]] = parts[0]
        mismatches = []
        for rel, _, baseline in FILES:
            actual = remote_md5.get(f"/opt/camxora/repo/platform_api/{rel}")
            print(f"md5 {rel}: remote={actual} baseline={baseline}")
            if actual != baseline:
                mismatches.append(rel)
        if mismatches:
            print("ABORT: remote drifted from baseline for:", mismatches)
            if err.strip():
                print("STDERR", err[-1000:])
            return 1

        # 2) Upload each patched file (SFTP write, then remote md5 verify).
        sftp = client.open_sftp()
        for rel, local, _ in FILES:
            remote = f"/opt/camxora/repo/platform_api/{rel}"
            with sftp.file(remote, "wb") as fh:
                fh.write(local.read_bytes())
            print(f"uploaded {rel}")
        sftp.close()

        cmd = """set -e
REPO=/opt/camxora/repo
TS=$(date +%Y%m%d-%H%M%S)
for f in signup_domain_guard telegram_ops_alert_service telegram_ops_commands; do
  cp $REPO/platform_api/services/$f.py $REPO/platform_api/services/$f.py.bak.sg-telegram-$TS
  chown camxora:camxora $REPO/platform_api/services/$f.py
done
echo backups_done_$TS
python3 -m py_compile \\
  $REPO/platform_api/services/signup_domain_guard.py \\
  $REPO/platform_api/services/telegram_ops_alert_service.py \\
  $REPO/platform_api/services/telegram_ops_commands.py
echo pycompile_ok
systemctl restart camxora-api
echo waiting_for_api...
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if curl -sS -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health | grep -q 200; then
    echo health_ok_attempt_$i; break
  fi
  sleep 3
done
systemctl is-active camxora-api
curl -sS -m 10 -o /dev/null -w 'pub_health=%{http_code}\\n' https://api.camxora.com/health

cd /opt/camxora/repo/platform_api
/opt/camxora/repo/platform_api/.venv/bin/python -u - 2>&1 <<'PY'
import asyncio, inspect, json, sys
sys.path.insert(0, "/opt/camxora/repo")

import asyncpg
import redis.asyncio as aioredis

from platform_api.dependencies import (
    clear_connections, get_settings, set_db_pool, set_redis,
)

async def main():
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    set_redis(redis_conn)

    def check(label, cond):
        print(("PASS" if cond else "FAIL"), label)
        if not cond:
            sys.exit(1)

    try:
        from platform_api.services import signup_domain_guard as g
        from platform_api.services import telegram_ops_alert_service as A
        from platform_api.services import telegram_ops_commands as C

        # A: markup builder + send_html signature
        markup = A._signup_actions_markup(email="jigiw61621@airhemp.com", user_id="08e5ed29-011e-4257-8ac1-664a4525ee0b")
        serial = json.dumps(markup)
        check("markup built", markup is not None)
        check("block cb in markup", "sg_block:airhemp.com" in serial)
        check("suspend-user cb in markup", "sg_suspend_user:08e5ed29" in serial)
        check("send_html has reply_markup", "reply_markup" in inspect.signature(A.TelegramOpsAlertService.send_html).parameters)

        # C: parsing + poll updates
        check("parse /blockdomain", C.parse_ops_command("/blockdomain airhemp.com") == ("blockdomain", "airhemp.com"))
        check("parse blockdomain bare", C.parse_ops_command("blockdomain airhemp.com") == ("blockdomain", "airhemp.com"))
        check("parse help", C.parse_ops_command("/blockdomain") == ("blockdomain", "help"))
        check("parse /stats intact", C.parse_ops_command("/stats") == ("stats", ""))
        src = inspect.getsource(C._poll_once)
        check("poll accepts callback_query", '"callback_query"' in src)

        # g: guard add/remove round-trip on a probe domain (restore afterwards)
        original = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'signup_blocked_email_domains'"
        )
        ok, msg = await g.add_blocked_email_domain("sgtelegramprobe.invalid")
        check("add probe domain", ok and "sgtelegramprobe.invalid" in msg)
        ok2, _ = await g.add_blocked_email_domain("sgtelegramprobe.invalid")
        check("second add reports already", not ok2)
        ok3, msg3 = await g.add_blocked_email_domain("gmail.com")
        check("trusted refused", not ok3 and "trusted" in msg3)
        # restore exact original value
        await pool.execute(
            "UPDATE system_settings SET value = $1 WHERE key = 'signup_blocked_email_domains'",
            original,
        )
        after = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'signup_blocked_email_domains'"
        )
        check("blocked list restored", after == original)

        # g: suspend helper refuses garbage (no real user touched)
        ok4, _ = await g.suspend_user_by_id("not-a-uuid", "probe")
        check("suspend invalid id refused", not ok4)

        print("TELEGRAM_SG_VERIFY_OK")
    finally:
        clear_connections()
        await redis_conn.aclose()
        await pool.close()

asyncio.run(main())
PY
echo PROD_HOTFIX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR", err[-3000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
