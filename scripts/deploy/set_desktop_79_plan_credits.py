#!/usr/bin/env python3
"""Set the hidden $79 desktop plan's credit grant on sandbox or production.

Hidden plan: "Monthly · 2-channel" (price 7900, plan_kind='subscription',
plan_type='desktop_pro'). It is the only active desktop plan and must stay
`is_public=false`.

Grant math (product brief):
  - 450 Suno requests x 10 credits = 4,500 credits   (1 request = 2 tracks)
  - 130 images x 5 credits         =   650 credits   (2 per batch x 2 batches/day)
  - video export + merge           =     0 credits   (already free)
  ---------------------------------------------------
  monthly_credits                  = 5,150

Dry-run by default. Pass --apply to write. Pass --credits N to override.
Use --env sandbox|production.
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

DEFAULT_CREDITS = 5150


def remote_cmd(credits: int, apply: bool) -> str:
    write = "true" if apply else "false"
    return f'''
set +e
REPO=/opt/camxora/repo/platform_api
cd $REPO && env PYTHONPATH=/opt/camxora/repo APPLY={write} TARGET_CREDITS={credits} .venv/bin/python - <<'PYEOF'
import asyncio, os
import asyncpg

APPLY = os.environ.get("APPLY") == "true"
TARGET = int(os.environ.get("TARGET_CREDITS") or 0)

async def main():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    await pool.execute("SET statement_timeout = '20s'")

    row = await pool.fetchrow(
        "SELECT id, name, price_cents, billing_cycle_days, monthly_credits, "
        "monthly_song_limit, image_credits, lyric_credits, title_credits, album_credits, "
        "style_credits, music_credits, video_credits, merge_credits, is_active, is_public "
        "FROM plans WHERE price_cents = 7900 AND plan_kind = 'subscription' "
        "AND plan_type = 'desktop_pro'"
    )
    if row is None:
        print("NO_PLAN_ROW_FOUND")
        return
    print("BEFORE:", dict(row))
    if not APPLY:
        print(f"DRY_RUN target monthly_credits = {{TARGET}} (no change written)")
        print("DRY_RUN_OK")
        return

    updated = await pool.fetchrow(
        "UPDATE plans SET monthly_credits = $1, image_credits = 5, "
        "video_credits = 0, merge_credits = 0, updated_at = NOW() "
        "WHERE id = $2 RETURNING id, name, monthly_credits, image_credits, "
        "video_credits, merge_credits, is_active, is_public",
        TARGET, row["id"],
    )
    print("AFTER:", dict(updated))
    print("APPLIED")
    await pool.close()

asyncio.run(main())
PYEOF
echo SET_PLAN_DONE
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credits", type=int, default=DEFAULT_CREDITS)
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
        _, stdout, stderr = client.exec_command(remote_cmd(args.credits, args.apply), get_pty=False, timeout=150)
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
