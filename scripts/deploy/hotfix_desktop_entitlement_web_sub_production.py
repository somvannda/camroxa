"""Production-only file-scoped hotfix: /users/me honors paid web subscriptions.

Uploads platform_api/routers/users.py to the production API host and restarts
camxora-api. Refuses to run against the sandbox host.
"""

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

PRODUCTION_HOST = "82.197.71.248"
SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/routers/users.py",
]


def load_production() -> dict[str, str]:
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.production.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.production.env")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
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
if ip -4 addr | grep -q '46.250.235.83'; then
  echo Refusing sandbox host
  exit 1
fi
chown -R camxora:camxora /opt/camxora/repo/platform_api/routers/users.py
PYBIN=$(command -v python3 || true)
if [ -z "$PYBIN" ] && [ -x /opt/camxora/repo/.venv/bin/python ]; then PYBIN=/opt/camxora/repo/.venv/bin/python; fi
if [ -n "$PYBIN" ]; then
  "$PYBIN" -c "import ast; ast.parse(open('/opt/camxora/repo/platform_api/routers/users.py').read())"
fi
grep -q '_fetch_active_web_plan' /opt/camxora/repo/platform_api/routers/users.py
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api || { journalctl -u camxora-api -n 40 --no-pager; exit 1; }
echo DESKTOP_ENTITLEMENT_WEB_SUB_PRODUCTION_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "DESKTOP_ENTITLEMENT_WEB_SUB_PRODUCTION_OK" not in out:
            raise SystemExit("Production entitlement hotfix did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
