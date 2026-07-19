#!/usr/bin/env python3
"""Deploy AI Structure, streaming, and sample-pack features to sandbox."""

from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect, tar_filter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_PATHS = ("platform_api", "admin_portal", "music_web", "docs")


def safe_print(text: str) -> None:
    """Print deploy output without failing on Windows cp1252 consoles."""
    if not text:
        return
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace") + b"\n")


def build_feature_tarball() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="camxora-feature-deploy-"))
    archive = tmp / "camxora-feature.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in DEPLOY_PATHS:
            src = REPO_ROOT / name
            if not src.is_dir():
                raise FileNotFoundError(f"Missing deploy directory: {src}")
            tar.add(src, arcname=name, filter=tar_filter, recursive=True)
    return archive


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    archive = build_feature_tarball()
    sftp = client.open_sftp()
    with sftp.file("/tmp/camxora-feature.tar.gz", "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()

    cmd = r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.sandbox.camxora.com

tar -xzf /tmp/camxora-feature.tar.gz -C $REPO platform_api admin_portal music_web docs
chown -R camxora:camxora $REPO/platform_api $REPO/admin_portal $REPO/music_web $REPO/docs

mkdir -p /opt/camxora/data/sample-pack-storage
chown -R camxora:camxora /opt/camxora/data/sample-pack-storage
grep -q '^PLATFORM_SAMPLE_PACK_STORAGE_PATH=' $REPO/platform_api/.env || \
  echo 'PLATFORM_SAMPLE_PACK_STORAGE_PATH=/opt/camxora/data/sample-pack-storage' >> $REPO/platform_api/.env

sudo -u camxora bash -lc "
  set -e
  cd $REPO/platform_api
  source .venv/bin/activate
  alembic upgrade head
"

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
# Deploy restarts can cause failed login attempts; clear sandbox lockouts.
redis-cli -n 1 KEYS 'auth:lockout:*' | xargs -r redis-cli -n 1 DEL >/dev/null 2>&1 || true
redis-cli -n 1 KEYS 'auth:failures:*' | xargs -r redis-cli -n 1 DEL >/dev/null 2>&1 || true

sudo -u camxora bash -lc "
  set -e
  cd $REPO/admin_portal
  npm ci || npm install --no-audit --no-fund
  npm run build
"

sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
ENVEOF
  npm run build
"

systemctl restart camxora-music
sleep 2
systemctl is-active camxora-music || true

echo FEATURE_DEPLOY_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    safe_print(out)
    if err.strip():
        safe_print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
