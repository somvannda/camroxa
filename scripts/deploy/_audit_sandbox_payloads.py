"""Audit sandbox /api/v3 payloads for incomplete serializers (plans-style bug).

Compares live API JSON to DB truth and client-required field sets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402


REMOTE = r'''
import asyncio, asyncpg, jwt, json, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from platform_api.config import get_settings
from platform_api.dependencies import set_db_pool

ISSUES = []
OKS = []

def note_ok(msg):
    OKS.append(msg)
    print("OK ", msg)

def note_issue(msg):
    ISSUES.append(msg)
    print("ISSUE ", msg)

def get_json(url, token=None, ok=(200,)):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = resp.status
            data = json.loads(body) if body.strip() else None
            return code, data, body[:200]
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except Exception:
            data = None
        return exc.code, data, body[:300]

def first_item(payload):
    if isinstance(payload, list):
        return payload[0] if payload else None
    if isinstance(payload, dict):
        for key in ("items", "plans", "users", "licenses", "data", "results"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                return val[0]
        return payload
    return None

def require_keys(label, obj, keys):
    if not isinstance(obj, dict):
        note_issue(f"{label}: not an object ({type(obj).__name__})")
        return
    missing = [k for k in keys if k not in obj]
    if missing:
        note_issue(f"{label}: missing keys {missing}; have={sorted(obj.keys())[:40]}")
    else:
        note_ok(f"{label}: keys present ({len(keys)})")

def mint(pool, settings, email=None, role_prefer=None):
    if email:
        row = awaitable = None
    # sync helper replaced below
    raise RuntimeError("use mint_user")

async def mint_user(pool, settings, *, email=None, prefer_role=None):
    row = None
    if email:
        row = await pool.fetchrow(
            "SELECT id, email, role, token_version FROM users WHERE email=$1", email
        )
    if row is None and prefer_role:
        row = await pool.fetchrow(
            "SELECT id, email, role, token_version FROM users WHERE role=$1 ORDER BY created_at DESC LIMIT 1",
            prefer_role,
        )
    if row is None:
        row = await pool.fetchrow(
            "SELECT id, email, role, token_version FROM users ORDER BY created_at DESC LIMIT 1"
        )
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(row["id"]),
        "email": row["email"],
        "role": row["role"] or "user",
        "token_version": int(row["token_version"] or 0),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    if isinstance(token, bytes):
        token = token.decode()
    return dict(row), token

async def main():
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)

    admin_user, admin_token = await mint_user(pool, settings, prefer_role="admin")
    user_row, user_token = await mint_user(pool, settings, email="duke@test.com")
    print("admin", admin_user["email"], admin_user["role"])
    print("user", user_row["email"], user_row["role"])

    api = "https://api.sandbox.camxora.com"
    admin_proxy = "https://admin.sandbox.camxora.com"
    music_proxy = "https://music.sandbox.camxora.com"
    portal_proxy = "https://app.sandbox.camxora.com"
    website = "https://sandbox.camxora.com"

    # --- DB plan truth ---
    db_plans = await pool.fetch(
        """
        SELECT id::text AS id, name, monthly_credits, daily_credits, is_public, is_active,
               price_cents, plan_kind, plan_type, lyric_credits, music_credits
        FROM plans
        ORDER BY name
        """
    )
    db_by_id = {r["id"]: dict(r) for r in db_plans}
    print(f"db_plans={len(db_plans)}")

    # Fields that, if missing/wrong, cause UI to show Hidden / GRANT 0 (admin credits-only bug class).
    ADMIN_GRANT_FIELDS = (
        "monthly_credits", "daily_credits", "is_public", "is_active",
        "price_cents", "name",
    )
    PUBLIC_GRANT_FIELDS = ("monthly_credits", "daily_credits", "price_cents", "name")
    SUBS_GRANT_FIELDS = ("monthly_credits", "daily_credits", "price_cents", "name", "is_public")
    V3_EXTRA = (
        "lyric_credits", "title_credits", "album_credits", "music_credits",
        "style_credits", "image_credits", "video_credits", "merge_credits",
        "plan_kind", "plan_type",
    )

    # (label, url, token, compare_fields, need_v3_ops)
    plan_endpoints = [
        ("api.admin.plans", f"{api}/api/v3/admin/plans", admin_token, ADMIN_GRANT_FIELDS, True),
        ("api.plans.legacy", f"{api}/api/v3/plans", admin_token, ADMIN_GRANT_FIELDS, False),
        ("api.plans.public", f"{api}/api/v3/plans/public", None, PUBLIC_GRANT_FIELDS, False),
        ("api.subscriptions.plans", f"{api}/api/v3/subscriptions/plans", None, SUBS_GRANT_FIELDS, False),
        ("admin.proxy.admin.plans", f"{admin_proxy}/api/v3/admin/plans", admin_token, ADMIN_GRANT_FIELDS, True),
        ("music.proxy.subscriptions.plans", f"{music_proxy}/api/v3/subscriptions/plans", None, SUBS_GRANT_FIELDS, False),
        ("music.proxy.plans.public", f"{music_proxy}/api/v3/plans/public", None, PUBLIC_GRANT_FIELDS, False),
        ("portal.proxy.plans.public", f"{portal_proxy}/api/v3/plans/public", None, PUBLIC_GRANT_FIELDS, False),
    ]

    admin_plans_payload = None
    for label, url, token, compare_fields, need_v3_ops in plan_endpoints:
        code, data, snippet = get_json(url, token)
        if code != 200:
            note_issue(f"{label}: HTTP {code} {snippet}")
            continue
        plans = data
        if isinstance(data, dict) and "plans" in data:
            plans = data["plans"]
        if not isinstance(plans, list) or not plans:
            note_issue(f"{label}: empty or non-list")
            continue
        sample = plans[0]
        require_keys(f"{label}.sample", sample, ["id", "name", "price_cents"])
        mismatches = 0
        missing_field_rows = 0
        compared = 0
        for p in plans:
            pid = str(p.get("id") or "")
            db = db_by_id.get(pid)
            if not db:
                continue
            compared += 1
            for field in compare_fields:
                if field not in p:
                    missing_field_rows += 1
                    note_issue(f"{label}: plan {db['name']!r} missing field {field}")
                    break
                api_val = p[field]
                db_val = db[field]
                if field in ("monthly_credits", "daily_credits", "price_cents"):
                    if int(api_val or 0) != int(db_val or 0):
                        mismatches += 1
                        note_issue(
                            f"{label}: {db['name']}.{field} api={api_val} db={db_val}"
                        )
                elif field in ("is_public", "is_active"):
                    if bool(api_val) != bool(db_val):
                        mismatches += 1
                        note_issue(
                            f"{label}: {db['name']}.{field} api={api_val} db={db_val}"
                        )
                elif field == "name" and str(api_val) != str(db_val):
                    mismatches += 1
                    note_issue(f"{label}: name drift api={api_val!r} db={db_val!r}")
            if need_v3_ops:
                miss_ops = [k for k in V3_EXTRA if k not in p]
                if miss_ops:
                    note_issue(f"{label}: missing v3 fields {miss_ops} on {p.get('name')}")
        if "public" in label or "subscriptions" in label:
            nonzero = [
                p for p in plans
                if int(p.get("monthly_credits") or 0) > 0 or int(p.get("daily_credits") or 0) > 0
            ]
            if plans and not nonzero:
                pub_db = [r for r in db_plans if r["is_public"] and r["is_active"]]
                pub_nonzero = [
                    r for r in pub_db
                    if (r["monthly_credits"] or 0) > 0 or (r["daily_credits"] or 0) > 0
                ]
                if pub_nonzero:
                    note_issue(f"{label}: all plans show 0 credits but DB has public grants")
        if mismatches == 0 and missing_field_rows == 0:
            note_ok(f"{label}: {len(plans)} plans, compared {compared} vs DB (no grant mismatches)")
        if label == "api.admin.plans":
            admin_plans_payload = plans

    code, legacy, _ = get_json(f"{api}/api/v3/plans", admin_token)
    if code == 200 and isinstance(legacy, list) and legacy:
        sample = legacy[0]
        for f in ("monthly_credits", "daily_credits", "is_public"):
            if f not in sample:
                note_issue(f"api.plans.legacy: still omits {f} (credits-only bug class)")
            else:
                note_ok(f"api.plans.legacy includes {f}")

    code_p, public, _ = get_json(f"{api}/api/v3/plans/public")
    if code_p == 200 and isinstance(public, list) and admin_plans_payload:
        admin_by_id = {str(p["id"]): p for p in admin_plans_payload}
        drift = 0
        for p in public:
            a = admin_by_id.get(str(p["id"]))
            if not a:
                continue
            for f in ("monthly_credits", "daily_credits", "price_cents"):
                if int(p.get(f) or 0) != int(a.get(f) or 0):
                    drift += 1
                    note_issue(
                        f"admin<->public drift on {p.get('name')}.{f}: public={p.get(f)} admin={a.get(f)}"
                    )
            if str(p.get("name")) != str(a.get("name")):
                drift += 1
                note_issue(f"admin<->public name drift {p.get('name')} vs {a.get('name')}")
        if drift == 0:
            note_ok("admin<->public: grant fields aligned for overlapping IDs")

    # --- Auth / wallet shapes used by music + portal ---
    wallet_checks = [
        ("api.me.credits", f"{api}/api/v3/me/credits", user_token,
         ["balance_credits", "grant_remaining_credits", "lots"]),
        ("api.credits.balance", f"{api}/api/v3/credits/balance", user_token,
         ["total_credits", "monthly_credits", "topup_credits"]),
        ("api.web_music.quota", f"{api}/api/v3/web-music/quota", user_token,
         []),  # flexible
        ("api.users.me", f"{api}/api/v3/users/me", user_token, ["id", "email"]),
        ("music.me.credits", f"{music_proxy}/api/v3/me/credits", user_token,
         ["balance_credits", "grant_remaining_credits"]),
        ("portal.me.credits", f"{portal_proxy}/api/v3/me/credits", user_token,
         ["balance_credits", "grant_remaining_credits"]),
    ]
    for label, url, token, keys in wallet_checks:
        code, data, snippet = get_json(url, token)
        if code != 200:
            note_issue(f"{label}: HTTP {code} {snippet}")
            continue
        if keys:
            require_keys(label, data if isinstance(data, dict) else first_item(data), keys)
        else:
            note_ok(f"{label}: HTTP 200")
        # plan nested object if present should have monthly/daily when plan exists
        if isinstance(data, dict) and isinstance(data.get("plan"), dict):
            plan = data["plan"]
            for f in ("monthly_credits", "daily_credits"):
                if f not in plan:
                    note_issue(f"{label}.plan missing {f}; keys={sorted(plan.keys())}")
                else:
                    note_ok(f"{label}.plan has {f}={plan.get(f)}")

    # --- Marketplace admin list ---
    for label, url in (
        ("api.marketplace.admin", f"{api}/api/v3/marketplace/admin/items?page=1&page_size=20"),
        ("admin.marketplace.admin", f"{admin_proxy}/api/v3/marketplace/admin/items?page=1&page_size=20"),
        ("api.marketplace.catalog", f"{api}/api/v3/marketplace/catalog?page=1&page_size=20"),
    ):
        code, data, snippet = get_json(url, admin_token if "admin" in label or "catalog" in label else user_token)
        # catalog needs user token
        if "catalog" in label:
            code, data, snippet = get_json(url, user_token)
        if code != 200:
            note_issue(f"{label}: HTTP {code} {snippet}")
            continue
        item = first_item(data)
        if item is None:
            note_ok(f"{label}: empty list")
            continue
        require_keys(label, item, ["id", "name", "preview_url", "status", "kind", "price"])
        preview = str(item.get("preview_url") or "")
        if "/api/v1/" in preview:
            note_issue(f"{label}: preview_url still on /api/v1: {preview}")
        elif "/api/v3/" in preview:
            note_ok(f"{label}: preview_url on /api/v3")
        else:
            note_issue(f"{label}: unexpected preview_url {preview!r}")

    # --- Other admin list endpoints commonly rendered in tables ---
    admin_lists = [
        ("users", f"{api}/api/v3/users?limit=5", ["id", "email"]),
        ("licenses", f"{api}/api/v3/licenses", ["id", "status"]),
        ("redeem-codes", f"{api}/api/v3/redeem-codes", ["id", "code"]),
        ("web-music-plans", f"{api}/api/v3/plans/web-music/plans", ["id", "name", "monthly_credits", "is_public", "is_active"]),
        ("web-music-topups", f"{api}/api/v3/plans/web-music/topups", ["id", "name", "total_credits", "price_cents"]),
        ("system-settings", f"{api}/api/v3/admin/system-settings", None),  # envelope varies
        ("overview", f"{api}/api/v3/admin/overview", None),
        ("health", f"{api}/api/v3/health", ["status"]),
    ]
    for label, url, keys in admin_lists:
        code, data, snippet = get_json(url, admin_token)
        if code != 200:
            note_issue(f"admin.{label}: HTTP {code} {snippet}")
            continue
        if keys is None:
            note_ok(f"admin.{label}: HTTP 200")
            continue
        item = first_item(data)
        if item is None:
            note_ok(f"admin.{label}: empty")
            continue
        require_keys(f"admin.{label}", item, keys)

    # Website pricing page itself is SSR — probe public API used by build
    code, data, _ = get_json(f"{api}/api/v3/plans/public")
    if code == 200 and isinstance(data, list):
        for p in data[:5]:
            require_keys("website.public.plan", p, ["id", "name", "price_cents", "monthly_credits", "daily_credits"])
            break

    # Streaming home (music)
    code, data, snippet = get_json(f"{api}/api/v3/public/streaming/home")
    if code != 200:
        note_issue(f"streaming.home: HTTP {code} {snippet}")
    else:
        note_ok("streaming.home: HTTP 200")
        if isinstance(data, dict):
            # soft check common keys without being brittle
            for k in ("sections", "tracks", "playlists", "albums", "artists", "featured"):
                if k in data:
                    note_ok(f"streaming.home has {k}")
                    break

    print("\n=== SUMMARY ===")
    print(f"ok={len(OKS)} issues={len(ISSUES)}")
    for msg in ISSUES:
        print(" -", msg)
    await pool.close()
    raise SystemExit(1 if ISSUES else 0)

asyncio.run(main())
'''


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/audit_sandbox_payloads.py", "w") as remote:
            remote.write(REMOTE)
        sftp.close()
        cmd = (
            "cd /opt/camxora/repo && source platform_api/.venv/bin/activate && "
            "PYTHONPATH=/opt/camxora/repo python /tmp/audit_sandbox_payloads.py"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print("STDERR", err[-3000:].encode("ascii", errors="replace").decode("ascii"))
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
