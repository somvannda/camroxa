#!/usr/bin/env python3
"""Migrate platform configuration from local Postgres to sandbox VPS.

Copies system settings, plans, credits, key pools, AI costs, and admin music prompts.
Does not migrate content pools (title/album/opening) or user-owned data.
Preserves encrypted API keys by syncing PLATFORM_ENCRYPTION_MASTER_KEY to sandbox.

Usage:
  python scripts/deploy/migrate_platform_config.py
  python scripts/deploy/migrate_platform_config.py --dry-run
  python scripts/deploy/migrate_platform_config.py --prompts-only
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

LOCAL_ENV = REPO_ROOT / "platform_api" / ".env"

# (table, sort_key, optional_export_where)
CONFIG_TABLES: list[tuple[str, str, str | None]] = [
    ("system_settings", "key", None),
    ("plans", "name", None),
    ("plan_offers", "id", None),
    ("credit_packs", "id", None),
    ("credit_pricing", "id", None),
    ("ai_model_costs", "id", None),
    ("key_pool_configs", "provider", None),
    ("api_key_entries", "id", None),
    ("rate_limit_config", "id", None),
]

# Admin catalog only — user-owned prompts stay on their home environment.
PROMPT_TABLES: list[tuple[str, str, str | None]] = [
    ("music_descriptions", "id", "user_id IS NULL"),
    ("music_structures", "id", "user_id IS NULL"),
    ("channel_prompts", "id", None),
]

TRUNCATE_ORDER = [
    "key_status_events",
    "api_key_entries",
    "key_pool_configs",
    "credit_pricing",
    "credit_packs",
    "ai_model_costs",
    "plan_offers",
    "rate_limit_config",
    # plans: upsert — may be referenced by licenses
    "system_settings",
]


def read_local_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if not LOCAL_ENV.is_file():
        return data
    for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def local_dsn() -> str:
    env = read_local_env()
    raw = os.environ.get(
        "PLATFORM_DATABASE_URL",
        env.get("PLATFORM_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/platform_db"),
    )
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def export_table(conn, table: str, out_dir: Path) -> dict:
    import asyncpg

    cols = [
        r["column_name"]
        for r in conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
            """,
            table,
        )
    ]
    if not cols:
        raise RuntimeError(f"Table not found: {table}")

    rows = conn.fetch(f'SELECT * FROM "{table}"')
    path = out_dir / f"{table}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump({"columns": cols, "rows": [dict(r) for r in rows]}, fh, default=str)
    return {"table": table, "rows": len(rows), "path": str(path), "size": path.stat().st_size}


async def export_local(out_dir: Path) -> list[dict]:
    import asyncpg

    conn = await asyncpg.connect(local_dsn())
    meta: list[dict] = []
    try:
        for table, _, where_clause in CONFIG_TABLES + PROMPT_TABLES:
            print(f"Exporting {table}...")
            # asyncpg connection is async — use fetch in async wrapper
            cols = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                table,
            )
            col_names = [r["column_name"] for r in cols]
            if not col_names:
                print(f"  skip (missing): {table}")
                continue
            where_sql = f" WHERE {where_clause}" if where_clause else ""
            rows = await conn.fetch(f'SELECT * FROM "{table}"{where_sql}')
            path = out_dir / f"{table}.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                json.dump({"columns": col_names, "rows": [dict(r) for r in rows]}, fh, default=str)
            meta.append({"table": table, "rows": len(rows), "size": path.stat().st_size})
            print(f"  {len(rows)} rows ({path.stat().st_size // 1024} KB)")
    finally:
        await conn.close()
    return meta


def serialize_value(val):
    if val is None:
        return None
    if isinstance(val, (bytes, bytearray, memoryview)):
        return {"__bytes__": bytes(val).hex()}
    if isinstance(val, list):
        return [serialize_value(v) for v in val]
    if isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    return val


async def export_local_streaming(out_dir: Path, tables: list[tuple[str, str, str | None]]) -> list[dict]:
    """Export with byte-safe JSON for encrypted keys."""
    import asyncpg

    conn = await asyncpg.connect(local_dsn())
    meta: list[dict] = []
    try:
        for table, _, where_clause in tables:
            print(f"Exporting {table}...")
            cols = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                table,
            )
            col_names = [r["column_name"] for r in cols]
            if not col_names:
                print(f"  skip (missing): {table}")
                continue

            where_sql = f" WHERE {where_clause}" if where_clause else ""
            path = out_dir / f"{table}.json.gz"
            count = 0
            batch_size = 10000
            offset = 0
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                fh.write('{"columns":')
                json.dump(col_names, fh)
                fh.write(',"rows":[')
                first = True
                while True:
                    rows = await conn.fetch(
                        f'SELECT * FROM "{table}"{where_sql} ORDER BY 1 LIMIT $1 OFFSET $2',
                        batch_size,
                        offset,
                    )
                    if not rows:
                        break
                    for record in rows:
                        row = dict(record)
                        row = {k: serialize_value(v) for k, v in row.items()}
                        if not first:
                            fh.write(",")
                        json.dump(row, fh, default=str)
                        first = False
                        count += 1
                    offset += batch_size
                    if count % 50000 == 0:
                        print(f"  ... {count} rows")
                fh.write("]}")
            meta.append({"table": table, "rows": count, "size": path.stat().st_size})
            print(f"  {count} rows ({path.stat().st_size // 1024} KB)")
    finally:
        await conn.close()
    return meta


def build_archive(meta: list[dict], out_dir: Path) -> Path:
    archive = out_dir / "camxora-config-export.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        manifest = {"tables": meta, "source_dsn_host": "localhost"}
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        tar.addfile(info, io.BytesIO(manifest_bytes))
        for entry in meta:
            table = entry["table"]
            tar.add(out_dir / f"{table}.json.gz", arcname=f"{table}.json.gz")
    return archive


def sync_encryption_key(client, master_key: str) -> None:
    if not master_key:
        print("Warning: no local PLATFORM_ENCRYPTION_MASTER_KEY — API keys may not decrypt on sandbox.")
        return
    env_path = "/opt/camxora/repo/platform_api/.env"
    cmd = f"""
set -e
ENV={env_path}
if grep -q '^PLATFORM_ENCRYPTION_MASTER_KEY=' "$ENV"; then
  sed -i 's|^PLATFORM_ENCRYPTION_MASTER_KEY=.*|PLATFORM_ENCRYPTION_MASTER_KEY={master_key}|' "$ENV"
else
  echo 'PLATFORM_ENCRYPTION_MASTER_KEY={master_key}' >> "$ENV"
fi
systemctl restart camxora-api
echo ENCRYPTION_KEY_SYNCED
"""
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out.strip())
    if err.strip():
        print(err.strip())


def import_on_sandbox(client, archive: Path) -> None:
    import time

    stamp = int(time.time())
    remote_archive = f"/tmp/camxora-config-export-{stamp}.tar.gz"
    remote_dir = f"/tmp/camxora-config-import-{stamp}"
    local_runner = Path(__file__).resolve().parent / "migrate_import_config.py"
    remote_py = f"/tmp/camxora_import_config_{stamp}.py"

    sftp = client.open_sftp()
    with open(archive, "rb") as local_f:
        sftp.putfo(local_f, remote_archive, confirm=True)
    sftp.put(str(local_runner), remote_py, confirm=True)
    sftp.close()

    cmd = f"""
set -e
rm -rf {remote_dir} && mkdir -p {remote_dir}
/opt/camxora/repo/platform_api/.venv/bin/python -c "import tarfile; tarfile.open('{remote_archive}', 'r:gz').extractall('{remote_dir}')"
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python {remote_py} {remote_dir}'
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print(err)
    if code != 0:
        raise SystemExit(code)


async def run_export(out_dir: Path, tables: list[tuple[str, str, str | None]]) -> list[dict]:
    return await export_local_streaming(out_dir, tables)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Export only, do not upload")
    parser.add_argument(
        "--prompts-only",
        action="store_true",
        help="Migrate only admin music prompts and channel setup prompts",
    )
    args = parser.parse_args()

    import asyncio

    tables = PROMPT_TABLES if args.prompts_only else CONFIG_TABLES + PROMPT_TABLES
    local_env = read_local_env()
    master_key = local_env.get("PLATFORM_ENCRYPTION_MASTER_KEY", "")

    with tempfile.TemporaryDirectory(prefix="camxora-config-") as tmp:
        out_dir = Path(tmp)
        print(f"Local source: {local_dsn()}")
        if args.prompts_only:
            print("Mode: prompts only")
        meta = asyncio.run(run_export(out_dir, tables))
        archive = build_archive(meta, out_dir)
        print(f"Archive: {archive} ({archive.stat().st_size // 1024 // 1024} MB)")
        total_rows = sum(m["rows"] for m in meta)
        print(f"Total rows: {total_rows}")

        if args.dry_run:
            print("Dry run — skipping upload.")
            return 0

        secrets = load_secrets()
        client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
        try:
            print("Uploading and importing on sandbox...")
            import_on_sandbox(client, archive)
            if not args.prompts_only:
                enc_key = secrets.get("PLATFORM_ENCRYPTION_MASTER_KEY") or master_key
                sync_encryption_key(client, enc_key)
        finally:
            client.close()

    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
