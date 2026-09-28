"""Sandbox-only: run leftover mint + grant + flag On for a dedicated test license.

Refuses production host. Does not call Suno.
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
PROD_IP = "82.197.71.248"
OUT_CSV = ROOT / "docs" / "credits-only-sandbox-conversion-dry-run.csv"
UPLOADS = [
    (
        ROOT / "platform_api/services/v2/credit_service.py",
        "/opt/camxora/repo/platform_api/services/v2/credit_service.py",
    ),
    (
        DEPLOY / "_credits_only_sandbox_cutover_test.py",
        "/tmp/credits_only_sandbox_cutover_test.py",
    ),
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
        for local, remote in UPLOADS:
            data = local.read_bytes().replace(b"\r\n", b"\n")
            with sftp.file(remote, "wb") as handle:
                handle.write(data)
            print(f"uploaded {local.name}")
        sftp.close()
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing production host
  exit 1
fi
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/platform_api/services/v2/credit_service.py
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api || { journalctl -u camxora-api -n 40 --no-pager; exit 1; }
sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/credits_only_sandbox_cutover_test.py'
systemctl is-active camxora-api || { journalctl -u camxora-api -n 40 --no-pager; exit 1; }
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
            csv_text = out[begin + len("===CSV_BEGIN===") : end].strip("\r\n") + "\n"
            OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
            OUT_CSV.write_text(csv_text, encoding="utf-8")
            print(f"WROTE {OUT_CSV}")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
