#!/usr/bin/env python3
"""Point sandbox channel_logo/channel_cover AI routing at SLAI (primary image provider)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

CHANNEL_IMAGE_OPS = ("channel_logo", "channel_cover")
SLAI_IMAGE_ASSIGNMENT = {
    "provider": "slai",
    "sub_model": "cx/gpt-image-2.5",
    "is_active": True,
}


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    remote_script = r"""
import asyncio, asyncpg, json, os

CHANNEL_IMAGE_OPS = ("channel_logo", "channel_cover")
SLAI_IMAGE_ASSIGNMENT = {
    "provider": "slai",
    "sub_model": "cx/gpt-image-2.5",
    "is_active": True,
}

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        "SELECT value FROM system_settings WHERE key = 'ai_routing_assignments'"
    )
    if row is None:
        raise SystemExit("ai_routing_assignments not found")
    assignments = json.loads(row["value"])
    for op in CHANNEL_IMAGE_OPS:
        assignments[op] = dict(SLAI_IMAGE_ASSIGNMENT)
        print(f"patched {op} -> cx/gpt-image-2.5")
    await conn.execute(
        "UPDATE system_settings SET value = $1, updated_at = NOW() WHERE key = 'ai_routing_assignments'",
        json.dumps(assignments, separators=(",", ":")),
    )
    await conn.close()

asyncio.run(main())
"""

    sftp = client.open_sftp()
    remote_path = "/tmp/fix_channel_image_routing.py"
    with sftp.file(remote_path, "w") as remote_file:
        remote_file.write(remote_script)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {remote_path}' && "
        "systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
