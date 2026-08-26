#!/bin/bash
set -euo pipefail
APPLY="${APPLY:-0}"
echo "HOST=$(hostname) APPLY=$APPLY"
if ip -4 addr | grep -q '82.197.71.248'; then
  echo "Refusing production host"
  exit 1
fi
echo "=== credits snapshot before web leftover apply ==="
python3 /tmp/credits_cutover_snapshot.py dump /tmp/credits-snapshot-before.csv
sudo -u camxora bash -lc "cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && APPLY=$APPLY python /tmp/web_ledger_conversion.py"
echo "=== credits snapshot after web leftover apply ==="
python3 /tmp/credits_cutover_snapshot.py dump /tmp/credits-snapshot-after.csv
python3 /tmp/credits_cutover_snapshot.py diff /tmp/credits-snapshot-before.csv /tmp/credits-snapshot-after.csv
echo WEB_LEDGER_SANDBOX_OK
