#!/usr/bin/env python3
"""Apply the musicapi nginx config from repo to VPS (sandbox or production).

Production has two vhosts:
    musicapi.camxora.com        -> user portal + landing page 127.0.0.1:4001
                                   (API mounted by path -> 4003)
    admin.musicapi.camxora.com  -> web-admin                  127.0.0.1:4002

Sandbox has three vhosts (it keeps the legacy split):
    musicapi.sandbox.camxora.com        -> core API   127.0.0.1:4003
    app.musicapi.sandbox.camxora.com    -> web-user   127.0.0.1:4001
    admin.musicapi.sandbox.camxora.com  -> web-admin  127.0.0.1:4002

Usage:
    python scripts/deploy/apply_musicapi_nginx.py --env sandbox
    python scripts/deploy/apply_musicapi_nginx.py --env production

First-time bootstrap (certs do not exist yet, so the ssl vhosts cannot load):
    python scripts/deploy/apply_musicapi_nginx.py --env sandbox --issue-cert
`--issue-cert` stands up a temporary port-80 server block for the environment's
names, runs certbot to obtain the shared Let's Encrypt cert, then applies the config.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

DEPLOY_DIR = Path(__file__).resolve().parent

ENV_CONFIG = {
    "sandbox": {
        "conf_file": "nginx-musicapi-sandbox.conf",
        "remote_tmp": "/tmp/nginx-musicapi-sandbox.conf",
        "remote_site": "/etc/nginx/sites-available/musicapi-sandbox",
        "site_link": "/etc/nginx/sites-enabled/musicapi-sandbox",
        "names": [
            "musicapi.sandbox.camxora.com",
            "app.musicapi.sandbox.camxora.com",
            "admin.musicapi.sandbox.camxora.com",
        ],
    },
    "production": {
        "conf_file": "nginx-musicapi-production.conf",
        "remote_tmp": "/tmp/nginx-musicapi-production.conf",
        "remote_site": "/etc/nginx/sites-available/musicapi-production",
        "site_link": "/etc/nginx/sites-enabled/musicapi-production",
        "names": [
            "musicapi.camxora.com",
            "admin.musicapi.camxora.com",
        ],
    },
}


def upload_conf(client, env: str) -> None:
    cfg = ENV_CONFIG[env]
    local = DEPLOY_DIR / cfg["conf_file"]
    if not local.is_file():
        raise FileNotFoundError(f"Missing nginx config: {local}")
    sftp = client.open_sftp()
    sftp.put(str(local), cfg["remote_tmp"])
    sftp.close()


def issue_cert(client, env: str) -> tuple[str, str]:
    """Bootstrap TLS: serve the three names on :80, then run certbot."""
    cfg = ENV_CONFIG[env]
    names = " ".join(cfg["names"])
    d_flags = " ".join(f"-d {n}" for n in cfg["names"])
    bootstrap_tmp = f"/tmp/musicapi-{env}-bootstrap.conf"
    bootstrap_site = f"/etc/nginx/sites-available/musicapi-{env}-bootstrap"
    bootstrap_link = f"/etc/nginx/sites-enabled/musicapi-{env}-bootstrap"
    conf = (
        "server {\n"
        "    listen 80;\n"
        f"    server_name {names};\n"
        "    location / { return 404; }\n"
        "}\n"
    )
    sftp = client.open_sftp()
    with sftp.open(bootstrap_tmp, "w") as fh:
        fh.write(conf)
    sftp.close()

    cmd = f"""
set -e
cp {bootstrap_tmp} {bootstrap_site}
ln -sf {bootstrap_site} {bootstrap_link}
nginx -t
systemctl reload nginx
certbot --nginx {d_flags} --expand --non-interactive --redirect
rm -f {bootstrap_link} {bootstrap_site}
nginx -t
systemctl reload nginx
echo MUSICAPI_CERT_ISSUED_{env.upper()}
"""
    _, stdout, stderr = client.exec_command(cmd)
    return (
        stdout.read().decode("utf-8", errors="replace"),
        stderr.read().decode("utf-8", errors="replace"),
    )


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
    parser = argparse.ArgumentParser(description="Apply musicapi nginx config to VPS")
    parser.add_argument(
        "--env",
        choices=("sandbox", "production"),
        default="sandbox",
        help="Target environment (default: sandbox)",
    )
    parser.add_argument(
        "--issue-cert",
        action="store_true",
        help="Bootstrap TLS: run certbot for the three hostnames before applying",
    )
    args = parser.parse_args()

    secrets = load_secrets()
    host = secrets.get("PRODUCTION_VPS_HOST") if args.env == "production" else secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    if not host:
        print(f"No VPS host configured for {args.env}. Set VPS_HOST or PRODUCTION_VPS_HOST in .deploy/secrets.env")
        return 1

    client = ssh_connect(host, user, ensure_deploy_key(), secrets.get("VPS_PASSWORD") or None)
    if args.issue_cert:
        print(f"Issuing TLS cert for {' '.join(ENV_CONFIG[args.env]['names'])} on {user}@{host}...")
        out, err = issue_cert(client, args.env)
        print(out)
        if err.strip():
            print(err, file=sys.stderr)
        if f"MUSICAPI_CERT_ISSUED_{args.env.upper()}" not in out:
            client.close()
            return 1

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
