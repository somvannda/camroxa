#!/usr/bin/env python3
"""Apply migration 102 refund idempotency index on sandbox (verify + fallback SQL)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect

SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_txn_refund_idempotency
ON credit_transactions (user_id, ref_id, reason)
WHERE direction = 'credit'
  AND ref_id IS NOT NULL
  AND reason LIKE 'refunded_%';
"""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}\n")
    client = ssh_connect(host, user, ensure_deploy_key(), password)

    remote = r"""
set -e
echo "=== Alembic current ==="
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic current' || true
echo ""
echo "=== Index before ==="
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_credit_txn_refund_idempotency';"
echo ""
echo "=== Apply index SQL (idempotent) ==="
sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c "CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_txn_refund_idempotency ON credit_transactions (user_id, ref_id, reason) WHERE direction = 'credit' AND ref_id IS NOT NULL AND reason LIKE 'refunded_%';"
echo ""
echo "=== Index after ==="
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT indexname FROM pg_indexes WHERE indexname = 'idx_credit_txn_refund_idempotency';"
echo ""
echo "VERIFY_COMPLETE"
"""
    _, stdout, stderr = client.exec_command(remote, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
