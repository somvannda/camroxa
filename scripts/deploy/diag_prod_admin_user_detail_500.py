#!/usr/bin/env python3
"""Verify production admin user-detail import after hotfix (read-only)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
echo '=== import line ==='
grep -n 'upload_paths import' /opt/camxora/repo/platform_api/routers/users.py
echo '=== unauth details status (expect 401/403, not 500) ==='
curl -sS -o /tmp/ud.json -w 'HTTP_%{http_code} bytes=%{size_download}\n' --max-time 10 \
  http://127.0.0.1:8100/api/v1/users/ad6eda59-18f0-4ffb-b80e-fdae60028980/details
head -c 200 /tmp/ud.json; echo
echo '=== replay profile loop as camxora ==='
sudo -u camxora env PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -u - <<'PY'
import asyncio, os, traceback
from uuid import UUID
from pathlib import Path

# Load .env without bash mangling
env_path = Path('/opt/camxora/repo/platform_api/.env')
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, _, v = line.partition('=')
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

TARGET = UUID('ad6eda59-18f0-4ffb-b80e-fdae60028980')

async def main():
    import asyncpg
    from platform_api.routers.users import ChannelProfileAdminSummary, upload_path_exists
    print('NAME_OK', callable(upload_path_exists))
    dsn = os.environ['PLATFORM_DATABASE_URL'].replace('postgresql+asyncpg://','postgresql://',1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    rows = await pool.fetch(
        'SELECT id, name, folder_name, run_prefix, created_at, logo_path, video_template_id, reel_template_id, output_resolution, image_config, youtube_config FROM channel_profiles WHERE user_id = $1',
        TARGET,
    )
    built = []
    for row in rows:
        image_cfg = row['image_config'] or {}
        youtube_cfg = row['youtube_config'] or {}
        cover_paths = image_cfg.get('cover_paths') or []
        summary = ChannelProfileAdminSummary(
            id=str(row['id']),
            name=row['name'],
            folder_name=row.get('folder_name'),
            run_prefix=str(row.get('run_prefix') or '').strip() or None,
            created_at=row['created_at'],
            logo_available=upload_path_exists(row.get('logo_path')),
            cover_count=len([x for x in cover_paths if upload_path_exists(x)]),
            output_resolution=str(row.get('output_resolution') or '').strip() or None,
            video_template_id=str(row.get('video_template_id') or '').strip() or None,
            keywords=[str(x).strip() for x in (youtube_cfg.get('keywords') or []) if str(x).strip()],
            tags=[str(x).strip() for x in (youtube_cfg.get('tags') or []) if str(x).strip()],
        )
        built.append(summary.id)
    print('PROFILES_OK', built)
    await pool.close()

asyncio.run(main())
PY
echo VERIFY_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 60) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535)
            if not chunk:
                break
            out += chunk
        if chan.recv_stderr_ready():
            out += chan.recv_stderr(65535)
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            while chan.recv_stderr_ready():
                out += chan.recv_stderr(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.05)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=55), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
