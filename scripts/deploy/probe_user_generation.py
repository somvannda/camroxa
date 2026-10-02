#!/usr/bin/env python3
"""READ-ONLY probe: why does a free music-web user have >5 songs downloaded?

Answers for a given email:
- account/subscription/license status (is the user really free-tier?)
- system_settings free-pool knobs (limit credits, reset period)
- web_music_daily_usage buckets (credits_used vs generation_count per day/month)
- credit_transactions web_music debits (per-request ledger, refunds)
- suno_tasks web_music rows (task count by status, success list since a month start)

Usage: python scripts/deploy/probe_user_generation.py <email> [month_start YYYY-MM-DD]
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

REMOTE_BODY = r'''
set +e
REPO=/opt/camxora/repo/platform_api
cd $REPO
env PYTHONPATH=/opt/camxora/repo .venv/bin/python - 'EMAIL_PLACEHOLDER' 'MONTH_PLACEHOLDER' <<'PYEOF'
import asyncio, datetime, sys
import asyncpg

EMAIL = sys.argv[1].strip().lower()
MONTH = datetime.date.fromisoformat(sys.argv[2].strip())

def load_env(path):
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return out

async def main() -> int:
    env = load_env("/opt/camxora/repo/platform_api/.env")
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not dsn:
        print("NO_DSN"); return 2
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)

    print("== system_settings (free pool knobs) ==")
    for r in await pool.fetch(
        "SELECT key, value, value_type FROM system_settings "
        "WHERE key IN ('web_music_free_daily_credits','music_web_free_reset_period',"
        "'web_music_free_daily_limit') ORDER BY key"
    ):
        print("  ", r["key"], "=", r["value"], "(", r["value_type"], ")")

    user = await pool.fetchrow("SELECT id, email, created_at, status FROM users WHERE lower(email)=$1", EMAIL)
    if not user:
        print("NO_USER:", EMAIL); return 2
    uid = user["id"]
    print("== user ==")
    print("  ", user["id"], "|", user["email"], "| created", user["created_at"], "| status", user["status"])

    print("== web_subscriptions ==")
    subs = await pool.fetch(
        "SELECT id, status, plan_id, payment_provider, monthly_credits_granted, "
        "monthly_credits_used, current_period_start, current_period_end "
        "FROM web_subscriptions WHERE user_id=$1 ORDER BY created_at DESC", uid
    )
    for s in subs:
        print("   sub", s["id"], "status=", s["status"], "plan=", s["plan_id"],
              "granted=", s["monthly_credits_granted"], "used=", s["monthly_credits_used"],
              "period=", s["current_period_start"], "->", s["current_period_end"])

    print("== licenses ==")
    try:
        for l in await pool.fetch(
            "SELECT id, plan_id, status, expires_at FROM licenses WHERE user_id=$1", uid
        ):
            print("   lic", l["id"], "plan=", l["plan_id"], "status=", l["status"],
                  "expires=", l["expires_at"])
    except Exception as exc:  # noqa: BLE001
        print("   (licenses query failed:", type(exc).__name__, str(exc)[:200], ")")

    print("== web_music_daily_usage (all buckets) ==")
    for r in await pool.fetch(
        "SELECT usage_date, credits_used, generation_count FROM web_music_daily_usage "
        "WHERE user_id=$1 ORDER BY usage_date DESC LIMIT 25", uid
    ):
        print("   bucket", r["usage_date"], "credits_used=", r["credits_used"],
              "generation_count=", r["generation_count"])

    print("== credit_transactions web_music (summary by reason/direction) ==")
    for r in await pool.fetch(
        "SELECT reason, direction, count(*) AS n, COALESCE(SUM(amount),0) AS total "
        "FROM credit_transactions WHERE user_id=$1 AND reason LIKE '%web_music%' "
        "GROUP BY reason, direction ORDER BY reason, direction", uid
    ):
        print("   ", r["reason"], "/", r["direction"], "n=", r["n"], "sum=", r["total"])

    print("== credit_transactions web_music (last 40 rows) ==")
    for r in await pool.fetch(
        "SELECT created_at, direction, reason, amount, ref_id FROM credit_transactions "
        "WHERE user_id=$1 AND reason LIKE '%web_music%' ORDER BY created_at DESC LIMIT 40", uid
    ):
        print("   ", r["created_at"], r["direction"], "|", r["reason"],
              "amount=", r["amount"], "ref=", str(r["ref_id"])[:12])

    print("== suno_tasks web_music (by status) ==")
    for r in await pool.fetch(
        "SELECT status, count(*) AS n, min(created_at) AS first, max(created_at) AS last "
        "FROM suno_tasks WHERE user_id=$1 AND source='web_music' GROUP BY status ORDER BY status", uid
    ):
        print("   status=", r["status"], "n=", r["n"], "first=", r["first"], "last=", r["last"])

    print("== suno_tasks web_music success since", MONTH, "==")
    rows = await pool.fetch(
        "SELECT id, title, created_at, "
        "(audio_url_ok IS NOT NULL OR b2_storage_key_ok IS NOT NULL) AS ok_ready, "
        "(audio_url_alt IS NOT NULL OR b2_storage_key_alt IS NOT NULL) AS alt_ready "
        "FROM suno_tasks WHERE user_id=$1 AND source='web_music' AND status='success' "
        "AND created_at >= $2 ORDER BY created_at DESC LIMIT 30", uid, MONTH
    )
    print("   success-count:", len(rows))
    for r in rows:
        print("   ", str(r["id"])[:12], "|", r["created_at"], "| ok=", r["ok_ready"],
              "alt=", r["alt_ready"], "|", (str(r["title"] or ""))[:60])

    print("== suno_tasks web_music ALL recent (any status) ==")
    for r in await pool.fetch(
        "SELECT id, status, created_at FROM suno_tasks WHERE user_id=$1 AND source='web_music' "
        "ORDER BY created_at DESC LIMIT 12", uid
    ):
        print("   ", str(r["id"])[:12], "|", r["status"], "|", r["created_at"])

    print("== export_events (downloads: mp3/wav) summary ==")
    for r in await pool.fetch(
        "SELECT format, variant, actor, count(*) AS n, min(created_at) AS first, max(created_at) AS last "
        "FROM export_events WHERE user_id=$1 GROUP BY format, variant, actor ORDER BY format, variant", uid
    ):
        print("   ", r["format"], "/", r["variant"], "actor=", r["actor"],
              "n=", r["n"], "first=", r["first"], "last=", r["last"])

    print("== export_events by task (how many distinct songs downloaded) ==")
    for r in await pool.fetch(
        "SELECT suno_task_id, count(*) AS n, "
        "string_agg(DISTINCT format || ':' || variant, ', ') AS kinds "
        "FROM export_events WHERE user_id=$1 GROUP BY suno_task_id ORDER BY n DESC", uid
    ):
        print("   task=", str(r["suno_task_id"])[:12], "downloads=", r["n"], "kinds=", r["kinds"])

    print("== export_events last 40 rows ==")
    for r in await pool.fetch(
        "SELECT e.created_at, e.format, e.variant, e.actor, "
        "substring(e.suno_task_id::text, 1, 12) AS task "
        "FROM export_events e WHERE e.user_id=$1 ORDER BY e.created_at DESC LIMIT 40", uid
    ):
        print("   ", r["created_at"], "|", r["format"], "/", r["variant"],
              "| actor=", r["actor"], "| task=", r["task"])

    print("== audio_watermarks (payload hashes stored per export) ==")
    try:
        n = await pool.fetchval(
            "SELECT count(*) FROM audio_watermarks WHERE user_id=$1", uid
        )
        print("   count=", n)
    except Exception as exc:  # noqa: BLE001
        print("   (audio_watermarks query failed:", type(exc).__name__, str(exc)[:200], ")")

    await pool.close()
    print("PROBE_DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
PYEOF
echo USER_PROBE_RC=$?
'''


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python probe_user_generation.py <email> [month_start]")
        return 2
    email = sys.argv[1].replace("'", "")
    month = (sys.argv[2] if len(sys.argv) > 2 else "2026-09-01").replace("'", "")

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    cmd = REMOTE_BODY.replace("EMAIL_PLACEHOLDER", email).replace("MONTH_PLACEHOLDER", month)
    print(f"=== probe user generation usage ({host}) email={email} month_start={month} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
