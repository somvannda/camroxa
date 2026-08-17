#!/usr/bin/env python3
"""File-scoped sandbox hotfix: skip leftover Alembic sibling heads on startup."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

FILES = [
    "platform_api/migrations/runner.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="alembic-leftover-hotfix-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/alembic-leftover-api.tar.gz -C $REPO
chown camxora:camxora $REPO/platform_api/migrations/runner.py
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
echo === leftover skip probe ===
if [ -f /tmp/084_provider_balance_events.py.bak ]; then
  cp /tmp/084_provider_balance_events.py.bak $REPO/platform_api/migrations/versions/084_provider_balance_events.py
  chown camxora:camxora $REPO/platform_api/migrations/versions/084_provider_balance_events.py
  systemctl restart camxora-api
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
    echo leftover_attempt_$i health=$code
    if [ "$code" = "200" ]; then break; fi
    sleep 2
  done
  test "$code" = "200"
  journalctl -u camxora-api -n 80 --no-pager | grep -E 'Skipping leftover Alembic|alembic upgrade|084_provider_balance' || true
  rm -f $REPO/platform_api/migrations/versions/084_provider_balance_events.py
else
  echo SKIP leftover probe, bak missing
fi
echo === streaming home ===
curl -sS -m 10 -o /tmp/sbx_home.json -w 'home_http=%{http_code}\n' http://127.0.0.1:8100/api/v1/public/streaming/home
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("/tmp/sbx_home.json").read_text(encoding="utf-8"))
print("tracks", len(data.get("recent_tracks") or []))
PY
echo ALEMBIC_LEFTOVER_HOTFIX_DONE
"""
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/alembic-leftover-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        out_path = Path(__file__).with_name("_tmp_hotfix_alembic_leftover.out")
        out_path.write_text(out + ("\nSTDERR:\n" + err if err.strip() else ""), encoding="utf-8")
        print(f"Wrote {out_path} ({len(out)} chars)")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
