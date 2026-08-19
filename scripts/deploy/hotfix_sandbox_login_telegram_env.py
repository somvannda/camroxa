#!/usr/bin/env python3
"""Restore sandbox login: comment unknown Telegram env vars and unstick Alembic."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
REMOTE = r"""
set -e
REPO=/opt/camxora/repo
ENV=/opt/camxora/repo/platform_api/.env
QDIR=/tmp/alembic-broken-stubs-20260817
mkdir -p "$QDIR"

echo '=== config extra / telegram fields ==='
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/config.py")
text = p.read_text(encoding="utf-8", errors="replace")
print("has telegram_bot_token field:", "telegram_bot_token" in text)
print("telegram service exists:", Path("/opt/camxora/repo/platform_api/services/telegram_ops_alert_service.py").is_file())
print("main has telegram hooks:", "install_telegram_ops_hooks" in Path("/opt/camxora/repo/platform_api/main.py").read_text(encoding="utf-8", errors="replace"))
for line in text.splitlines():
    if "SettingsConfigDict" in line or ("extra" in line.lower() and ("forbid" in line.lower() or "ignore" in line.lower())):
        print("CFG", line.strip())
PY

echo '=== comment PLATFORM_TELEGRAM_* env (keep values) ==='
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/.env")
text = p.read_text(encoding="utf-8", errors="replace")
out = []
changed = 0
for line in text.splitlines(True):
    stripped = line.lstrip()
    if stripped.startswith("PLATFORM_TELEGRAM_") and not stripped.startswith("#"):
        key = stripped.split("=", 1)[0]
        out.append("#" + line if not line.startswith("#") else line)
        changed += 1
        print("commented", key)
    else:
        out.append(line)
p.write_text("".join(out), encoding="utf-8")
print("telegram_env_commented", changed)
PY
chown camxora:camxora "$ENV"

echo '=== quarantine broken alembic stubs ==='
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
find "$REPO/platform_api/migrations" -name "__pycache__" -type d -exec rm -rf {} + || true

echo '=== restart api ==='
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w "%{http_code}" http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
echo "=== health body ==="
head -c 300 /tmp/sbx_health.json; echo
echo "=== login probe ==="
curl -sS -m 10 -o /tmp/sbx_login.json -w "login_http=%{http_code}\n" \
  -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"probe@test.com","password":"wrongpassword"}' || true
head -c 400 /tmp/sbx_login.json; echo
ss -lntp | grep 8100 || echo "nothing on 8100"
if [ "$code" != "200" ]; then
  echo "=== journal tail ==="
  journalctl -u camxora-api -n 40 --no-pager --no-hostname
  exit 1
fi
echo RESTORE_DONE
"""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        path = DEPLOY / "_tmp_sandbox_login_restore.out"
        path.write_text(out + ("\nSSH STDERR:\n" + err if err.strip() else ""), encoding="utf-8")
        print(out)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


AUTH_IMPORT_REMOTE = r'''
set -e
python3 - <<'PY'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/routers/auth.py")
text = p.read_text(encoding="utf-8")
old = (
    "from platform_api.exceptions import (\n"
    "    AuthenticationError,\n"
    "    DuplicateError,\n"
    "    NotFoundError,\n"
    "    ValidationError,\n"
    ")"
)
new = (
    "from platform_api.exceptions import (\n"
    "    AccountLockedError,\n"
    "    AuthenticationError,\n"
    "    DuplicateError,\n"
    "    NotFoundError,\n"
    "    ValidationError,\n"
    ")"
)
import_block = text.split("from platform_api.exceptions import", 1)[-1].split(")", 1)[0]
already = "AccountLockedError," in import_block
if already:
    print("AccountLockedError import already present")
elif old not in text:
    raise SystemExit("Could not find exceptions import block in auth.py")
else:
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("patched AccountLockedError import")
print("grep", [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "AccountLockedError" in line][:8])
PY
chown camxora:camxora /opt/camxora/repo/platform_api/routers/auth.py
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w "%{http_code}" http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
test "$code" = "200"
curl -sS -m 10 -o /tmp/sbx_login.json -w "login_http=%{http_code}\n" \
  -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"probe@test.com","password":"wrongpassword"}'
head -c 400 /tmp/sbx_login.json; echo
echo AUTH_IMPORT_DONE
'''


def patch_auth_import() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(AUTH_IMPORT_REMOTE, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        print(out)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auth-import":
        raise SystemExit(patch_auth_import())
    raise SystemExit(main())
