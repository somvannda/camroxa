#!/usr/bin/env python3
"""File-scoped sandbox hotfix: import AccountLockedError in auth login."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSIST = ROOT.parent / "MusicGenerator-music-web-generate-assist"
AUTH = ASSIST / "platform_api" / "routers" / "auth.py"
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402


def main() -> int:
    if not AUTH.is_file():
        raise FileNotFoundError(AUTH)
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}", flush=True)

    archive = Path(tempfile.mkdtemp(prefix="sandbox-auth-hotfix-")) / "auth.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(AUTH, arcname="platform_api/routers/auth.py")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/sandbox-auth-hotfix.tar.gz -C "$REPO"
chown camxora:camxora "$REPO/platform_api/routers/auth.py"
grep -n AccountLockedError "$REPO/platform_api/routers/auth.py" | head
echo '=== turnstile hostnames (names only) ==='
python3 - <<'PY'
from pathlib import Path
for line in Path("/opt/camxora/repo/platform_api/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("CLOUDFLARE_TURNSTILE_HOSTNAMES=") or line.startswith("PLATFORM_CLOUDFLARE_TURNSTILE_HOSTNAMES="):
        key, _, val = line.partition("=")
        print(key + "=" + val)
PY
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
test "$code" = "200"
echo '=== login probe ==='
curl -sS -m 10 -o /tmp/sbx_login.json -w 'login_http=%{http_code}\n' \
  -X POST http://127.0.0.1:8100/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"probe@test.com","password":"wrongpassword"}'
cat /tmp/sbx_login.json
echo
echo AUTH_IMPORT_HOTFIX_DONE
"""
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/sandbox-auth-hotfix.tar.gz", "wb") as remote_file:
            remote_file.write(archive.read_bytes())
        sftp.close()
        _, stdout, _ = client.exec_command(remote, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        Path(__file__).with_name("_tmp_hotfix_sandbox_auth.out").write_text(out, encoding="utf-8")
        print(out)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
