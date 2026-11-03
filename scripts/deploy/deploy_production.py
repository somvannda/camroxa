#!/usr/bin/env python3
"""Deploy Camxora production to VPS via SSH. Reads .deploy/secrets.production.env.

Production ships **one commit of main**, never a working tree:

  1. fetch origin (unless ``--no-fetch``)
  2. resolve the deploy source (default ``origin/main``)
  3. refuse unless that commit is merged to ``origin/main``
  4. package it with ``git archive`` + a sha256 manifest
  5. verify the manifest on the server before any build or restart

Escape hatches (deliberate hotfix only, recorded as unmerged/dirty):

    CAMXORA_DEPLOY_SOURCE=worktree   package the working tree
    CAMXORA_DEPLOY_SOURCE_REF=HEAD   package HEAD instead of origin/main
    CAMXORA_ALLOW_UNMERGED_DEPLOY=1  allow a commit that is not on main
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    build_source_bundle,
    ensure_deploy_key,
    ensure_paramiko,
    fetch_origin,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
    upload_source,
)
from deploy_guards import (  # noqa: E402
    acquire_remote_lock,
    enforce_deploy_gate,
    post_deploy_record,
    release_remote_lock,
)
from release_source import DEFAULT_SOURCE_REF, SOURCE_MODE_ENV, SourceBundle  # noqa: E402

REMOTE_SCRIPT = Path(__file__).resolve().parent / "camxora-production-remote.sh"
NGINX_CONF = Path(__file__).resolve().parent / "nginx-camxora-production.conf"


def ensure_https_config(client) -> tuple[bool, str]:
    """Guarantee production ends with the canonical TLS vhosts applied.

    The remote install script bootstraps an HTTP-only site and then applies the
    uploaded HTTPS config *conditionally*; when that condition is false it exits
    0 and leaves production serving the wrong certificate for ``api.``/``admin.``.
    Re-apply the committed template here, verify the resulting file really has
    TLS for every required host, and fail the deploy otherwise.
    """
    from nginx_guard import missing_tls_error

    if not NGINX_CONF.is_file():
        return False, f"missing nginx template: {NGINX_CONF}"

    template = NGINX_CONF.read_text(encoding="utf-8")
    local_error = missing_tls_error(template)
    if local_error:
        return False, f"committed template is not safe: {local_error}"

    sftp = client.open_sftp()
    try:
        sftp.put(str(NGINX_CONF), "/tmp/nginx-camxora-production.conf")
    finally:
        sftp.close()

    site = "/etc/nginx/sites-available/camxora-production"
    command = (
        "set -e; "
        "cp /tmp/nginx-camxora-production.conf {site}; "
        "ln -sf {site} /etc/nginx/sites-enabled/camxora-production; "
        "nginx -t; "
        "systemctl reload nginx; "
        "cat {site}"
    ).format(site=site)
    _, stdout, stderr = client.exec_command(command)
    applied = stdout.read().decode("utf-8", errors="replace")
    errors = stderr.read().decode("utf-8", errors="replace").strip()
    status = stdout.channel.recv_exit_status()
    if status != 0:
        return False, f"applying nginx config failed: {errors or applied[-400:]}"

    remote_error = missing_tls_error(applied)
    if remote_error:
        return False, remote_error
    return True, "TLS vhosts applied and verified"


def upload_and_run(client, secrets: dict[str, str], bundle: SourceBundle) -> int:
    upload_source(client, bundle)
    remote_path = "/tmp/camxora-production-remote.sh"
    sftp = client.open_sftp()
    with sftp.file(remote_path, "wb") as remote_file:
        remote_file.write(REMOTE_SCRIPT.read_bytes().replace(b"\r\n", b"\n"))
    sftp.chmod(remote_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
    if NGINX_CONF.is_file():
        sftp.put(str(NGINX_CONF), "/tmp/nginx-camxora-production.conf")
    sftp.close()
    keys = ("SYNC_FROM_LOCAL", "GIT_REPO", "GIT_BRANCH", "GITHUB_TOKEN", "ADMIN_EMAIL", "CERTBOT_EMAIL", "DB_PASSWORD", "PLATFORM_JWT_SECRET", "PLATFORM_ENCRYPTION_MASTER_KEY", "PLATFORM_SUNO_CALLBACK_HMAC_SECRET", "EDGE_VERIFY_SECRET", "PLATFORM_CUTLUY_SECRET_KEY", "PLATFORM_CUTLUY_PAYMENT_LINK_ID", "PLATFORM_CUTLUY_WEBHOOK_SECRET", "PLATFORM_CHMABA_API_KEY", "PLATFORM_CHMABA_STORE_ID", "PLATFORM_CHMABA_WEBHOOK_SECRET", "PLATFORM_TELEGRAM_BOT_TOKEN", "PLATFORM_TELEGRAM_CHAT_ID", "PLATFORM_TELEGRAM_OPS_ENABLED", "PLATFORM_TELEGRAM_POLLER_ENABLED", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "PLATFORM_MUSICAPI_DATABASE_URL", "CLOUDFLARE_TURNSTILE_SITE_KEY", "CLOUDFLARE_TURNSTILE_SECRET_KEY", "CLOUDFLARE_TURNSTILE_HOSTNAMES", "API_WORKERS", "PLATFORM_SMTP_HOST", "PLATFORM_SMTP_PORT", "PLATFORM_SMTP_USER", "PLATFORM_SMTP_PASSWORD", "PLATFORM_SMTP_USE_TLS", "PLATFORM_EMAIL_FROM_NAME", "PLATFORM_EMAIL_FROM_ADDRESS", "PLATFORM_GOOGLE_CLIENT_ID", "PLATFORM_GOOGLE_CLIENT_SECRET", "PLATFORM_GOOGLE_REDIRECT_URIS", "MUSICAPI_GOOGLE_CLIENT_ID", "MUSICAPI_GOOGLE_CLIENT_SECRET", "PLATFORM_MUSIC_WEB_EMAIL_SIGNUP_ENABLED", "PLATFORM_MUSIC_WEB_GEO_ENFORCE")
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
    while channel.recv_ready(): sys.stdout.buffer.write(channel.recv(4096))
    while channel.recv_stderr_ready(): sys.stderr.buffer.write(channel.recv_stderr(4096))
    return channel.recv_exit_status()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-ref",
        default=os.environ.get("CAMXORA_DEPLOY_SOURCE_REF", "").strip() or DEFAULT_SOURCE_REF,
        help=f"commit-ish to ship (default {DEFAULT_SOURCE_REF})",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="do not `git fetch origin` before resolving the source",
    )
    args = parser.parse_args()

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

    if not args.no_fetch:
        ok, detail = fetch_origin()
        if not ok:
            print(f"WARNING: git fetch origin failed ({detail}); using the local {args.source_ref}")
        else:
            print(f"[deploy-guard] origin/main refreshed: {detail}")

    # Package first: the bundle is the source of truth for what ships, and the
    # gate should judge that commit, not whatever HEAD happens to be.
    try:
        bundle = build_source_bundle(args.source_ref)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - surface a clean refusal
        print(f"Refusing deploy — could not build the source bundle: {exc}")
        return 1

    mode = os.environ.get(SOURCE_MODE_ENV, "commit").strip().lower()
    gate = enforce_deploy_gate(
        commit=bundle.commit,
        require_merged=True,
        # A commit archive cannot be stale; only the worktree escape hatch can.
        require_clean=(mode == "worktree"),
    )

    client = ssh_connect(host, user, Path(custom_key) if custom_key else ensure_deploy_key(), password)
    lock = acquire_remote_lock(client)
    live_status = "not-checked"
    live_detail = ""
    try:
        # Surface the case that used to be invisible: production was hotfixed in
        # place after the last deploy, and this deploy is about to replace it.
        from check_deploy_guards import live_source_status

        live_status, live_detail = live_source_status(client, "/opt/camxora/repo")
        if live_status == "drift":
            print(
                "\nWARNING: the live checkout has drifted from its deployed manifest — "
                "production was edited in place (a server-side hotfix). This deploy "
                "replaces it with the source commit; if that change is not on main, "
                "merge it first or it will be lost.\n"
                + live_detail
            )
        elif live_status == "no-manifest":
            print(
                "\nWARNING: production has no .deploy-manifest.json (deployed before "
                "verified-source deploys); this deploy starts tracking it."
            )

        code = upload_and_run(client, secrets, bundle)
        # Always re-assert TLS, even when the remote script failed: its early
        # fatal paths exit *after* overwriting the site with the HTTP-only
        # bootstrap, which is exactly the state that must never persist.
        https_ok, https_detail = ensure_https_config(client)
        print(f"[deploy-guard] nginx TLS: {https_detail}")
        if code == 0 and not https_ok:
            print(
                "DEPLOY_VERIFY_FAILED — production was left without TLS; "
                "fix the nginx template/config before retrying."
            )
            code = 1
        if code == 0:
            post_deploy_record(
                client,
                gate,
                target="production",
                script=Path(__file__).name,
                extra={
                    "source_commit": bundle.commit,
                    "source_ref": bundle.ref,
                    "source_mode": bundle.mode,
                    "source_files": bundle.files,
                    "manifest": ".deploy-manifest.json",
                    "previous_live_status": live_status,
                },
            )
    finally:
        release_remote_lock(client, lock)
        client.close()
    if code == 0:
        print("\nProduction deploy finished successfully.")
        print(f"  Live commit: {bundle.short} ({bundle.ref}, {bundle.files} files)")
        print("  API:    https://api.camxora.com/health\n  Site:   https://camxora.com\n  Portal: https://app.camxora.com\n  Admin:  https://admin.camxora.com\n  Music:  https://music.camxora.com")
    else: print(f"\nProduction deploy failed with exit code {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
