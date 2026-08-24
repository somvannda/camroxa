"""Sandbox-only: set hidden-plan grants, dry-run leftover conversion, optional apply + flag.

Does not touch production. Default is dry-run only.
Usage:
  python scripts/deploy/run_credits_only_sandbox_cutover.py
  python scripts/deploy/run_credits_only_sandbox_cutover.py --apply --flag-on
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

SANDBOX_HOST = "46.250.235.83"
APPLY = "1" if "--apply" in sys.argv else "0"
FLAG_ON = "1" if "--flag-on" in sys.argv else "0"
REMOTE_SH = DEPLOY / "_credits_only_sandbox_cutover_remote.sh"
REMOTE_PY = DEPLOY / "_credits_only_sandbox_cutover.py"


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
    print(f"Target sandbox host: {host} APPLY={APPLY} FLAG_ON={FLAG_ON}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/credits_only_sandbox_cutover.sh", "wb") as remote:
            remote.write(REMOTE_SH.read_bytes().replace(b"\r\n", b"\n"))
        with sftp.file("/tmp/credits_only_sandbox_cutover.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        cmd = (
            "chmod +x /tmp/credits_only_sandbox_cutover.sh && "
            f"APPLY={APPLY} FLAG_ON={FLAG_ON} bash /tmp/credits_only_sandbox_cutover.sh"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
