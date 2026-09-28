"""Sandbox-only runner: upload and execute two real Suno generates."""

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
    print(f"Target sandbox host: {host}")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    local = DEPLOY / "_credits_only_sandbox_suno_generate.py"
    try:
        sftp = client.open_sftp()
        data = local.read_bytes().replace(b"\r\n", b"\n")
        with sftp.file("/tmp/credits_only_sandbox_suno_generate.py", "wb") as handle:
            handle.write(data)
        sftp.close()
        print("uploaded suno generate script")
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing production host
  exit 1
fi
sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/credits_only_sandbox_suno_generate.py'
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=420)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write(err[-3000:] + "\n")
        if "===SUNO_GENERATE_DONE===" not in out:
            raise SystemExit("Sandbox Suno generate did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
