#!/usr/bin/env python3
"""Deploy website + user portal marketing chrome to sandbox."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect, tar_filter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_PATHS = ("website", "user_portal")


def safe_print(text: str) -> None:
    if not text:
        return
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def build_tarball() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="camxora-web-portal-deploy-"))
    archive = tmp / "camxora-web-portal.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in DEPLOY_PATHS:
            src = REPO_ROOT / name
            if not src.is_dir():
                raise FileNotFoundError(f"Missing deploy directory: {src}")
            tar.add(src, arcname=name, filter=tar_filter, recursive=True)
    return archive


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )

    archive = build_tarball()
    safe_print(f"Uploading {archive.name} ({archive.stat().st_size / (1024 * 1024):.1f} MB)...")
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-web-portal.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.sandbox.camxora.com
SITE_URL=https://sandbox.camxora.com
PORTAL_URL=https://app.sandbox.camxora.com

tar -xzf /tmp/camxora-web-portal.tar.gz -C $REPO website user_portal
# Drop orphaned remote-only sources that break builds (e.g. old quota page).
rm -rf $REPO/user_portal/src/app/dashboard/quota
chown -R camxora:camxora $REPO/website $REPO/user_portal

sudo -u camxora bash -lc "
  set -e
  cd $REPO/website
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_PLATFORM_API_BASE_URL=$API_URL/api/v3
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_SITE_URL=$SITE_URL
NEXT_PUBLIC_USER_PORTAL_URL=$PORTAL_URL
NEXT_PUBLIC_CAMXORA_ENV=sandbox
ENVEOF
  npm run build
"

sudo -u camxora bash -lc "
  set -e
  cd $REPO/user_portal
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_WEBSITE_URL=$SITE_URL
NEXT_PUBLIC_USER_PORTAL_URL=$PORTAL_URL
NEXT_PUBLIC_PLATFORM_API_BASE_URL=$API_URL/api/v3
ENVEOF
  npm run build
"

systemctl restart camxora-website camxora-portal
sleep 3
systemctl is-active camxora-website camxora-portal

echo -n 'website home: '
curl -s -o /dev/null -w '%{http_code}\n' https://sandbox.camxora.com/ || true
echo -n 'website terms: '
curl -s -o /dev/null -w '%{http_code}\n' https://sandbox.camxora.com/terms || true
echo -n 'website privacy: '
curl -s -o /dev/null -w '%{http_code}\n' https://sandbox.camxora.com/privacy || true
echo -n 'website google-api: '
curl -s -o /dev/null -w '%{http_code}\n' https://sandbox.camxora.com/google-api || true
echo -n 'portal login: '
curl -s -o /dev/null -w '%{http_code}\n' https://app.sandbox.camxora.com/login || true

echo WEB_PORTAL_DEPLOY_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=1200)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    safe_print(out)
    if err.strip():
        safe_print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    if code == 0:
        safe_print("\nSandbox deploy complete:")
        safe_print("  Website: https://sandbox.camxora.com/")
        safe_print("  Terms:   https://sandbox.camxora.com/terms")
        safe_print("  Privacy: https://sandbox.camxora.com/privacy")
        safe_print("  Portal:  https://app.sandbox.camxora.com/login")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
