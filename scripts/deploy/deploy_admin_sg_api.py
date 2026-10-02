"""Production hotfix: add signup email-domain guard admin endpoints to routers/admin.py.

Uploads the append block (staged text), appends it to the live prod admin.py
(after a timestamped .bak), restarts camxora-api, then verifies the new
endpoints with a real admin token minted server-side.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
ADMIN_PY = "/opt/camxora/repo/platform_api/routers/admin.py"
APPEND_FILE = DEPLOY / "_sg_stage" / "admin_sg_append.py.txt"


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
    append_text = APPEND_FILE.read_text(encoding="utf-8")

    cmd = """set -e
REPO=/opt/camxora/repo
ADMIN=/opt/camxora/repo/platform_api/routers/admin.py

TS=$(date +%Y%m%d-%H%M%S)
BAK=$ADMIN.bak.signup-domain-guard-$TS
cp $ADMIN $BAK
echo admin_backup=$BAK

python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/routers/admin.py")
t = p.read_text(encoding="utf-8")
if "signup-domain-guard" in t:
    print("APPEND_ALREADY_PRESENT")
else:
    block = Path("/tmp/sg_admin_append.py").read_text(encoding="utf-8").strip()
    if not t.endswith("\\n"):
        t += "\\n"
    p.write_text(t + "\\n" + block + "\\n", encoding="utf-8")
    print("APPEND_APPLIED")
PY

python3 -m py_compile $ADMIN
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

# Verify with a real admin token minted server-side.
cd /opt/camxora/repo/platform_api
/opt/camxora/repo/platform_api/.venv/bin/python -u - <<'PY'
import asyncio, json, sys
sys.path.insert(0, "/opt/camxora/repo")

import asyncpg
import redis.asyncio as aioredis

from platform_api.dependencies import (
    clear_connections,
    get_auth_service,
    get_settings,
    get_user_repo,
    set_db_pool,
    set_redis,
)

BASE = "http://127.0.0.1:8100/api/v1/admin/signup-domain-guard"


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    set_redis(redis_conn)

    try:
        email_row = await pool.fetchval(
            "SELECT email FROM users WHERE role='admin' AND status='active' ORDER BY created_at LIMIT 1"
        )
        print("admin_email=" + (email_row or "NONE"))
        auth = get_auth_service()
        user_repo = get_user_repo()
        user = await user_repo.get_by_email(email_row)
        pair = await auth.issue_token_pair_for_user(user)

        import httpx

        headers = {"Cookie": f"camxora_access_token={pair.access_token}"}

        def show(label, resp):
            body = resp.text[:600]
            print(f"{label} status={resp.status_code} body={body}")
            if resp.status_code >= 400:
                print("VERIFY_FAIL_HTTP")
                sys.exit(1)

        with httpx.Client(base_url=BASE, headers=headers, timeout=15) as c:
            r = c.get("")
            show("GET config", r)
            cfg = r.json()
            assert cfg.get("max_free") == 3, "max_free != 3"
            assert any("bowlfuel.com" in d for d in cfg.get("blocked", [])), "bowlfuel not blocked"

            r = c.get("/accounts", params={"domain": "bowlfuel.com"})
            show("GET accounts bowlfuel.com", r)
            assert r.json().get("count") == 2, "bowlfuel count != 2"

            r = c.put("", json={"max_free": 3})
            show("PUT no-op max_free", r)

            r = c.put("", json={"blocked": cfg["blocked"] + ["sgprobe.invalid"]})
            show("PUT add sgprobe.invalid", r)
            assert "sgprobe.invalid" in r.json().get("blocked", []), "add failed"

            r = c.post("/domain-action", json={"domain": "sgprobe.invalid", "action": "block"})
            show("POST action block (idempotent)", r)

            r = c.post("/domain-action", json={"domain": "no.suchdomain.invalid", "action": "suspend"})
            show("POST action suspend no-op", r)
            assert r.json().get("affected_accounts") == 0

            r = c.post("/domain-action", json={"domain": "no.suchdomain.invalid", "action": "freeze", "hours": 24})
            show("POST action freeze no-op", r)
            assert r.json().get("affected_accounts") == 0

            r = c.post("/domain-action", json={"domain": "sgprobe.invalid", "action": "unblock"})
            show("POST action unblock", r)

            r = c.put("", json={"blocked": [d for d in cfg["blocked"] if d != "sgprobe.invalid"]})
            show("PUT remove sgprobe.invalid", r)
            assert "sgprobe.invalid" not in r.json().get("blocked", []), "cleanup failed"

        print("ADMIN_SG_VERIFY_OK")
        return 0
    finally:
        clear_connections()
        await redis_conn.aclose()
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
PY
echo PROD_HOTFIX_DONE
"""
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/sg_admin_append.py", "wb") as remote:
            remote.write(append_text.encode("utf-8"))
        sftp.close()

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
