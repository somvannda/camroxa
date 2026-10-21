#!/usr/bin/env python3
"""File-scoped production hotfix: workspace picker in Simple mode.

Uploads allowlisted files only. A full music_web sync is not safe here: the
production tree already runs the ChmabaPay provider switch, and the branch that
carries this UI change may be based on an older main tip. This script therefore
uploads only the Create page component, does not run npm ci, and does not
rewrite .env.production.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
_DEPLOY_CANDIDATES = [SCRIPT_DIR, Path(r"G:\Developments\Projects\Camxora\scripts\deploy")]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "music_web/src/components/create-page-client.tsx",
]

# npm spinner glyphs (braille) break a cp1252 Windows console after the remote
# build already succeeded.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _run(client, cmd: str, timeout: int = 900) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}", flush=True)

    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/music_web/src/components/create-page-client.tsx

echo '=== rebuild music_web ==='
sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  npm run build
"

echo '=== chunk contains simple-mode workspace picker ==='
if grep -l 'Save to\.\.\.' $REPO/music_web/.next/static/chunks/*.js >/dev/null 2>&1; then
  grep -l 'Save to\.\.\.' $REPO/music_web/.next/static/chunks/*.js | head -3
else
  echo 'ERROR: Save to... missing from build' >&2
  exit 1
fi
if grep -l 'Songs to generate' $REPO/music_web/.next/static/chunks/*.js >/dev/null 2>&1; then
  echo 'Songs to generate present'
else
  echo 'ERROR: Songs to generate missing from build' >&2
  exit 1
fi

systemctl restart camxora-music
sleep 5
systemctl is-active camxora-music
curl -sf -o /dev/null -w 'create_http=%{http_code}\n' http://127.0.0.1:3102/create
echo MUSIC_WEB_SIMPLE_WORKSPACE_PICKER_PRODUCTION_DONE
""",
        )
        print(out)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
