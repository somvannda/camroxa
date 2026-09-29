#!/usr/bin/env python3
"""Make local video export + merge free (0 credits) on sandbox or production.

Video export (``video`` / ``video_manual``) and auto-merge (``video_merge``) run
locally with FFmpeg (COGS $0). This sets both the sell price and the cost to 0:

  - ``credit_pricing``: local rows -> credits_per_operation = 0, external_cost_cents = 0
  - ``plans``: video_credits = 0, merge_credits = 0 on every plan

Dry-run by default. Pass --apply to write. Use --env sandbox|production.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)

LOCAL_OPS = ("video", "video_manual", "video_merge", "merge")


def remote_cmd(apply: bool) -> str:
    write = "true" if apply else "false"
    return f'''
set +e
REPO=/opt/camxora/repo/platform_api
cd $REPO && env PYTHONPATH=/opt/camxora/repo APPLY={write} .venv/bin/python - <<'PYEOF'
import asyncio, os
import asyncpg

APPLY = os.environ.get("APPLY") == "true"
LOCAL_OPS = ('video', 'video_manual', 'video_merge', 'merge')

async def main():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    await pool.execute("SET statement_timeout = '20s'")

    print("===== credit_pricing local video/merge rows (BEFORE) =====")
    rows = await pool.fetch(
        "SELECT ai_service, operation_type, sub_model, credits_per_operation, "
        "external_cost_cents FROM credit_pricing "
        "WHERE ai_service = 'local' AND operation_type = ANY($1::text[]) "
        "ORDER BY operation_type", list(LOCAL_OPS))
    for r in rows:
        print(dict(r))

    print("\\n===== plans with non-zero video/merge credits (BEFORE) =====")
    plans = await pool.fetch(
        "SELECT name, plan_type, price_cents, video_credits, merge_credits FROM plans "
        "WHERE COALESCE(video_credits, 0) <> 0 OR COALESCE(merge_credits, 0) <> 0 "
        "ORDER BY price_cents DESC")
    for r in plans:
        print(dict(r))

    if not APPLY:
        print("\\nDRY_RUN: would zero the rows above (no change written)")
        print("DRY_RUN_OK")
        return

    priced = await pool.execute(
        "UPDATE credit_pricing SET credits_per_operation = 0, external_cost_cents = 0 "
        "WHERE ai_service = 'local' AND operation_type = ANY($1::text[])", list(LOCAL_OPS))
    planres = await pool.execute(
        "UPDATE plans SET video_credits = 0, merge_credits = 0, updated_at = NOW() "
        "WHERE COALESCE(video_credits, 0) <> 0 OR COALESCE(merge_credits, 0) <> 0")

    print("\\n===== AFTER =====")
    after_price = await pool.fetch(
        "SELECT operation_type, credits_per_operation, external_cost_cents FROM credit_pricing "
        "WHERE ai_service = 'local' AND operation_type = ANY($1::text[]) ORDER BY operation_type",
        list(LOCAL_OPS))
    for r in after_price:
        print(dict(r))
    remaining = await pool.fetch(
        "SELECT COUNT(*) n FROM plans "
        "WHERE COALESCE(video_credits, 0) <> 0 OR COALESCE(merge_credits, 0) <> 0")
    print("plans still non-zero:", remaining[0]["n"])
    print("pricing_update:", priced, "| plans_update:", planres)
    print("APPLIED")
    await pool.close()

asyncio.run(main())
PYEOF
echo SET_FREE_DONE
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--env", choices=["sandbox", "production"], default="sandbox")
    args = parser.parse_args()

    if args.env == "production":
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)
        expected = CANONICAL_PRODUCTION_HOST
    else:
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
        expected = CANONICAL_SANDBOX_HOST
    if host != expected:
        raise SystemExit(f"Refusing {args.env} host mismatch: {host} != {expected}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(remote_cmd(args.apply), get_pty=False, timeout=150)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
