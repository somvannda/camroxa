#!/usr/bin/env python3
"""Correct historical audit_logs timestamps stored with utcnow()+local TZ bug."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
sudo -u postgres psql -d camxora_platform <<'SQL'
SELECT COUNT(*) AS rows_before FROM audit_logs;
UPDATE audit_logs
SET created_at = created_at + interval '7 hours'
WHERE created_at < TIMESTAMPTZ '2026-07-16 15:30:00+07';
SELECT COUNT(*) AS rows_after FROM audit_logs;
SELECT created_at FROM audit_logs ORDER BY created_at DESC LIMIT 3;
SQL
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
