"""Verify sandbox admin dist + API after the v3 reports hotfix."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (
    ROOT,
    Path(r"G:\Developments\Projects\Camxora\MusicGenerator"),
)
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"


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
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        cmd = r"""
set -e
systemctl is-active camxora-api
grep -R -l 'Live generate path' /opt/camxora/repo/admin_portal/dist/assets | head
grep -R -l 'Grant issued' /opt/camxora/repo/admin_portal/dist/assets | head
curl -sS -o /dev/null -w 'admin_http=%{http_code}\n' https://admin.sandbox.camxora.com/
echo ADMIN_V3_DIST_OK
"""
        _, stdout, _stderr = client.exec_command(cmd, get_pty=True, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace").encode("ascii", errors="replace").decode("ascii")
        print(out)
        if "ADMIN_V3_DIST_OK" not in out:
            raise SystemExit("verify failed")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
