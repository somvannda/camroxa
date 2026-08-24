"""Production leftover CutLuy remaining -> credit_wallets.

DO NOT RUN until the user explicitly asks to deploy production and mint
existing-user leftover. Default is usage + exit.

  python scripts/deploy/run_web_ledger_conversion_production.py --i-mean-production
  python scripts/deploy/run_web_ledger_conversion_production.py --i-mean-production --apply
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
REMOTE_PY = DEPLOY / "_web_ledger_conversion.py"


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
    if "--i-mean-production" not in sys.argv:
        print(
            "Usage:\n"
            "  python scripts/deploy/run_web_ledger_conversion_production.py --i-mean-production\n"
            "  python scripts/deploy/run_web_ledger_conversion_production.py --i-mean-production --apply\n"
            "Refusing to run. This is the existing-user leftover mint for production."
        )
        return 2
    apply = "1" if "--apply" in sys.argv else "0"
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host} APPLY={apply}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/web_ledger_conversion.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        cmd = f"""
set -e
if ! ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing non-production host
  exit 1
fi
if ip -4 addr | grep -q '46.250.235.83'; then
  echo Refusing sandbox host
  exit 1
fi
sudo -u camxora bash -lc "cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && APPLY={apply} python /tmp/web_ledger_conversion.py"
echo WEB_LEDGER_PRODUCTION_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "WEB_LEDGER_PRODUCTION_OK" not in out:
            raise SystemExit("Production web-ledger conversion did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
