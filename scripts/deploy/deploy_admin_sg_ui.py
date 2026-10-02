"""Production hotfix: add the Signup Guard tab to the admin portal.

Uploads the section component, hook, types and the patched settings/index.tsx
into /opt/camxora/repo/admin_portal, backs up the replaced index, rebuilds the
portal on the server, restarts camxora-admin and verifies the new markers in
the built bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
STAGE = DEPLOY / "_sg_stage"
ADMIN = "/opt/camxora/repo/admin_portal"

FILES = [
    # (local staged file, remote rel path under admin_portal/src, is_replacement)
    ("signup-domain-guard-section.tsx", "src/pages/settings/signup-domain-guard-section.tsx", False),
    ("use-signup-domain-guard.ts", "src/hooks/use-signup-domain-guard.ts", False),
    ("signup-domain-guard-types.ts", "src/types/signup-domain-guard.ts", False),
    ("settings-index.prod.tsx", "src/pages/settings/index.tsx", True),
]


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()

        # Backup the file we replace.
        bak_cmd = (
            "TS=$(date +%Y%m%d-%H%M%S); "
            f"cp {ADMIN}/src/pages/settings/index.tsx {ADMIN}/src/pages/settings/index.tsx.bak.signup-guard-$TS; "
            "echo index_backup_done"
        )
        _, out, _ = client.exec_command(bak_cmd)
        print(out.read().decode(errors="replace"))

        for local_name, remote_rel, is_replacement in FILES:
            remote = f"{ADMIN}/{remote_rel}"
            with sftp.file(remote, "wb") as fh:
                fh.write((STAGE / local_name).read_bytes())
            print(f"uploaded {remote_rel}" + (" (replacement)" if is_replacement else " (new)"))

        sftp.close()

        cmd = """set -e
REPO=/opt/camxora/repo/admin_portal
chown -R camxora:camxora $REPO/src/pages/settings/signup-domain-guard-section.tsx \\
  $REPO/src/hooks/use-signup-domain-guard.ts $REPO/src/types/signup-domain-guard.ts \\
  $REPO/src/pages/settings/index.tsx
echo "--- build admin_portal ---"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
echo build_exit_ok
systemctl restart camxora-admin || true
sleep 2
systemctl is-active camxora-admin || true
echo "--- markers in dist ---"
grep -rl "signup-domain-guard" /opt/camxora/repo/admin_portal/dist 2>/dev/null | head -5 || echo NO_SG_MARKER
grep -rl "Signup Guard" /opt/camxora/repo/admin_portal/dist 2>/dev/null | head -5 || echo NO_TAB_MARKER
echo UI_DEPLOY_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR", err[-3000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
