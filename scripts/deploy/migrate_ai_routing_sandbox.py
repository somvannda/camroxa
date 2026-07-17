#!/usr/bin/env python3
"""Migrate ai_routing_* settings to sandbox (channel ops use deepseek on sandbox)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402
from migrate_platform_config import read_local_env, sync_encryption_key  # noqa: E402

CHANNEL_TEXT_OPS = (
    "channel_name",
    "channel_description",
    "channel_keywords",
    "channel_tags",
)

CHANNEL_IMAGE_OPS = (
    "channel_logo",
    "channel_cover",
)


def local_dsn() -> str:
    env = read_local_env()
    raw = env.get("PLATFORM_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/platform_db")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


async def load_local_routing() -> dict[str, tuple[str, str]]:
    import asyncpg

    conn = await asyncpg.connect(local_dsn())
    rows = await conn.fetch(
        "SELECT key, value, value_type FROM system_settings WHERE key LIKE 'ai_routing%' ORDER BY key"
    )
    await conn.close()
    return {row["key"]: (row["value"], row["value_type"]) for row in rows}


def patch_assignments_for_sandbox(raw_value: str) -> str:
    assignments = json.loads(raw_value)
    for op in CHANNEL_TEXT_OPS:
        if op in assignments:
            assignments[op] = {
                "provider": "deepseek",
                "sub_model": "deepseek-chat",
                "is_active": True,
            }
    for op in CHANNEL_IMAGE_OPS:
        if op in assignments:
            assignments[op] = {
                "provider": "slai",
                "sub_model": "slai/gpt-image-2",
                "is_active": True,
            }
    return json.dumps(assignments, separators=(",", ":"))


def main() -> int:
    routing = asyncio.run(load_local_routing())
    if not routing:
        print("No ai_routing_* settings found locally.")
        return 1

    if "ai_routing_assignments" in routing:
        value, value_type = routing["ai_routing_assignments"]
        routing["ai_routing_assignments"] = (
            patch_assignments_for_sandbox(value),
            value_type,
        )
        print(
            "Patched channel text ops to deepseek/deepseek-chat and "
            "channel_logo/cover to slai/slai/gpt-image-2 for sandbox."
        )

    payload = json.dumps(
        [{"key": k, "value": v, "value_type": vt} for k, (v, vt) in routing.items()]
    )

    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    local_script = Path(__file__).resolve().parent / "remote_apply_routing.py"
    local_script.write_text(
        f"""#!/usr/bin/env python3
import asyncio, asyncpg, json, os
ROWS = json.loads({payload!r})
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    for row in ROWS:
        await conn.execute(
            '''
            INSERT INTO system_settings (key, value, value_type, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (key) DO UPDATE SET
              value = EXCLUDED.value,
              value_type = EXCLUDED.value_type,
              updated_at = NOW()
            ''',
            row["key"], row["value"], row["value_type"],
        )
        print("upsert", row["key"])
    await conn.close()
asyncio.run(main())
""",
        encoding="utf-8",
    )

    remote_script = "/tmp/apply_routing_sandbox.py"
    sftp = client.open_sftp()
    sftp.put(str(local_script), remote_script)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {remote_script}' && "
        "systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)

    local_env = read_local_env()
    master_key = secrets.get("PLATFORM_ENCRYPTION_MASTER_KEY") or local_env.get("PLATFORM_ENCRYPTION_MASTER_KEY", "")
    sync_encryption_key(client, master_key)
    client.close()
    print("AI routing migrated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
