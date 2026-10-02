"""File-scoped production hotfix: signup email-domain guard (disposable blocklist + per-domain cap).

Ships platform_api/services/signup_domain_guard.py (new module), surgically
patches the live prod routers/auth.py register() (no whole-file upload), seeds
default system_settings rows (ON CONFLICT DO NOTHING), restarts camxora-api,
and verifies the guard logic with a fake-pool probe.

Provenance: only the small guard module is uploaded from scripts/deploy; the
router patch is applied in-place on the production tree.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

GUARD_MODULE_REMOTE = "/opt/camxora/repo/platform_api/services/signup_domain_guard.py"
AUTH_PY_REMOTE = "/opt/camxora/repo/platform_api/routers/auth.py"
REPO = "/opt/camxora/repo"


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


def load_guard_defaults() -> tuple[list[str], list[str]]:
    spec = importlib.util.spec_from_file_location(
        "_src_signup_domain_guard", DEPLOY / "_src_signup_domain_guard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DEFAULT_BLOCKED_DOMAINS, mod.DEFAULT_TRUSTED_DOMAINS


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    blocked, trusted = load_guard_defaults()
    blocked_json = json.dumps(blocked)
    trusted_json = json.dumps(trusted)
    print(f"Target production host: {host}")
    print(f"Blocked domains seeded: {len(blocked)}")
    print(f"Trusted domains seeded: {len(trusted)}")

    archive = Path(tempfile.mkdtemp(prefix="signup-guard-prod-")) / "guard.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(
            DEPLOY / "_src_signup_domain_guard.py",
            arcname="platform_api/services/signup_domain_guard.py",
        )

    cmd = """set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/signup-guard-prod.tar.gz -C $REPO
chown camxora:camxora /opt/camxora/repo/platform_api/services/signup_domain_guard.py
echo module_installed=$(test -f /opt/camxora/repo/platform_api/services/signup_domain_guard.py && echo yes || echo no)

# 2) backup live auth.py
TS=$(date +%Y%m%d-%H%M%S)
BAK=/opt/camxora/repo/platform_api/routers/auth.py.bak.signup-domain-guard-$TS
cp /opt/camxora/repo/platform_api/routers/auth.py $BAK
echo auth_backup=$BAK

# 3) surgical patch register() (idempotent)
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/routers/auth.py")
t = p.read_text(encoding="utf-8")
if "enforce_signup_domain_guard" in t:
    print("PATCH_ALREADY_PRESENT")
else:
    anchor = "    # Hash password and create user\\n"
    idx = t.find(anchor)
    assert idx != -1, "anchor not found"
    insert = (
        "    # Email-domain farm guard (music web): disposable blocklist + per-domain free-account cap\\n"
        "    if signup_product == PRODUCT_MUSIC_WEB:\\n"
        "        from platform_api.services.signup_domain_guard import enforce_signup_domain_guard\\n"
        "        await enforce_signup_domain_guard(request.email, signup_product)\\n"
        "\\n"
    )
    t = t[:idx] + insert + t[idx:]
    p.write_text(t, encoding="utf-8")
    print("PATCH_APPLIED")
PY

# 4) syntax check
python3 -m py_compile /opt/camxora/repo/platform_api/routers/auth.py /opt/camxora/repo/platform_api/services/signup_domain_guard.py
echo pycompile_ok

# 5) seed system_settings defaults (never overwrite admin edits)
sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO system_settings (key, value_type, value, updated_at) VALUES
('signup_blocked_email_domains', 'json', '__BLOCKED_JSON__', NOW()),
('signup_trusted_email_domains', 'json', '__TRUSTED_JSON__', NOW()),
('signup_max_free_accounts_per_domain', 'int', '3', NOW())
ON CONFLICT (key) DO NOTHING;
SQL
echo settings_seeded

# 6) restart + health
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

# 7) verify patch site + settings presence
grep -n "enforce_signup_domain_guard" /opt/camxora/repo/platform_api/routers/auth.py | head -3
sudo -u postgres psql -d camxora_platform -P pager=off -c "SELECT key, value_type, left(value, 60) AS value FROM system_settings WHERE key LIKE 'signup_%' ORDER BY key;"

# 8) logic probe with fake pool (no accounts created)
cd /opt/camxora/repo/platform_api
python3 -u - <<'PY'
import asyncio, json, sys
sys.path.insert(0, "/opt/camxora/repo")
import platform_api.services.signup_domain_guard as g
import platform_api.dependencies as deps

class FakePool:
    def __init__(self, settings, count):
        self._s = settings
        self._count = count
    async def fetchval(self, query, *params):
        if params and params[0] in self._s:
            return self._s[params[0]]
        return self._count

SETTINGS = {
    "signup_blocked_email_domains": json.dumps(["bowlfuel.com", "beiwoh.com"]),
    "signup_trusted_email_domains": json.dumps(["gmail.com", "camxora.com"]),
    "signup_max_free_accounts_per_domain": "3",
}

def run(case, coro, expect):
    try:
        asyncio.run(coro())
        ok = expect == "allow"
    except Exception as e:
        msg = str(e)
        ok = (expect == "raise" and "not allowed" in msg) or (expect == "capped" and "Too many free" in msg)
    print(("PASS" if ok else "FAIL"), case)
    if not ok:
        sys.exit(1)

async def c1(): await g.enforce_signup_domain_guard("probe1@bowlfuel.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 0)
run("blocked-domain rejected", c1, "raise")

async def c2(): await g.enforce_signup_domain_guard("user@gmail.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 0)
run("trusted-domain allowed", c2, "allow")

async def c3(): await g.enforce_signup_domain_guard("user@unknownfarm.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 3)
run("over-cap rejected", c3, "capped")

async def c4(): await g.enforce_signup_domain_guard("user@unknownfarm2.com", "music_web")
deps.get_db_pool = lambda: FakePool(SETTINGS, 2)
run("under-cap allowed", c4, "allow")

async def c5(): await g.enforce_signup_domain_guard("probe1@bowlfuel.com", "studio")
run("non-music product skipped", c5, "allow")

async def c6(): await g.enforce_signup_domain_guard("", "music_web")
run("empty email ignored", c6, "allow")

async def c7(): await g.enforce_signup_domain_guard("user@camxora.com", "music_web")
run("own-domain trusted allowed", c7, "allow")
print("GUARD_PROBE_ALL_OK")
PY
echo PROD_HOTFIX_DONE
"""
    cmd = cmd.replace("__BLOCKED_JSON__", blocked_json).replace("__TRUSTED_JSON__", trusted_json)

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/signup-guard-prod.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
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
