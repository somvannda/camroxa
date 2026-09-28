"""Sandbox leftover conversion DRY-RUN only. Does not touch production.

Usage:
  python scripts/deploy/run_credits_only_sandbox_leftover_dryrun.py
"""

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
REMOTE_PY = DEPLOY / "_credits_only_sandbox_leftover_dryrun.py"
OUT_CSV = ROOT / "docs" / "credits-only-sandbox-conversion-dry-run.csv"


def _secrets_path() -> Path:
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            return path
    raise SystemExit("No .deploy/secrets.sandbox.env found")


def load_sandbox() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in _secrets_path().read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host} APPLY=0 FLAG_ON=0")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/credits_only_sandbox_leftover_dryrun.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        cmd = r"""
set -euo pipefail
if ip -4 addr | grep -q '82.197.71.248'; then
  echo "Refusing production host"
  exit 1
fi
echo HOST=$(hostname) APPLY=0 FLAG_ON=0
sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/credits_only_sandbox_leftover_dryrun.py'
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        begin = out.find("===CSV_BEGIN===")
        end = out.find("===CSV_END===")
        if begin != -1 and end != -1:
            csv_text = out[begin + len("===CSV_BEGIN==="):end].strip("\r\n") + "\n"
            OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
            OUT_CSV.write_text(csv_text, encoding="utf-8")
            print(f"WROTE {OUT_CSV}")
        else:
            print("ASK_CURSOR: dry-run stdout missing CSV markers")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
