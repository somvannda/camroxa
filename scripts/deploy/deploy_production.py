#!/usr/bin/env python3
"""Deploy Camxora production to VPS via SSH. Reads .deploy/secrets.env (never commit it)."""
from __future__ import annotations
import stat
import sys
import time
from pathlib import Path
from deploy import ensure_deploy_key, ensure_paramiko, load_production_secrets, ssh_connect, upload_source
from deploy_guards import (
    acquire_remote_lock,
    enforce_deploy_gate,
    post_deploy_record,
    release_remote_lock,
)

REMOTE_SCRIPT = Path(__file__).resolve().parent / "camxora-production-remote.sh"
NGINX_CONF = Path(__file__).resolve().parent / "nginx-camxora-production.conf"

def upload_and_run(client, secrets: dict[str, str]) -> int:
    upload_source(client)
    remote_path = "/tmp/camxora-production-remote.sh"
    sftp = client.open_sftp()
    with sftp.file(remote_path, "wb") as remote_file:
        remote_file.write(REMOTE_SCRIPT.read_bytes().replace(b"\r\n", b"\n"))
    sftp.chmod(remote_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
    if NGINX_CONF.is_file():
        sftp.put(str(NGINX_CONF), "/tmp/nginx-camxora-production.conf")
    sftp.close()
    keys = ("SYNC_FROM_LOCAL", "GIT_REPO", "GIT_BRANCH", "GITHUB_TOKEN", "ADMIN_EMAIL", "CERTBOT_EMAIL", "DB_PASSWORD", "PLATFORM_JWT_SECRET", "PLATFORM_ENCRYPTION_MASTER_KEY", "PLATFORM_SUNO_CALLBACK_HMAC_SECRET", "EDGE_VERIFY_SECRET", "PLATFORM_CUTLUY_SECRET_KEY", "PLATFORM_CUTLUY_PAYMENT_LINK_ID", "PLATFORM_CUTLUY_WEBHOOK_SECRET", "PLATFORM_TELEGRAM_BOT_TOKEN", "PLATFORM_TELEGRAM_CHAT_ID", "PLATFORM_TELEGRAM_OPS_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "CLOUDFLARE_TURNSTILE_SITE_KEY", "CLOUDFLARE_TURNSTILE_SECRET_KEY", "CLOUDFLARE_TURNSTILE_HOSTNAMES", "API_WORKERS", "PLATFORM_SMTP_HOST", "PLATFORM_SMTP_PORT", "PLATFORM_SMTP_USER", "PLATFORM_SMTP_PASSWORD", "PLATFORM_SMTP_USE_TLS", "PLATFORM_EMAIL_FROM_NAME", "PLATFORM_EMAIL_FROM_ADDRESS", "PLATFORM_GOOGLE_CLIENT_ID", "PLATFORM_GOOGLE_CLIENT_SECRET", "PLATFORM_GOOGLE_REDIRECT_URIS", "MUSICAPI_GOOGLE_CLIENT_ID", "MUSICAPI_GOOGLE_CLIENT_SECRET", "PLATFORM_MUSIC_WEB_EMAIL_SIGNUP_ENABLED", "PLATFORM_MUSIC_WEB_GEO_ENFORCE")
    exports = ["export SYNC_FROM_LOCAL='1'"]
    for key in keys:
        value = secrets.get(key, "")
        if value:
            exports.append("export {}='{}'".format(key, value.replace("'", "'\\''")))
    print("Running production install (this may take 15-30 minutes)...")
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport unavailable")
    channel = transport.open_session()
    channel.get_pty()
    channel.exec_command(f"{' && '.join(exports)} && bash {remote_path}")
    while not channel.exit_status_ready():
        if channel.recv_ready():
            sys.stdout.buffer.write(channel.recv(4096)); sys.stdout.flush()
        if channel.recv_stderr_ready():
            sys.stderr.buffer.write(channel.recv_stderr(4096)); sys.stderr.flush()
        time.sleep(0.2)
    while channel.recv_ready(): sys.stdout.buffer.write(channel.recv(4096))
    while channel.recv_stderr_ready(): sys.stderr.buffer.write(channel.recv_stderr(4096))
    return channel.recv_exit_status()

def main() -> int:
    ensure_paramiko()
    secrets = load_production_secrets()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets.get("VPS_HOST", "")
    user = secrets.get("PRODUCTION_VPS_USER") or secrets.get("VPS_USER", "root")
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD") or None
    custom_key = secrets.get("PRODUCTION_VPS_SSH_KEY") or secrets.get("VPS_SSH_KEY") or None
    if not host:
        print("PRODUCTION_VPS_HOST or VPS_HOST is required in secrets.env"); return 1
    if not REMOTE_SCRIPT.is_file():
        print(f"Missing {REMOTE_SCRIPT}"); return 1
    gate = enforce_deploy_gate()
    client = ssh_connect(host, user, Path(custom_key) if custom_key else ensure_deploy_key(), password)
    lock = acquire_remote_lock(client)
    try:
        code = upload_and_run(client, secrets)
        if code == 0:
            post_deploy_record(client, gate, target="production", script=Path(__file__).name)
    finally:
        release_remote_lock(client, lock)
        client.close()
    if code == 0:
        print("\nProduction deploy finished successfully.")
        print("  API:    https://api.camxora.com/health\n  Site:   https://camxora.com\n  Portal: https://app.camxora.com\n  Admin:  https://admin.camxora.com\n  Music:  https://music.camxora.com")
    else: print(f"\nProduction deploy failed with exit code {code}")
    return code
if __name__ == "__main__": raise SystemExit(main())