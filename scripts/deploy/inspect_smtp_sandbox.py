#!/usr/bin/env python3
"""Inspect sandbox SMTP config and optionally send a test verification email."""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE_INSPECT = textwrap.dedent(
    '''
import re
from pathlib import Path

env = Path("/opt/camxora/repo/platform_api/.env")
keys = (
    "PLATFORM_SMTP_HOST",
    "PLATFORM_SMTP_PORT",
    "PLATFORM_SMTP_USER",
    "PLATFORM_SMTP_USE_TLS",
    "PLATFORM_EMAIL_FROM_NAME",
    "PLATFORM_EMAIL_FROM_ADDRESS",
)
for line in env.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    key, _, value = line.partition("=")
    if key in keys:
        print(f"{key}={value}")
    if key == "PLATFORM_SMTP_PASSWORD":
        print(f"{key}={'set' if value.strip() else 'empty'}")
'''
)

REMOTE_SEND = textwrap.dedent(
    '''
import asyncio
import sys

sys.path.insert(0, "/opt/camxora/repo")
from platform_api.services.email_service import send_verification_email

to = sys.argv[1]
ok = send_verification_email(to, "123456", "Test User")
print("SEND_OK" if ok else "SEND_FAIL")
'''
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-test", metavar="EMAIL", help="Send test verification email to address")
    args = parser.parse_args()

    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )

    remote_inspect = "/tmp/inspect_smtp.py"
    sftp = client.open_sftp()
    with sftp.file(remote_inspect, "w") as fh:
        fh.write(REMOTE_INSPECT)
    sftp.close()

    _, stdout, stderr = client.exec_command(
        "grep PLATFORM_SMTP /opt/camxora/repo/platform_api/.env 2>/dev/null || echo NO_SMTP_VARS_IN_ENV"
    )
    out = stdout.read().decode().strip()
    for line in out.splitlines():
        if "PASSWORD" in line:
            print("PLATFORM_SMTP_PASSWORD=***")
        else:
            print(line)

    _, stdout, _ = client.exec_command(
        "journalctl -u camxora-api -n 300 --no-pager 2>/dev/null | grep -i email | tail -8 || true"
    )
    logs = stdout.read().decode().strip()
    if logs:
        print("\nRecent email log lines:")
        print(logs)

    if args.send_test:
        remote_send = "/tmp/send_test_email.py"
        sftp = client.open_sftp()
        with sftp.file(remote_send, "w") as fh:
            fh.write(REMOTE_SEND)
        sftp.close()
        _, stdout, stderr = client.exec_command(
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && set +a && "
            f"/opt/camxora/repo/platform_api/.venv/bin/python {remote_send} {args.send_test!r}'"
        )
        print(stdout.read().decode().strip())
        err = stderr.read().decode().strip()
        if err:
            print(err, file=sys.stderr)

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
