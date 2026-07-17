#!/usr/bin/env python3
"""Quick verify sandbox deploy state."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    cmd = r"""
timedatectl | grep -E 'Time zone|Local time'
systemctl is-active camxora-portal nginx
grep -A6 'server_name app.sandbox' /etc/nginx/sites-available/camxora-sandbox | head -20
curl -sf https://api.sandbox.camxora.com/api/v1/auth/signup-mode; echo
curl -sf https://app.sandbox.camxora.com/api/v1/auth/signup-mode; echo
curl -sI https://app.sandbox.camxora.com/invite | head -8
"""
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err:
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
