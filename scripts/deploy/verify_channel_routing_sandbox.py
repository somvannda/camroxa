#!/usr/bin/env python3
"""Print sandbox channel image routing assignments."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote_script = r"""
import asyncio, asyncpg, json, os
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    for key in ("ai_routing_assignments", "ai_routing_image_fallback_chain"):
        row=await conn.fetchrow("SELECT value FROM system_settings WHERE key=$1", key)
        print("===", key, "===")
        if not row:
            print("(missing)")
            continue
        val=json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]
        if key == "ai_routing_assignments":
            for op in ("channel_logo", "channel_cover", "background_image", "thumbnail_image"):
                print(op, val.get(op))
        else:
            print(json.dumps(val, indent=2))
    await conn.close()
asyncio.run(main())
"""
    sftp = client.open_sftp()
    remote_path = "/tmp/verify_channel_routing.py"
    with sftp.file(remote_path, "w") as remote_file:
        remote_file.write(remote_script)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && "
        f"set +a && /opt/camxora/repo/platform_api/.venv/bin/python {remote_path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
