#!/usr/bin/env python3
"""Restore sandbox platform_api/.env from /opt/camxora/.deploy-secrets and restart API."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
set -e
source /opt/camxora/.deploy-secrets
CORS='["https://sandbox.camxora.com","https://app.sandbox.camxora.com","https://admin.sandbox.camxora.com","https://music.sandbox.camxora.com"]'
cat > /opt/camxora/repo/platform_api/.env <<EOF
PLATFORM_ENVIRONMENT=staging
PLATFORM_DEBUG=false
PLATFORM_HOST=127.0.0.1
PLATFORM_PORT=8100
PLATFORM_DATABASE_URL=postgresql+asyncpg://camxora:${DB_PASSWORD}@127.0.0.1:5432/camxora_platform
PLATFORM_REDIS_URL=redis://127.0.0.1:6379/1
PLATFORM_JWT_SECRET=${PLATFORM_JWT_SECRET}
PLATFORM_CORS_ORIGINS=${CORS}
PLATFORM_SUNO_CALLBACK_BASE_URL=https://api.sandbox.camxora.com
PLATFORM_SUNO_CALLBACK_HMAC_SECRET=${PLATFORM_SUNO_CALLBACK_HMAC_SECRET}
PLATFORM_CUTLUY_API_BASE_URL=https://cutluy.com
PLATFORM_CUTLUY_SECRET_KEY=${PLATFORM_CUTLUY_SECRET_KEY:-}
PLATFORM_CUTLUY_PAYMENT_LINK_ID=${PLATFORM_CUTLUY_PAYMENT_LINK_ID:-}
PLATFORM_CUTLUY_WEBHOOK_SECRET=${PLATFORM_CUTLUY_WEBHOOK_SECRET:-}
PLATFORM_ENCRYPTION_MASTER_KEY=${PLATFORM_ENCRYPTION_MASTER_KEY}
PLATFORM_SLAI_API_BASE_URL=https://api.slai.shop
EOF
chown camxora:camxora /opt/camxora/repo/platform_api/.env
chmod 600 /opt/camxora/repo/platform_api/.env
systemctl restart camxora-api
sleep 3
curl -sf https://api.sandbox.camxora.com/api/v1/auth/signup-mode
echo ""
echo ENV_RESTORED
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
