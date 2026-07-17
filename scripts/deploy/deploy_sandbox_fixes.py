#!/usr/bin/env python3
"""Deploy sandbox fixes: nginx /api proxy, portal rebuilds, timezone."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import build_source_tarball, ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def upload_source(client) -> None:
    archive = build_source_tarball()
    remote_path = "/tmp/camxora-src.tar.gz"
    sftp = client.open_sftp()
    with sftp.file(remote_path, "wb") as remote_file:
        remote_file.write(archive.read_bytes())
    sftp.close()
    _, stdout, stderr = client.exec_command(
        "mkdir -p /opt/camxora/repo && "
        "tar -xzf /tmp/camxora-src.tar.gz -C /opt/camxora/repo && "
        "chown -R camxora:camxora /opt/camxora/repo"
    )
    stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if err:
        print(err)


def upload_nginx(client) -> None:
    nginx_conf = Path(__file__).resolve().parent / "nginx-camxora-sandbox.conf"
    sftp = client.open_sftp()
    sftp.put(str(nginx_conf), "/tmp/nginx-camxora-sandbox.conf")
    sftp.close()


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    print("Uploading source...")
    upload_source(client)
    print("Uploading nginx config...")
    upload_nginx(client)

    cmd = r"""
set -e
REPO=/opt/camxora/repo

echo "=== Setting timezone ==="
timedatectl set-timezone Asia/Phnom_Penh
timedatectl | grep -E 'Time zone|Local time'

echo "=== Applying nginx config ==="
cp /tmp/nginx-camxora-sandbox.conf /etc/nginx/sites-available/camxora-sandbox
ln -sf /etc/nginx/sites-available/camxora-sandbox /etc/nginx/sites-enabled/camxora-sandbox
nginx -t
systemctl reload nginx

echo "=== Writing user portal env ==="
cat > $REPO/user_portal/.env.production <<'ENVEOF'
# Same-origin /api/v1 via nginx — leave NEXT_PUBLIC_PLATFORM_API_BASE_URL unset
NEXT_PUBLIC_CAMXORA_ENV=sandbox
NEXT_PUBLIC_WEBSITE_URL=https://sandbox.camxora.com
NEXT_PUBLIC_USER_PORTAL_URL=https://app.sandbox.camxora.com
ENVEOF
chown camxora:camxora $REPO/user_portal/.env.production

echo "=== Updating portal systemd unit ==="
tee /etc/systemd/system/camxora-portal.service >/dev/null <<'UNIT'
[Unit]
Description=CamXora User Portal
After=network.target

[Service]
User=camxora
Group=camxora
WorkingDirectory=/opt/camxora/repo/user_portal
Environment=NODE_ENV=production
Environment=PORT=3101
Environment=PLATFORM_API_INTERNAL_URL=http://127.0.0.1:8100/api/v1
Environment=TZ=Asia/Phnom_Penh
ExecStart=/usr/bin/npm run start -- -p 3101 -H 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload

echo "=== Building user portal ==="
sudo -u camxora bash -lc "cd $REPO/user_portal && npm ci || npm install --no-audit --no-fund && npm run build"

echo "=== Building admin portal ==="
sudo -u camxora bash -lc "cd $REPO/admin_portal && npm ci || npm install --no-audit --no-fund && npm run build"

echo "=== Restarting services ==="
systemctl restart camxora-portal

echo "=== Verification ==="
echo -n "signup-mode API: "
curl -sf https://api.sandbox.camxora.com/api/v1/auth/signup-mode
echo ""
echo -n "app /api proxy: "
curl -sf https://app.sandbox.camxora.com/api/v1/auth/signup-mode
echo ""
echo -n "/invite redirect: "
curl -sI https://app.sandbox.camxora.com/invite | head -5
echo "DONE"
"""
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err:
        sys.stdout.buffer.write(b"STDERR: ")
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
