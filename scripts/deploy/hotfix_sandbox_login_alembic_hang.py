#!/usr/bin/env python3
"""Unstick sandbox login: quarantine broken Alembic merge stubs and restart API."""

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
    "platform_api/migrations/versions/103_merge_credit_refund_heads.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}", flush=True)

    archive = Path(tempfile.mkdtemp(prefix="sandbox-login-hotfix-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote = r"""
set -e
REPO=/opt/camxora/repo
QDIR=/tmp/alembic-broken-stubs-20260817
mkdir -p "$QDIR"

echo '=== current api state ==='
systemctl is-active camxora-api || true
systemctl stop camxora-api || true

echo '=== deploy runner + linear 103 ==='
tar -xzf /tmp/sandbox-login-runner.tar.gz -C "$REPO"
chown camxora:camxora \
  "$REPO/platform_api/migrations/runner.py" \
  "$REPO/platform_api/migrations/versions/103_merge_credit_refund_heads.py"

echo '=== quarantine stubs ==='
python3 - <<'PY'
from pathlib import Path
import shutil
vers = Path("/opt/camxora/repo/platform_api/migrations/versions")
qdir = Path("/tmp/alembic-broken-stubs-20260817")
qdir.mkdir(parents=True, exist_ok=True)
needles = (
    "084_provider_balance_events",
    "e5077c52f2b7",
    "fffddbe8fbb3",
    "ff781163cfbb",
    "1f0ad008d202",
)
moved = []
for path in sorted(vers.glob("*.py")):
    if path.name.startswith("103_"):
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if any(needle in text for needle in needles):
        shutil.move(str(path), str(qdir / path.name))
        moved.append(path.name)
print("MOVED", ", ".join(moved) if moved else "NONE")
PY
find "$REPO/platform_api/migrations" -name '__pycache__' -type d -exec rm -rf {} + || true

echo '=== 103 preview ==='
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/migrations/versions/103_merge_credit_refund_heads.py")
print(p.read_text(encoding="utf-8", errors="replace")[:400] if p.exists() else "MISSING 103")
PY

echo '=== alembic heads ==='
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic heads'

echo '=== start api ==='
systemctl start camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
echo HEALTH_BODY
cat /tmp/sbx_health.json || true
echo
test "$code" = "200"

echo '=== login probe ==='
curl -sS -m 10 -o /tmp/sbx_login.json -w 'login_http=%{http_code}\n' \
  -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"probe@test.com","password":"wrongpassword"}'
cat /tmp/sbx_login.json || true
echo
echo SANDBOX_LOGIN_HOTFIX_DONE
"""
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/sandbox-login-runner.tar.gz", "wb") as remote_file:
            remote_file.write(archive.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(remote, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        out_path = Path(__file__).with_name("_tmp_hotfix_sandbox_login.out")
        out_path.write_text(out + ("\nSTDERR:\n" + err if err.strip() else ""), encoding="utf-8")
        print(out)
        print(f"Wrote {out_path} ({len(out)} chars)", flush=True)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
