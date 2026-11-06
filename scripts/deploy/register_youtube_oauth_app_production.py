"""Register the project's Google OAuth client as the default YouTube OAuth app.

Reads the production env (never prints the secret), encrypts it with the
platform master key, and upserts the single default app row.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

REMOTE = r'''
import asyncio
from pathlib import Path

env = {}
for line in Path('/opt/camxora/repo/platform_api/.env').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    env[key.strip()] = value.strip().strip('"').strip("'")

client_id = (env.get('PLATFORM_GOOGLE_CLIENT_ID') or '').strip()
secret = (env.get('PLATFORM_GOOGLE_CLIENT_SECRET') or '').strip()
dsn = (env.get('PLATFORM_DATABASE_URL') or '').strip()
dsn = dsn.replace('postgresql+asyncpg://', 'postgresql://')
master = (env.get('PLATFORM_ENCRYPTION_MASTER_KEY') or '').strip()

print('client_id_present:', bool(client_id), 'prefix:', client_id[:24])
print('secret_present:', bool(secret), 'len:', len(secret))
print('db_present:', bool(dsn), 'master_present:', bool(master))

if not (client_id and secret and dsn and master):
    raise SystemExit('missing configuration')

import asyncpg
from platform_api.services.key_encryption import KeyEncryption


async def main() -> None:
    enc = KeyEncryption(master)
    blob = enc.encrypt(secret)
    conn = await asyncpg.connect(dsn)
    try:
        existing = await conn.fetchrow(
            'SELECT id FROM youtube_oauth_apps WHERE client_id = $1', client_id
        )
        if existing:
            await conn.execute(
                'UPDATE youtube_oauth_apps SET encrypted_client_secret = $2, '
                'is_default = TRUE, updated_at = NOW() WHERE id = $1',
                existing['id'],
                blob,
            )
            print('action: updated', existing['id'])
        else:
            await conn.execute('UPDATE youtube_oauth_apps SET is_default = FALSE')
            row = await conn.fetchrow(
                'INSERT INTO youtube_oauth_apps (name, client_id, encrypted_client_secret, '
                'is_default, created_at, updated_at) VALUES ($1, $2, $3, TRUE, NOW(), NOW()) '
                'RETURNING id',
                'CAMXORA YouTube',
                client_id,
                blob,
            )
            print('action: created', row['id'])
        stored = await conn.fetchrow(
            'SELECT encrypted_client_secret FROM youtube_oauth_apps WHERE client_id = $1',
            client_id,
        )
        print('roundtrip_ok:', enc.decrypt(bytes(stored['encrypted_client_secret'])) == secret)
        print('default_apps:', await conn.fetchval(
            'SELECT count(*) FROM youtube_oauth_apps WHERE is_default'
        ))
    finally:
        await conn.close()


asyncio.run(main())
'''


def main() -> int:
    host, user, password = resolve_production_ssh(load_production_secrets())
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        payload = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
        _i, out, err = client.exec_command(
            f"echo {payload} | base64 -d | sudo tee /tmp/_register_yt_app.py >/dev/null"
        )
        print(out.read().decode("utf-8", "replace").strip())
        e = err.read().decode("utf-8", "replace").strip()
        if e:
            print("[stderr]", e)

        cmd = (
            "cd /opt/camxora/repo && "
            "sudo env PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/_register_yt_app.py"
        )
        _i, out, err = client.exec_command(cmd)
        print(out.read().decode("utf-8", "replace").strip())
        e = err.read().decode("utf-8", "replace").strip()
        if e:
            print("[stderr]", e)

        client.exec_command("sudo rm -f /tmp/_register_yt_app.py")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
