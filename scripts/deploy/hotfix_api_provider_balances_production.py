#!/usr/bin/env python3
"""Restore provider-key-balance API files onto production (kept from main tree).

An earlier full platform_api sync from release/desktop-1.0.15 may have dropped
these files if they only lived on main. Re-upload the allowlisted set and
restart the API.
"""

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

MAIN_ROOT = Path(r"G:\Developments\Projects\Camxora\MusicGenerator")

# File-scoped: only provider-balance pieces + wiring from main.
FILES = (
    "platform_api/services/provider_key_balance_service.py",
    "platform_api/tests/test_provider_key_balance_service.py",
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)

    # Check whether service already exists on prod
    _, stdout, _ = client.exec_command(
        "test -f /opt/camxora/repo/platform_api/services/provider_key_balance_service.py "
        "&& echo HAS_SERVICE || echo MISSING_SERVICE"
    )
    presence = stdout.read().decode("utf-8", errors="replace")
    print(presence.strip())

    # Upload service file always (safe overwrite)
    sftp = client.open_sftp()
    for rel in FILES:
        local = MAIN_ROOT / rel
        if not local.is_file():
            print(f"Skip missing local: {rel}")
            continue
        remote = f"/opt/camxora/repo/{rel}"
        print(f"Uploading {rel}")
        parent = str(Path(remote).parent).replace("\\", "/")
        client.exec_command(f"mkdir -p {parent}")
        sftp.put(str(local), remote)
    sftp.close()

    # Patch admin.py / dependencies / wire_dependencies from main only if
    # provider-key-balances route is missing on production.
    _, stdout, _ = client.exec_command(
        "grep -c 'provider-key-balances' /opt/camxora/repo/platform_api/routers/admin.py || true"
    )
    count_raw = stdout.read().decode("utf-8", errors="replace").strip() or "0"
    print(f"provider-key-balances mentions in admin.py: {count_raw}")
    try:
        count = int(count_raw.splitlines()[-1])
    except ValueError:
        count = 0

    if count < 1:
        print("Route missing — uploading admin.py, dependencies.py, wire_dependencies.py from main")
        sftp = client.open_sftp()
        for rel in (
            "platform_api/routers/admin.py",
            "platform_api/dependencies.py",
            "platform_api/wire_dependencies.py",
        ):
            local = MAIN_ROOT / rel
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Uploading {rel}")
            sftp.put(str(local), remote)
        sftp.close()
        # Re-apply force-update publish fix from release tree (main may lack latest form-version logic)
        release = Path(__file__).resolve().parents[2]
        sftp = client.open_sftp()
        for rel in (
            "platform_api/routers/admin.py",
            "platform_api/services/desktop_release_upload_service.py",
        ):
            local = release / rel
            remote = f"/opt/camxora/repo/{rel}"
            print(f"Re-applying force-update fix: {rel}")
            sftp.put(str(local), remote)
        sftp.close()
        print(
            "NOTE: admin.py from release overwrote main — provider-balance route must exist "
            "on release or we need a merge. Checking..."
        )
        _, stdout, _ = client.exec_command(
            "grep -c 'provider-key-balances' /opt/camxora/repo/platform_api/routers/admin.py || true"
        )
        print("after release admin.py:", stdout.read().decode("utf-8", errors="replace").strip())

    cmd = r"""
set -e
chown -R camxora:camxora /opt/camxora/repo/platform_api
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
# quick presence check
python3 - <<'PY'
from pathlib import Path
p = Path('/opt/camxora/repo/platform_api/services/provider_key_balance_service.py')
print('SERVICE_OK' if p.is_file() else 'SERVICE_MISSING')
admin = Path('/opt/camxora/repo/platform_api/routers/admin.py').read_text(encoding='utf-8', errors='replace')
print('ROUTE_OK' if 'provider-key-balances' in admin else 'ROUTE_MISSING')
PY
curl -s -o /dev/null -w 'HEALTH_%{http_code}\n' http://127.0.0.1:8000/health || true
echo API_PROVIDER_BALANCE_DONE
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
