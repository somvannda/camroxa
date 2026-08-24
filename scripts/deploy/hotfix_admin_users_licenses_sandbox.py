"""Sandbox-only: users/licenses catalog recast + admin rebuild."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (
    ROOT,
    Path(r"D:\Development\Projects\Electron\MusicGenerator"),
)
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/routers/users.py",
    "platform_api/routers/licenses.py",
    "platform_api/repositories/credit_repo.py",
    "platform_api/CHANGELOG.md",
    "admin_portal/src/pages/users/index.tsx",
    "admin_portal/src/pages/licenses/index.tsx",
    "admin_portal/src/pages/usage/index.tsx",
    "admin_portal/src/pages/user-spent/index.tsx",
    "admin_portal/src/types/models.ts",
    "admin_portal/CHANGELOG.md",
    "docs/changelog/2026-08-23-admin-users-licenses-wallet.md",
    "docs/credits-only-api-platform-map.md",
]


def load_sandbox() -> dict[str, str]:
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.sandbox.env")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as handle:
                handle.write(local.read_bytes().replace(b"\r\n", b"\n"))
            print(f"uploaded {rel}")
        sftp.close()
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing production host
  exit 1
fi
python3 -m py_compile \
  /opt/camxora/repo/platform_api/routers/users.py \
  /opt/camxora/repo/platform_api/routers/licenses.py \
  /opt/camxora/repo/platform_api/repositories/credit_repo.py
systemctl restart camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
sleep 3
systemctl is-active camxora-api
echo ADMIN_USERS_LICENSES_SANDBOX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "ADMIN_USERS_LICENSES_SANDBOX_OK" not in out:
            raise SystemExit("Sandbox users/licenses hotfix did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
