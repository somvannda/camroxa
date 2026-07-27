#!/usr/bin/env python3
"""Production hotfix: admin set-password + plan form regroup + addon daily scale.

File-scoped only — does NOT sync full platform_api (keeps DistroKid out).
Uses committed password-only users.py from .dbg/_prod_hotfix_users.py when present.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

REPO = Path(__file__).resolve().parents[2]

# (local_path, remote_rel under /opt/camxora/repo/)
UPLOADS: list[tuple[Path, str]] = [
    (
        REPO / ".dbg" / "_prod_hotfix_users.py",
        "platform_api/routers/users.py",
    ),
    (
        REPO / "platform_api/services/subscription_entitlement_service.py",
        "platform_api/services/subscription_entitlement_service.py",
    ),
    (
        REPO / "platform_api/services/usage_enforcement_service.py",
        "platform_api/services/usage_enforcement_service.py",
    ),
    (
        REPO / "platform_api/routers/credits.py",
        "platform_api/routers/credits.py",
    ),
    (
        REPO / "admin_portal/src/hooks/use-users.ts",
        "admin_portal/src/hooks/use-users.ts",
    ),
    (
        REPO / "admin_portal/src/pages/users/index.tsx",
        "admin_portal/src/pages/users/index.tsx",
    ),
    (
        REPO / "admin_portal/src/pages/users/user-detail.tsx",
        "admin_portal/src/pages/users/user-detail.tsx",
    ),
    (
        REPO / "admin_portal/src/pages/plans/index.tsx",
        "admin_portal/src/pages/plans/index.tsx",
    ),
    (
        REPO / "admin_portal/src/pages/plans/plan-limits-fields.tsx",
        "admin_portal/src/pages/plans/plan-limits-fields.tsx",
    ),
]


def _run(client, cmd: str, timeout: int = 120) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    safe = text.encode("ascii", errors="replace").decode("ascii")
    return code, safe


def main() -> int:
    for local, _rel in UPLOADS:
        if not local.is_file():
            print(f"MISSING local file: {local}")
            return 1
        raw = local.read_text(encoding="utf-8", errors="replace").lower()
        if "distrokid" in raw and "users.py" in str(local):
            print(f"REFUSING upload with distrokid: {local}")
            return 1

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    for local, rel in UPLOADS:
        remote = f"/opt/camxora/repo/{rel}"
        print(f"Uploading {rel} ...")
        parent = str(Path(remote).parent).replace("\\", "/")
        client.exec_command(f"mkdir -p {parent}")
        sftp.put(str(local), remote)
    sftp.close()

    print("Restarting API ...")
    code, out = _run(
        client,
        "chown -R camxora:camxora /opt/camxora/repo/platform_api /opt/camxora/repo/admin_portal/src"
        " && systemctl restart camxora-api && sleep 2 && systemctl is-active camxora-api"
        " && grep -n set-password /opt/camxora/repo/platform_api/routers/users.py | head -3"
        " && grep -n effective_daily_limit_for_operation"
        " /opt/camxora/repo/platform_api/services/subscription_entitlement_service.py | head -3"
        " && test ! -f /opt/camxora/repo/platform_api/routers/distrokid.py"
        " && echo API_HOTFIX_OK",
        timeout=90,
    )
    print(out[-5000:])
    if code != 0:
        client.close()
        return code

    print("Building admin portal (may take a few minutes) ...")
    code, out = _run(
        client,
        "sudo -u camxora bash -lc "
        "'cd /opt/camxora/repo/admin_portal && CI=1 npm run build'"
        " && echo ADMIN_BUILD_OK",
        timeout=900,
    )
    print(out[-5000:])
    client.close()
    print(f"exit={code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
