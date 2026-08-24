"""Turn sandbox credits_only_v3_charge back off. Does not touch production."""

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
SQL = """
INSERT INTO system_settings (key, value, value_type, updated_at)
VALUES ('credits_only_v3_charge', 'false', 'boolean', NOW())
ON CONFLICT (key) DO UPDATE
SET value = 'false', value_type = 'boolean', updated_at = NOW();
SELECT key, value FROM system_settings WHERE key = 'credits_only_v3_charge';
"""


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
        sftp = client.open_sftp()
        with sftp.file("/tmp/turn_off_v3_flag.sql", "wb") as remote:
            remote.write(SQL.encode("utf-8"))
        sftp.close()
        _, stdout, stderr = client.exec_command(
            "sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -f /tmp/turn_off_v3_flag.sql",
            get_pty=True,
            timeout=30,
        )
        sys.stdout.buffer.write(stdout.read())
        err = stderr.read()
        if err.strip():
            sys.stderr.buffer.write(err[-1000:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
