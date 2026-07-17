#!/usr/bin/env python3
"""Store CutLuy credentials in sandbox system_settings (reads .deploy/secrets.env)."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE_PY = textwrap.dedent(
    '''
import asyncio
import os
import sys

import asyncpg

KEYS = {
    "billing.cutluy.api_base_url": ("string", "https://cutluy.com"),
    "billing.cutluy.secret_key": ("string", None),
    "billing.cutluy.payment_link_id": ("string", None),
    "billing.cutluy.webhook_secret": ("string", None),
    "billing.provider.cutluy.enabled": ("string", "true"),
    "billing.active_provider": ("string", "cutluy"),
}


async def upsert(conn, key: str, value_type: str, value: str) -> None:
    await conn.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value_type = EXCLUDED.value_type, value = EXCLUDED.value, updated_at = NOW()
        """,
        key,
        value_type,
        value,
    )


async def main() -> None:
    secret = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    payment_link_id = (sys.argv[2] if len(sys.argv) > 2 else "").strip()
    webhook_secret = (sys.argv[3] if len(sys.argv) > 3 else "").strip()
    if not secret:
        print("ERROR: CUTLUY_SECRET missing")
        sys.exit(1)

    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        await upsert(conn, "billing.cutluy.api_base_url", "string", "https://cutluy.com")
        await upsert(conn, "billing.cutluy.secret_key", "string", secret)
        if payment_link_id:
            await upsert(conn, "billing.cutluy.payment_link_id", "string", payment_link_id)
        if webhook_secret:
            await upsert(conn, "billing.cutluy.webhook_secret", "string", webhook_secret)
        await upsert(conn, "billing.provider.cutluy.enabled", "string", "true")
        await upsert(conn, "billing.active_provider", "string", "cutluy")
        masked = f"{secret[:8]}...{secret[-4:]}" if len(secret) > 12 else "(set)"
        print(f"OK cutluy configured masked={masked}")
        print(f"OK payment_link_id={'set' if payment_link_id else 'empty'}")
        print(f"OK webhook_secret={'set' if webhook_secret else 'empty'}")
    finally:
        await conn.close()


asyncio.run(main())
'''
)


def main() -> None:
    secrets = load_secrets()
    secret = (secrets.get("PLATFORM_CUTLUY_SECRET_KEY") or "").strip()
    if not secret:
        print("ERROR: Set PLATFORM_CUTLUY_SECRET_KEY in .deploy/secrets.env")
        sys.exit(1)

    payment_link_id = (secrets.get("PLATFORM_CUTLUY_PAYMENT_LINK_ID") or "").strip()
    webhook_secret = (secrets.get("PLATFORM_CUTLUY_WEBHOOK_SECRET") or "").strip()

    key_path = ensure_deploy_key()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        key_path,
        secrets.get("VPS_PASSWORD") or None,
    )
    remote_py = "/tmp/configure_cutluy.py"
    sftp = client.open_sftp()
    with sftp.file(remote_py, "w") as remote_file:
        remote_file.write(REMOTE_PY)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
        f"/opt/camxora/repo/platform_api/.venv/bin/python {remote_py} {secret!r} {payment_link_id!r} {webhook_secret!r}'"
    )
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    client.exec_command(f"rm -f {remote_py}")
    client.close()
    if out.strip():
        print(out.strip())
    if err.strip():
        print(err.strip(), file=sys.stderr)
    if code != 0:
        sys.exit(code)

    print("Restarting platform API...")
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        key_path,
        secrets.get("VPS_PASSWORD") or None,
    )
    client.exec_command("systemctl restart camxora-api")
    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
