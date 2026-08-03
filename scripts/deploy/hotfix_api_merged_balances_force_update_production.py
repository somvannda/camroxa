#!/usr/bin/env python3
"""Upload merged production API: provider balances + Force-update form version."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

ROOT = Path(__file__).resolve().parents[2]
DBG = ROOT / ".dbg"

UPLOADS = (
    (DBG / "admin_merged_prod.py", "/opt/camxora/repo/platform_api/routers/admin.py"),
    (
        DBG / "desktop_release_upload_merged_prod.py",
        "/opt/camxora/repo/platform_api/services/desktop_release_upload_service.py",
    ),
    (DBG / "dependencies_prod.py", "/opt/camxora/repo/platform_api/dependencies.py"),
    (DBG / "wire_dependencies_prod.py", "/opt/camxora/repo/platform_api/wire_dependencies.py"),
    (
        DBG / "provider_key_balance_service_prod.py",
        "/opt/camxora/repo/platform_api/services/provider_key_balance_service.py",
    ),
)


def main() -> int:
    for local, _ in UPLOADS:
        if not local.is_file():
            print(f"Missing {local}")
            return 1

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    for local, remote in UPLOADS:
        print(f"Uploading {local.name} -> {remote}")
        sftp.put(str(local), remote)
    sftp.close()

    cmd = r"""
set -e
chown -R camxora:camxora /opt/camxora/repo/platform_api
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
python3 - <<'PY'
from pathlib import Path
admin = Path('/opt/camxora/repo/platform_api/routers/admin.py').read_text(encoding='utf-8', errors='replace')
print('ROUTE_OK' if 'provider-key-balances' in admin else 'ROUTE_MISSING')
print('FORCE_OK' if 'Version is required. Set it in the Software Update form' in admin else 'FORCE_MISSING')
svc = Path('/opt/camxora/repo/platform_api/services/provider_key_balance_service.py')
print('SERVICE_OK' if svc.is_file() else 'SERVICE_MISSING')
PY
# health via nginx or local
curl -s -o /dev/null -w 'HEALTH_LOCAL_%{http_code}\n' --max-time 5 http://127.0.0.1:8000/health || true
curl -s -o /dev/null -w 'HEALTH_API_%{http_code}\n' --max-time 5 https://api.camxora.com/health || true
echo MERGED_API_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    print(out)
    if err.strip():
        print(err)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
