#!/usr/bin/env python3
"""Ensure music.camxora.com is allowed for Turnstile on production API."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

HOSTNAME = "music.camxora.com"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != "82.197.71.248":
        raise SystemExit(f"Refusing non-production host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote = f"""
set -e
ENV=/opt/camxora/repo/platform_api/.env
if grep -q '^CLOUDFLARE_TURNSTILE_HOSTNAMES=' "$ENV"; then
  if grep '^CLOUDFLARE_TURNSTILE_HOSTNAMES=' "$ENV" | grep -q '{HOSTNAME}'; then
    echo "HOSTNAME_ALREADY_PRESENT"
  else
    sed -i "s|^CLOUDFLARE_TURNSTILE_HOSTNAMES=|&{HOSTNAME},|" "$ENV"
    echo "HOSTNAME_APPENDED"
  fi
else
  echo "CLOUDFLARE_TURNSTILE_HOSTNAMES={HOSTNAME},app.camxora.com,camxora.com,www.camxora.com" >> "$ENV"
  echo "HOSTNAME_ADDED"
fi
grep '^CLOUDFLARE_TURNSTILE_HOSTNAMES=' "$ENV" || true
grep '^CLOUDFLARE_TURNSTILE_SITE_KEY=' "$ENV" | cut -c1-40 || true
grep '^CLOUDFLARE_TURNSTILE_SECRET_KEY=' "$ENV" | cut -c1-20 || true
systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
echo DONE
"""
    _, stdout, stderr = client.exec_command(remote, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
