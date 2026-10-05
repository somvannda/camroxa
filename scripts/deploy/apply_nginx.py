#!/usr/bin/env python3
"""Apply nginx config from repo to VPS (sandbox or production)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)

DEPLOY_DIR = Path(__file__).resolve().parent

ENV_CONFIG = {
    "sandbox": {
        "conf_file": "nginx-camxora-sandbox.conf",
        "remote_tmp": "/tmp/nginx-camxora-sandbox.conf",
        "remote_site": "/etc/nginx/sites-available/camxora-sandbox",
        "site_link": "/etc/nginx/sites-enabled/camxora-sandbox",
    },
    "production": {
        "conf_file": "nginx-camxora-production.conf",
        "remote_tmp": "/tmp/nginx-camxora-production.conf",
        "remote_site": "/etc/nginx/sites-available/camxora-production",
        "site_link": "/etc/nginx/sites-enabled/camxora-production",
    },
}


def edge_verify_secret(env: str) -> str:
    """Shared secret the API expects in `X-Origin-Verify` (empty = gate off)."""
    secrets = load_production_secrets() if env == "production" else load_sandbox_secrets()
    return str(secrets.get("EDGE_VERIFY_SECRET", "") or "").strip()


def upload_conf(client, env: str) -> None:
    cfg = ENV_CONFIG[env]
    local = DEPLOY_DIR / cfg["conf_file"]
    if not local.is_file():
        raise FileNotFoundError(f"Missing nginx config: {local}")
    # Substitute the edge secret at deploy time so it is never committed. Empty
    # when unset, which leaves the API geo gate in its legacy (disabled) mode.
    rendered = local.read_text(encoding="utf-8").replace(
        "__EDGE_VERIFY__", edge_verify_secret(env)
    )
    sftp = client.open_sftp()
    with sftp.file(cfg["remote_tmp"], "w") as fh:
        fh.write(rendered)
    sftp.close()


def apply_remote(client, env: str) -> tuple[str, str]:
    cfg = ENV_CONFIG[env]
    cmd = f"""
set -e
cp {cfg["remote_tmp"]} {cfg["remote_site"]}
ln -sf {cfg["remote_site"]} {cfg["site_link"]}
nginx -t
systemctl reload nginx
grep -n proxy_read_timeout {cfg["remote_site"]} || true
echo NGINX_APPLIED_{env.upper()}
"""
    _, stdout, stderr = client.exec_command(cmd)
    return (
        stdout.read().decode("utf-8", errors="replace"),
        stderr.read().decode("utf-8", errors="replace"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply CamXora nginx config to VPS")
    parser.add_argument(
        "--env",
        choices=("sandbox", "production"),
        default="sandbox",
        help="Target environment (default: sandbox)",
    )
    args = parser.parse_args()

    # Resolve through the canonical guards so a production run cannot be pointed
    # at the sandbox host (or vice versa) by a misconfigured secrets file.
    if args.env == "production":
        host, user, password = resolve_production_ssh()
    else:
        host, user, password = resolve_sandbox_ssh()

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print(f"Uploading {ENV_CONFIG[args.env]['conf_file']} to {user}@{host}...")
    upload_conf(client, args.env)
    out, err = apply_remote(client, args.env)
    client.close()
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    return 0 if f"NGINX_APPLIED_{args.env.upper()}" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
