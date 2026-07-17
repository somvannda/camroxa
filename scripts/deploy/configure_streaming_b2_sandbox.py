#!/usr/bin/env python3
"""Save Backblaze streaming settings on sandbox and verify upload."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    key_id = os.environ.get("B2_KEY_ID", "").strip()
    app_key = os.environ.get("B2_APPLICATION_KEY", "").strip()
    if not key_id or not app_key:
        print("Set B2_KEY_ID and B2_APPLICATION_KEY in the environment before running.")
        return 1

    bucket = os.environ.get("B2_BUCKET", "camroxa-song-storage").strip()
    region = os.environ.get("B2_REGION", "us-east-005").strip()
    endpoint = os.environ.get("B2_ENDPOINT", f"https://s3.{region}.backblazeb2.com").strip()
    cdn_base_url = os.environ.get("B2_CDN_BASE_URL", "").strip()
    ttl = int(os.environ.get("B2_STREAM_URL_TTL_SECONDS", "3600"))

    remote = f'''
import asyncio
import os
import sys

sys.path.insert(0, "/opt/camxora/repo")

async def main() -> int:
    import asyncpg
    import os

    from platform_api.dependencies import set_db_pool
    from platform_api.services.storage_service import StorageService
    from platform_api.services.streaming_config_service import (
        resolve_streaming_storage_config,
        save_streaming_storage_config,
    )

    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    try:
        public = await save_streaming_storage_config(
            pool,
            key_id={key_id!r},
            application_key={app_key!r},
            bucket={bucket!r},
            region={region!r},
            endpoint={endpoint!r},
            cdn_base_url={cdn_base_url!r},
            stream_url_ttl_seconds={ttl},
        )
        print("configured:", public.configured)
        print("bucket:", public.bucket)
        print("endpoint:", public.endpoint)
        print("cdn_base_url:", public.cdn_base_url or "(presigned B2 URLs)")
        print("key_id_masked:", public.key_id_masked)
        print("application_key_masked:", public.application_key_masked)

        config = await resolve_streaming_storage_config(pool)
        storage = StorageService.from_config(config)
        test_key = "__healthcheck__/streaming-config-probe.txt"
        await storage.upload_bytes(
            key=test_key,
            data=b"camxora streaming config ok",
            content_type="text/plain",
        )
        print("probe_upload: success", test_key)
        return 0
    finally:
        await pool.close()

raise SystemExit(asyncio.run(main()))
'''

    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/configure_streaming_b2.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(remote)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && "
        "export $(grep -E \"^(PLATFORM_DATABASE_URL|ENCRYPTION_MASTER_KEY)=\" platform_api/.env | xargs) && "
        f"PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
