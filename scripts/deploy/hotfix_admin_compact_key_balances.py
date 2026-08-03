#!/usr/bin/env python3
"""Deploy compact key-balances panel to sandbox + production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

FILES = [
    "admin_portal/src/components/dashboard/provider-key-balances-panel.tsx",
    "admin_portal/src/hooks/use-dashboard.ts",
]

HOSTS = [
    ("sandbox", "46.250.235.83", "secrets.sandbox.env", ("SANDBOX_VPS_HOST", "SANDBOX_VPS_USER", "SANDBOX_VPS_PASSWORD")),
    ("production", "82.197.71.248", "secrets.production.env", ("PRODUCTION_VPS_HOST", "PRODUCTION_VPS_USER", "PRODUCTION_VPS_PASSWORD")),
]


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def deploy(label: str, expected_host: str, secrets_file: str, keys: tuple[str, str, str]) -> None:
    secrets = load_env(secrets_file)
    host = secrets.get(keys[0]) or secrets["VPS_HOST"]
    user = secrets.get(keys[1]) or secrets["VPS_USER"]
    password = secrets.get(keys[2]) or secrets.get("VPS_PASSWORD")
    if host != expected_host:
        raise SystemExit(f"Refusing {label} host: {host}")
    print(f"Deploying compact balances UI → {label} ({host})")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"  uploaded {rel}")
        sftp.close()
        cmd = (
            "set -e; "
            "chown -R camxora:camxora /opt/camxora/repo/admin_portal/src; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'; "
            f"echo COMPACT_BALANCES_{label.upper()}_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace")[-2500:])
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err[-1000:], file=sys.stderr)
    finally:
        client.close()


def main() -> int:
    for label, host, secrets_file, keys in HOSTS:
        deploy(label, host, secrets_file, keys)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
