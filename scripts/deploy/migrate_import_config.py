#!/usr/bin/env python3
"""Import platform config / music prompts archive on sandbox (invoked remotely)."""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import sys

import asyncpg

CONFIG_TABLES_ORDER = [
    "system_settings",
    "plans",
    "plan_offers",
    "credit_packs",
    "credit_pricing",
    "ai_model_costs",
    "key_pool_configs",
    "api_key_entries",
    "rate_limit_config",
]

PROMPT_TABLES_ORDER = [
    "music_descriptions",
    "music_structures",
    "channel_prompts",
]

TRUNCATE = [
    "key_status_events",
    "api_key_entries",
    "key_pool_configs",
    "credit_pricing",
    "credit_packs",
    "ai_model_costs",
    "plan_offers",
    "rate_limit_config",
]


def deserialize(val):
    if isinstance(val, dict) and set(val.keys()) == {"__bytes__"}:
        return bytes.fromhex(val["__bytes__"])
    if isinstance(val, str):
        from datetime import date, datetime

        for fmt in (
            val,
            val.replace("Z", "+00:00"),
            val.replace(" ", "T", 1) if " " in val and "T" not in val else val,
        ):
            try:
                return datetime.fromisoformat(fmt)
            except ValueError:
                pass
        if len(val) >= 10 and val[4] == "-" and val[7] == "-":
            try:
                return date.fromisoformat(val[:10])
            except ValueError:
                pass
    if isinstance(val, list):
        return [deserialize(v) for v in val]
    if isinstance(val, dict):
        return {k: deserialize(v) for k, v in val.items()}
    return val


def upsert_sql(table: str, cols: list[str]) -> str:
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "id")
    return (
        f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
        f"ON CONFLICT (id) DO UPDATE SET {updates}"
    )


async def import_table(conn, table: str, export_dir: str) -> None:
    path = os.path.join(export_dir, f"{table}.json.gz")
    if not os.path.isfile(path):
        print(f"skip missing {table}")
        return
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    cols = payload["columns"]
    rows = payload["rows"]
    if not rows:
        print(f"skip empty {table}")
        return
    print(f"Importing {table}: {len(rows)} rows")
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
    sql = (
        f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
        "ON CONFLICT DO NOTHING"
    )
    if table == "system_settings":
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            "ON CONFLICT (key) DO UPDATE SET "
            "value_type = EXCLUDED.value_type, "
            "value = EXCLUDED.value, "
            "updated_at = EXCLUDED.updated_at"
        )
    elif table == "plans":
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            "ON CONFLICT (name) DO UPDATE SET "
            "price_cents = EXCLUDED.price_cents, "
            "billing_cycle_days = EXCLUDED.billing_cycle_days, "
            "profile_allowance = EXCLUDED.profile_allowance, "
            "monthly_song_limit = EXCLUDED.monthly_song_limit, "
            "monthly_draft_limit = EXCLUDED.monthly_draft_limit, "
            "monthly_image_limit = EXCLUDED.monthly_image_limit, "
            "monthly_video_limit = EXCLUDED.monthly_video_limit, "
            "monthly_merge_limit = EXCLUDED.monthly_merge_limit, "
            "daily_song_limit_per_channel = EXCLUDED.daily_song_limit_per_channel, "
            "daily_draft_limit_per_channel = EXCLUDED.daily_draft_limit_per_channel, "
            "daily_image_limit_per_channel = EXCLUDED.daily_image_limit_per_channel, "
            "daily_video_limit = EXCLUDED.daily_video_limit, "
            "daily_merge_limit = EXCLUDED.daily_merge_limit, "
            "included_wallet_credits = EXCLUDED.included_wallet_credits, "
            "plan_kind = EXCLUDED.plan_kind, "
            "is_active = EXCLUDED.is_active, "
            "updated_at = EXCLUDED.updated_at"
        )
    elif table == "key_pool_configs":
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            "ON CONFLICT (provider) DO UPDATE SET "
            "selection_strategy = EXCLUDED.selection_strategy, "
            "cooldown_seconds = EXCLUDED.cooldown_seconds, "
            "updated_at = EXCLUDED.updated_at"
        )
    elif table == "api_key_entries":
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            "ON CONFLICT (provider, label) DO UPDATE SET "
            "encrypted_key_value = EXCLUDED.encrypted_key_value, "
            "priority = EXCLUDED.priority, "
            "status = EXCLUDED.status, "
            "updated_at = EXCLUDED.updated_at"
        )
    elif table in PROMPT_TABLES_ORDER:
        sql = upsert_sql(table, cols)

    batch: list[tuple] = []
    batch_size = 500
    imported_ids = []
    for raw in rows:
        batch.append(tuple(deserialize(raw[c]) for c in cols))
        if "id" in cols:
            imported_ids.append(deserialize(raw["id"]))
        if len(batch) >= batch_size:
            await conn.executemany(sql, batch)
            batch.clear()
    if batch:
        await conn.executemany(sql, batch)

    if table in ("music_descriptions", "music_structures") and imported_ids:
        fk_col = "description_id" if table == "music_descriptions" else "structure_id"
        await conn.execute(
            f"""
            DELETE FROM "{table}" d
            WHERE d.user_id IS NULL
              AND d.id <> ALL($1::uuid[])
              AND NOT EXISTS (
                SELECT 1 FROM songs s
                WHERE s.{fk_col} = d.id
              )
            """,
            imported_ids,
        )
    elif table == "channel_prompts" and imported_ids:
        await conn.execute(
            """
            DELETE FROM channel_prompts d
            WHERE d.id <> ALL($1::uuid[])
            """,
            imported_ids,
        )


async def ensure_prompt_schema(conn) -> None:
    exists = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'channel_prompts'
              AND column_name = 'match_key'
        )
        """
    )
    if not exists:
        print("Adding channel_prompts.match_key column")
        await conn.execute("ALTER TABLE channel_prompts ADD COLUMN match_key VARCHAR(100)")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_channel_prompts_match_key ON channel_prompts(match_key)"
        )


async def backup_tables(conn, tables: list[str]) -> str:
    """Dump the tables about to be truncated to a timestamped /tmp dir.

    A destructive import must never run without a rollback source; the path is
    printed so an operator can restore from it.
    """
    import time

    backup_dir = os.path.join("/tmp", f"camxora-config-backup-{int(time.time())}")
    os.makedirs(backup_dir, exist_ok=True)
    for table in tables:
        if not await conn.fetchval("SELECT to_regclass($1)", f"public.{table}"):
            continue
        rows = await conn.fetch(f'SELECT row_to_json(t) AS r FROM "{table}" t')
        with gzip.open(os.path.join(backup_dir, f"{table}.json.gz"), "wt", encoding="utf-8") as fh:
            json.dump([row["r"] for row in rows], fh)
    print(f"BACKUP_DIR {backup_dir}")
    return backup_dir


async def main(export_dir: str, apply: bool) -> None:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        has_config = any(
            os.path.isfile(os.path.join(export_dir, f"{t}.json.gz"))
            for t in CONFIG_TABLES_ORDER
        )
        if not apply:
            print(
                "DRY RUN: pass --apply to replace config. "
                f"Tables that would be truncated: {', '.join(TRUNCATE)}; "
                "plans without a license would be deleted."
            )
            return

        await ensure_prompt_schema(conn)
        if has_config:
            # Backup first: the truncate below is permanent.
            await backup_tables(conn, TRUNCATE + ["plans"])
            for table in TRUNCATE:
                exists = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
                if exists:
                    print(f"TRUNCATE {table}")
                    await conn.execute(f'TRUNCATE TABLE "{table}" CASCADE')
            await conn.execute(
                """
                DELETE FROM plans p
                WHERE NOT EXISTS (SELECT 1 FROM licenses l WHERE l.plan_id = p.id)
                """
            )
            for table in CONFIG_TABLES_ORDER:
                await import_table(conn, table, export_dir)

        for table in PROMPT_TABLES_ORDER:
            await import_table(conn, table, export_dir)
        print("IMPORT_DONE")
    finally:
        await conn.close()


if __name__ == "__main__":
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not positional:
        raise SystemExit("usage: migrate_import_config.py <export_dir> [--apply]")
    asyncio.run(main(positional[0], apply="--apply" in sys.argv[1:]))
