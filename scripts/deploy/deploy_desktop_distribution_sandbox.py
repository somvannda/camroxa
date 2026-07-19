#!/usr/bin/env python3
"""Deploy desktop distribution + installer upload features to sandbox."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect, tar_filter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_PATHS = ("platform_api", "admin_portal", "website", "docs")


def safe_print(text: str) -> None:
    if not text:
        return
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def build_tarball() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="camxora-distribution-deploy-"))
    archive = tmp / "camxora-distribution.tar.gz"
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
    with sftp.file("/tmp/camxora-distribution.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.sandbox.camxora.com
SITE_URL=https://sandbox.camxora.com

tar -xzf /tmp/camxora-distribution.tar.gz -C $REPO platform_api admin_portal website docs
chown -R camxora:camxora $REPO/platform_api $REPO/admin_portal $REPO/website $REPO/docs

mkdir -p /opt/camxora/data/desktop-releases
chown -R camxora:camxora /opt/camxora/data/desktop-releases

touch $REPO/platform_api/.env
grep -q '^PLATFORM_DESKTOP_RELEASE_STORAGE_PATH=' $REPO/platform_api/.env || \
  echo 'PLATFORM_DESKTOP_RELEASE_STORAGE_PATH=/opt/camxora/data/desktop-releases' >> $REPO/platform_api/.env
grep -q '^PLATFORM_DESKTOP_RELEASE_MAX_UPLOAD_MB=' $REPO/platform_api/.env || \
  echo 'PLATFORM_DESKTOP_RELEASE_MAX_UPLOAD_MB=500' >> $REPO/platform_api/.env
# Serve uploaded installers via public API file route on sandbox (no separate CDN host).
if grep -q '^PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL=' $REPO/platform_api/.env; then
  sed -i 's|^PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL=.*|PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL=|' $REPO/platform_api/.env
else
  echo 'PLATFORM_DESKTOP_RELEASE_PUBLIC_BASE_URL=' >> $REPO/platform_api/.env
fi

systemctl restart camxora-api
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8100/health >/dev/null; then
    echo "camxora-api health OK after ${i} attempt(s)"
    break
  fi
  sleep 2
done
systemctl is-active camxora-api
curl -sf http://127.0.0.1:8100/health || { echo "API health check failed"; exit 1; }

PUBLIC_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/api/v1/public/desktop-release || true)
echo "public desktop-release HTTP ${PUBLIC_CODE}"

sudo -u camxora bash -lc "
  set -e
  cd $REPO/admin_portal
  npm ci || npm install --no-audit --no-fund
  npm run build
"

sudo -u camxora bash -lc "
  set -e
  cd $REPO/website
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_SITE_URL=$SITE_URL
NEXT_PUBLIC_CAMXORA_ENV=sandbox
ENVEOF
  npm run build
"

systemctl restart camxora-website
sleep 2
systemctl is-active camxora-website || true

redis-cli -n 1 KEYS 'auth:lockout:*' | xargs -r redis-cli -n 1 DEL >/dev/null 2>&1 || true
redis-cli -n 1 KEYS 'auth:failures:*' | xargs -r redis-cli -n 1 DEL >/dev/null 2>&1 || true

echo DISTRIBUTION_DEPLOY_DONE
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
        safe_print("  Admin Software Updates upload: https://admin.sandbox.camxora.com/software-updates")
        safe_print("  Public download page:          https://sandbox.camxora.com/download")
        safe_print("  Public changelog page:         https://sandbox.camxora.com/changelog")
        safe_print("  Public API:                    https://api.sandbox.camxora.com/api/v1/public/desktop-release")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
