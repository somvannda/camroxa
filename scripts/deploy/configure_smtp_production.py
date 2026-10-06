#!/usr/bin/env python3
"""Configure production SMTP in platform_api/.env from production secrets.

The keys are uploaded as a JSON file (not shell args): a NUL-separated payload
passed through ``repr()``/argv is misinterpreted by the shell, which previously
corrupted ``.env`` and leaked the password into the command line.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
KEYS = (
    "PLATFORM_SMTP_HOST",
    "PLATFORM_SMTP_PORT",
    "PLATFORM_SMTP_USER",
    "PLATFORM_SMTP_PASSWORD",
    "PLATFORM_SMTP_USE_TLS",
    "PLATFORM_EMAIL_FROM_NAME",
    "PLATFORM_EMAIL_FROM_ADDRESS",
)
REMOTE_PY = r'''
import json, sys
from pathlib import Path
env_path = Path("/opt/camxora/repo/platform_api/.env")
updates = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
seen, out = set(), []
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        out.append(line); continue
    key, _, _ = line.partition("=")
    if key in updates:
        out.append(f"{key}={updates[key]}"); seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print("SMTP_CONFIGURED")
for key in sorted(updates):
    print(f"{key}=" + ("***" if "PASSWORD" in key else str(updates[key])))
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        print(f"ERROR: refusing non-production host: {host}")
        return 1

    updates = {key: str(secrets.get(key, "")).strip() for key in KEYS}
    if not updates["PLATFORM_SMTP_HOST"]:
        print("ERROR: Set PLATFORM_SMTP_HOST in the production secrets first.")
        return 1
    if not updates["PLATFORM_SMTP_USER"] or not updates["PLATFORM_SMTP_PASSWORD"]:
        print("ERROR: Set PLATFORM_SMTP_USER and PLATFORM_SMTP_PASSWORD in the production secrets.")
        return 1
    if not updates["PLATFORM_SMTP_PORT"]:
        updates["PLATFORM_SMTP_PORT"] = "587"
    if not updates["PLATFORM_SMTP_USE_TLS"]:
        updates["PLATFORM_SMTP_USE_TLS"] = "true"
    if not updates["PLATFORM_EMAIL_FROM_NAME"]:
        updates["PLATFORM_EMAIL_FROM_NAME"] = "Camxora"
    if not updates["PLATFORM_EMAIL_FROM_ADDRESS"]:
        updates["PLATFORM_EMAIL_FROM_ADDRESS"] = updates["PLATFORM_SMTP_USER"]

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/smtp_updates.json", "wb") as fh:
            fh.write(json.dumps(updates).encode("utf-8"))
        with sftp.file("/tmp/configure_smtp_prod.py", "wb") as fh:
            fh.write(REMOTE_PY.encode("utf-8"))
        sftp.close()
        cmd = (
            "sudo -u camxora bash -lc '/opt/camxora/repo/platform_api/.venv/bin/python "
            "/tmp/configure_smtp_prod.py /tmp/smtp_updates.json' "
            "&& chown camxora:camxora /opt/camxora/repo/platform_api/.env "
            "&& systemctl restart camxora-api"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        print(stdout.read().decode("utf-8", errors="replace").strip())
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if err:
            print(err, file=sys.stderr)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
