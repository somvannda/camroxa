#!/usr/bin/env python3
"""Deploy the musicapi stack (core API + web-user + web-admin) to the sandbox VPS.

Mirrors scripts/deploy/deploy.py (same secrets, same SSH key + bootstrap) but only
ships the `musicapi/` tree plus `scripts/deploy/` (systemd units, nginx confs). The
remote side is scripts/deploy/camxora-musicapi-remote.sh.

Usage:
    python scripts/deploy/sync_musicapi_sandbox.py
    python scripts/deploy/sync_musicapi_sandbox.py --issue-cert   # first deploy, DNS ready
    python scripts/deploy/sync_musicapi_sandbox.py --api-only     # core API only (skip Next builds)

Secrets come from .deploy/secrets.sandbox.env (see .deploy/secrets.env.example).
Optional MUSICAPI_* keys:
    MUSICAPI_DB_PASSWORD, MUSICAPI_JWT_SECRET, MUSICAPI_COOKIE_ENCRYPTION_KEY,
    MUSICAPI_SUNO_CLIENT_COOKIE, MUSICAPI_SUNO_COOKIE, MUSICAPI_SUNO_JWT,
    MUSICAPI_SUNO_DEVICE_ID, MUSICAPI_SUNO_CAPTCHA_TOKEN, MUSICAPI_TWOCAPTCHA_KEY,
    MUSICAPI_GOOGLE_CLIENT_ID, MUSICAPI_GOOGLE_CLIENT_SECRET,
    MUSICAPI_BAKONG_API_TOKEN, MUSICAPI_BAKONG_ACCOUNT_ID,
    MUSICAPI_CHMABA_API_KEY, MUSICAPI_CHMABA_STORE_ID, MUSICAPI_CHMABA_WEBHOOK_SECRET,
    MUSICAPI_FRONTEND_ORIGINS, MUSICAPI_LOG_LEVEL,
    MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN, MUSICAPI_ALERT_TELEGRAM_CHAT_ID
      (health-alert bot; the platform's TELEGRAM_BOT_TOKEN / PLATFORM_TELEGRAM_*
       are reused when these are unset), MUSICAPI_BACKUP_DIR,
    MUSICAPI_BACKUP_RETENTION_DAYS
Anything omitted is generated on the server on first deploy and persisted to
/opt/camxora/.deploy-secrets, so redeploys keep sessions/cookies valid.

Production twin: scripts/deploy/deploy_musicapi_production.py
"""

from __future__ import annotations

import argparse
import stat
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    REPO_ROOT,
    ensure_deploy_key,
    ensure_paramiko,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
    tar_filter,
)
from deploy_guards import acquire_remote_lock, release_remote_lock  # noqa: E402

REMOTE_SCRIPT = Path(__file__).resolve().parent / "camxora-musicapi-remote.sh"
REMOTE_TARBALL = "/tmp/musicapi-src.tar.gz"
REMOTE_PATH = "/tmp/camxora-musicapi-remote.sh"
PACKAGE_DIRS = ("musicapi", "scripts/deploy")

DeployEnv = Literal["sandbox", "production"]


def _force_utf8_stdio() -> None:
    """Make stdout/stderr UTF-8 tolerant.

    Remote build output contains Unicode spinner frames and ANSI escapes; on a
    Windows console the default cp1252 codec raises UnicodeEncodeError mid-run
    and aborts an otherwise healthy deploy. Reconfiguring the streams with
    errors="replace" keeps the deploy going on any console.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def build_musicapi_tarball() -> Path:
    """Package musicapi/ + scripts/deploy/ (arcnames preserved) for upload."""
    tmp = Path(tempfile.mkdtemp(prefix="musicapi-deploy-"))
    archive = tmp / "musicapi-src.tar.gz"
    print("Packaging musicapi source for upload...")
    with tarfile.open(archive, "w:gz") as tar:
        for name in PACKAGE_DIRS:
            src = REPO_ROOT / name
            if not src.is_dir():
                raise FileNotFoundError(f"Missing deploy directory: {src}")
            tar.add(src, arcname=name, filter=tar_filter, recursive=True)
    print(f"Source archive ready ({archive.stat().st_size / (1024 * 1024):.1f} MB)")
    return archive


def _shell_exports(env: dict[str, str]) -> str:
    """Render `export K='v'` pairs, single-quote-escaping each value."""
    parts = []
    for key, val in env.items():
        safe = val.replace("'", "'\\''")
        parts.append(f"export {key}='{safe}'")
    return " && ".join(parts)


def upload_and_run(
    client, env: DeployEnv, secrets: dict[str, str], issue_cert: bool, skip_frontend: bool = False
) -> tuple[int, str]:
    archive = build_musicapi_tarball()
    if not REMOTE_SCRIPT.is_file():
        raise FileNotFoundError(f"Missing {REMOTE_SCRIPT}")

    sftp = client.open_sftp()
    total = archive.stat().st_size
    print(f"Uploading source to {REMOTE_TARBALL}...")

    def progress(sent: int, _total: int) -> None:
        if total:
            print(f"\rUploading source... {min(100, int(sent * 100 / total))}%", end="", flush=True)

    # A dropped connection can truncate an SFTP upload WITHOUT raising, and the
    # remote side extracts the tarball over the live tree after a destructive
    # `rm -rf`. Verify the remote size matches the local archive and retry, so a
    # bad upload can never reach the install step.
    last_error = ""
    for attempt in range(1, 4):
        try:
            sftp.put(str(archive), REMOTE_TARBALL, callback=progress)
            print()
            remote_size = sftp.stat(REMOTE_TARBALL).st_size
            if remote_size == total:
                break
            last_error = f"remote size {remote_size} != local {total}"
        except OSError as e:  # includes paramiko's IOError
            last_error = str(e)
        print(f"\nUpload attempt {attempt} failed ({last_error}); retrying...")
        try:
            sftp.close()
        except Exception:
            pass
        sftp = client.open_sftp()
    else:
        sftp.close()
        raise RuntimeError(
            f"Failed to upload {REMOTE_TARBALL} intact after 3 attempts: {last_error}"
        )

    script_bytes = REMOTE_SCRIPT.read_bytes().replace(b"\r\n", b"\n")
    with sftp.file(REMOTE_PATH, "wb") as remote_file:
        remote_file.write(script_bytes)
    sftp.chmod(REMOTE_PATH, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
    sftp.close()

    export_env = {
        "MUSICAPI_ENV": env,
        "SYNC_FROM_LOCAL": "1",
        "ISSUE_CERT": "1" if issue_cert else "0",
    }
    if skip_frontend:
        export_env["MUSICAPI_SKIP_FRONTEND"] = "1"
    if secrets.get("CERTBOT_EMAIL"):
        export_env["CERTBOT_EMAIL"] = secrets["CERTBOT_EMAIL"]
    # Forward every MUSICAPI_* deploy secret to the remote installer.
    for key, val in secrets.items():
        if key.startswith("MUSICAPI_") and val:
            export_env.setdefault(key, val)

    # Reuse the platform's ops Telegram channel for musicapi health alerts
    # (task 4.6) unless dedicated MUSICAPI_ALERT_* creds were supplied above.
    alert_token = (
        secrets.get("MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN")
        or secrets.get("TELEGRAM_BOT_TOKEN")
        or secrets.get("PLATFORM_TELEGRAM_BOT_TOKEN")
    )
    alert_chat = (
        secrets.get("MUSICAPI_ALERT_TELEGRAM_CHAT_ID")
        or secrets.get("TELEGRAM_CHAT_ID")
        or secrets.get("PLATFORM_TELEGRAM_CHAT_ID")
    )
    if alert_token:
        export_env.setdefault("MUSICAPI_ALERT_TELEGRAM_BOT_TOKEN", alert_token)
    if alert_chat:
        export_env.setdefault("MUSICAPI_ALERT_TELEGRAM_CHAT_ID", alert_chat)

    cmd = f"{_shell_exports(export_env)} && bash {REMOTE_PATH}"
    print(f"Running remote install for '{env}' (this can take several minutes)...")
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport unavailable")
    channel = transport.open_session()
    channel.get_pty()
    channel.exec_command(cmd)

    captured: list[str] = []
    sentinel = f"MUSICAPI_{env.upper()}_DEPLOYED"
    while True:
        if channel.recv_ready():
            chunk = channel.recv(4096).decode(errors="replace")
            captured.append(chunk)
            sys.stdout.write(chunk)
            sys.stdout.flush()
        if channel.recv_stderr_ready():
            sys.stderr.write(channel.recv_stderr(4096).decode(errors="replace"))
            sys.stderr.flush()
        # The installer prints this sentinel as its final line. Return on it even
        # if the SSH channel lingers open (a child holding the PTY), which used to
        # leave this client blocked forever after the remote work had finished.
        if sentinel in "".join(captured):
            while channel.recv_ready():
                captured.append(channel.recv(4096).decode(errors="replace"))
            return 0, "".join(captured)
        if channel.exit_status_ready():
            while channel.recv_ready():
                captured.append(channel.recv(4096).decode(errors="replace"))
            return channel.recv_exit_status(), "".join(captured)
        import time

        time.sleep(0.2)


def deploy(env: DeployEnv, issue_cert: bool = False, skip_frontend: bool = False) -> int:
    _force_utf8_stdio()
    ensure_paramiko()
    if not REMOTE_SCRIPT.is_file():
        print(f"Missing {REMOTE_SCRIPT}")
        return 1

    if env == "sandbox":
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
    else:
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)

    custom_key = secrets.get("VPS_SSH_KEY") or None
    key_path = Path(custom_key) if custom_key else ensure_deploy_key()
    if not key_path.is_file():
        print(f"Missing deploy key: {key_path}")
        return 1

    print(f"Connecting to {user}@{host}...")
    client = ssh_connect(host, user, key_path, password)
    lock = None
    try:
        # Serialize deploys to this host: two agents deploying at once clobber
        # each other's node_modules mid-build (observed 2026-10-07). A TTL keeps
        # a crashed deploy from wedging the lock; CAMXORA_ALLOW_CONCURRENT_DEPLOY=1
        # overrides for a deliberate parallel deploy.
        lock = acquire_remote_lock(client)
        code, output = upload_and_run(client, env, secrets, issue_cert, skip_frontend)
    finally:
        if lock is not None:
            release_remote_lock(client, lock)
        client.close()

    sentinel = f"MUSICAPI_{env.upper()}_DEPLOYED"
    if code == 0 and sentinel in output:
        print(f"\nMusic API {env} deploy finished successfully.")
        return 0
    print(f"\nMusic API {env} deploy FAILED (exit {code}).")
    return code or 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy the musicapi stack to the sandbox VPS")
    parser.add_argument(
        "--issue-cert",
        action="store_true",
        help="Bootstrap the Let's Encrypt cert on first deploy (DNS must resolve)",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Skip the Next.js frontend builds (core API + migrations + services only)",
    )
    args = parser.parse_args()
    return deploy("sandbox", issue_cert=args.issue_cert, skip_frontend=args.api_only)


if __name__ == "__main__":
    raise SystemExit(main())
