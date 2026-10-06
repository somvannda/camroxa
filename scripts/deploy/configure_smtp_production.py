#!/usr/bin/env python3
"""Configure production SMTP in platform_api/.env from .deploy/secrets.env."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

REMOTE_PY = textwrap.dedent(
    '''
import sys
from pathlib import Path

env_path = Path("/opt/camxora/repo/platform_api/.env")
pairs = sys.argv[1].split("\\0")
updates = {}
for pair in pairs:
    if not pair or "=" not in pair:
        continue
    key, _, value = pair.partition("=")
    updates[key] = value

lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
seen = set()
out = []
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key, _, _ = line.partition("=")
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
env_path.write_text("\\n".join(out) + "\\n", encoding="utf-8")
print("SMTP_CONFIGURED")
for key in sorted(updates):
    if "PASSWORD" in key:
        print(f"{key}=***")
    else:
        print(f"{key}={updates[key]}")
'''
)


def main() -> int:
    secrets = load_production_secrets()
    keys = (
        "PLATFORM_SMTP_HOST",
        "PLATFORM_SMTP_PORT",
        "PLATFORM_SMTP_USER",
        "PLATFORM_SMTP_PASSWORD",
        "PLATFORM_SMTP_USE_TLS",
        "PLATFORM_EMAIL_FROM_NAME",
        "PLATFORM_EMAIL_FROM_ADDRESS",
    )
    updates = {key: secrets.get(key, "").strip() for key in keys}
    if not updates["PLATFORM_SMTP_HOST"]:
        print("ERROR: Set PLATFORM_SMTP_HOST in .deploy/secrets.env first.")
        return 1
    if not updates["PLATFORM_SMTP_USER"] or not updates["PLATFORM_SMTP_PASSWORD"]:
        print("ERROR: Set PLATFORM_SMTP_USER and PLATFORM_SMTP_PASSWORD in .deploy/secrets.env.")
        return 1
    if not updates["PLATFORM_SMTP_PORT"]:
        updates["PLATFORM_SMTP_PORT"] = "587"
    if not updates["PLATFORM_SMTP_USE_TLS"]:
        updates["PLATFORM_SMTP_USE_TLS"] = "true"
    if not updates["PLATFORM_EMAIL_FROM_NAME"]:
        updates["PLATFORM_EMAIL_FROM_NAME"] = "Camxora"
    if not updates["PLATFORM_EMAIL_FROM_ADDRESS"]:
        updates["PLATFORM_EMAIL_FROM_ADDRESS"] = updates["PLATFORM_SMTP_USER"]

    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        print(f"ERROR: refusing non-production host: {host}")
        return 1

    payload = "\0".join(f"{k}={v}" for k, v in updates.items())
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote_py = "/tmp/configure_smtp_prod.py"
    sftp = client.open_sftp()
    with sftp.file(remote_py, "w") as fh:
        fh.write(REMOTE_PY)
    sftp.close()

    cmd = (
        f"sudo -u camxora bash -lc '/opt/camxora/repo/platform_api/.venv/bin/python {remote_py} {payload!r}' "
        "&& chown camxora:camxora /opt/camxora/repo/platform_api/.env "
        "&& systemctl restart camxora-api"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode().strip())
    err = stderr.read().decode().strip()
    if err:
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
