#!/usr/bin/env python3
"""Sandbox-only: encrypt leftover B2 MP3s, then probe /stream/ok like a Range stitcher.

Never targets production host or production B2.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

REMOTE_PY = r'''
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.chdir("/opt/camxora/repo")
sys.path.insert(0, "/opt/camxora/repo")
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

import jwt
import asyncpg

from platform_api.config import get_settings, is_production
from platform_api.services.audio_package_service import AudioPackageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config

PROD_HOST = "82.197.71.248"
SANDBOX_HOST = "46.250.235.83"


def _classify(data: bytes, content_type: str, status: str) -> str:
    head = data[:16]
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "PLAYABLE_MP3"
    if data.startswith(b"RIFF") and b"WAVE" in data[:16]:
        return "PLAYABLE_WAV"
    if data.startswith(b"CXA1") or data.startswith(b"CXO1"):
        return "ENCRYPTED_CAMXORA"
    if b"encrypted" in data.lower() or b"encrypted_playback_required" in data:
        return "REFUSED_ENCRYPTED_PLAYER"
    if status in {"401", "403"}:
        return "AUTH_BLOCKED"
    if status in {"404", "422"}:
        return "REFUSED_HTTP"
    return f"OTHER ct={content_type!r} head={head!r}"


def _curl(url: str, token: str, range_header: str) -> tuple[str, str, bytes]:
    hdr = "/tmp/cx-stream-hdr"
    body = "/tmp/cx-stream-body"
    cmd = [
        "curl", "-sS", "-o", body, "-D", hdr,
        "--connect-timeout", "15", "--max-time", "60",
        "-H", "CF-IPCountry: KH",
        "-H", "accept-encoding: identity",
        "-H", "user-agent: Camxora-Sandbox-Probe",
        "-H", f"range: bytes={range_header}",
        "-b", f"camxora_access_token={token}",
        url,
    ]
    subprocess.run(cmd, check=False)
    raw_hdr = Path(hdr).read_bytes() if Path(hdr).exists() else b""
    raw_body = Path(body).read_bytes() if Path(body).exists() else b""
    status = "000"
    ctype = ""
    for line in raw_hdr.decode("latin1", errors="replace").splitlines():
        if line.upper().startswith("HTTP/"):
            parts = line.split()
            if len(parts) >= 2:
                status = parts[1]
        if line.lower().startswith("content-type:"):
            ctype = line.split(":", 1)[1].strip()
    return status, ctype, raw_body


def _mint_access(settings, user: asyncpg.Record) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": str(user["id"]),
        "email": user["email"],
        "role": str(user["role"] or "user"),
        "token_version": int(user["token_version"] or 0),
        "exp": now + timedelta(minutes=10),
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def main() -> int:
    settings = get_settings()
    print("env=", settings.environment)
    if is_production(settings):
        print("REFUSE: PLATFORM_ENVIRONMENT is production")
        return 2
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        cfg = await resolve_streaming_storage_config(pool, settings=settings)
        print("b2_bucket=", cfg.bucket)
        print("b2_endpoint=", cfg.endpoint)
        print("cdn=", cfg.cdn_base_url)
        if not cfg.configured:
            print("REFUSE: storage not configured")
            return 2
        cdn = (cfg.cdn_base_url or "").lower()
        bucket = (cfg.bucket or "").lower()
        if "sandbox" not in cdn and "sandbox" not in bucket:
            print("REFUSE: bucket/CDN does not look like sandbox; aborting")
            return 2
        if PROD_HOST in cdn or "media.camxora.com" in cdn and "sandbox" not in cdn:
            print("REFUSE: looks like production CDN")
            return 2

        leftover_tracks = await pool.fetchval(
            """
            SELECT COUNT(*) FROM stream_tracks
            WHERE COALESCE(package_status, 'none') = 'none'
              AND storage_key IS NOT NULL AND storage_key <> ''
            """
        )
        leftover_tasks = await pool.fetchval(
            """
            SELECT COUNT(*) FROM suno_tasks
            WHERE source = 'web_music'
              AND (
                (COALESCE(package_status_ok, 'none') = 'none' AND COALESCE(b2_storage_key_ok, '') <> '')
                OR (COALESCE(package_status_alt, 'none') = 'none' AND COALESCE(b2_storage_key_alt, '') <> '')
              )
            """
        )
        print("leftover_stream_tracks=", leftover_tracks)
        print("leftover_suno_tasks=", leftover_tasks)

        svc = AudioPackageService(pool)
        packaged_total = 0
        for _ in range(3):
            result = await svc.backfill(limit=10)
            n = int(result.get("packaged") or 0)
            packaged_total += n
            print("backfill_batch=", result)
            if n == 0:
                break
        print("packaged_this_run=", packaged_total)

        track = await pool.fetchrow(
            """
            SELECT t.id, t.user_id, t.package_status, t.storage_key, t.encrypted_original_storage_key
            FROM stream_tracks t
            WHERE COALESCE(t.package_status, 'none') = 'ready'
            ORDER BY t.updated_at DESC NULLS LAST
            LIMIT 1
            """
        )
        task = await pool.fetchrow(
            """
            SELECT id, user_id, package_status_ok, b2_storage_key_ok, encrypted_original_key_ok
            FROM suno_tasks
            WHERE source = 'web_music' AND COALESCE(package_status_ok, 'none') = 'ready'
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        leftover_track = await pool.fetchrow(
            """
            SELECT id, user_id, package_status, storage_key
            FROM stream_tracks
            WHERE COALESCE(package_status, 'none') = 'none'
              AND storage_key IS NOT NULL AND storage_key <> ''
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

        async def user_row(user_id):
            return await pool.fetchrow(
                """
                SELECT id, email, role, COALESCE(token_version, 0) AS token_version,
                       COALESCE(email_confirmed, false) AS email_confirmed, status
                FROM users WHERE id = $1
                """,
                user_id,
            )

        ranges = ["0-0", "0-", "262144-", "524288-"]

        def stitch_probe(label: str, url: str, token: str) -> None:
            print(f"=== stitcher {label} ===")
            print("url=", url)
            glued = bytearray()
            for rng in ranges:
                status, ctype, body = _curl(url, token, rng)
                kind = _classify(body, ctype, status)
                print(f"range={rng} status={status} bytes={len(body)} class={kind}")
                if status in {"200", "206"} and body:
                    glued.extend(body)
                if kind in {"REFUSED_ENCRYPTED_PLAYER", "REFUSED_HTTP", "AUTH_BLOCKED", "ENCRYPTED_CAMXORA"}:
                    break
            glued_kind = _classify(bytes(glued), "", "206") if glued else "EMPTY"
            print("concat_bytes=", len(glued), "concat_class=", glued_kind)
            playable = glued_kind in {"PLAYABLE_MP3", "PLAYABLE_WAV"} and len(glued) > 1024
            print("FULL_PLAYABLE_MP3=", playable)

        if track:
            owner = await user_row(track["user_id"])
            print("packaged_catalog_track=", track["id"], "package_status=", track["package_status"])
            if owner and owner["email_confirmed"] and owner["status"] == "active":
                token = _mint_access(settings, owner)
                stitch_probe(
                    "catalog-packaged",
                    f"https://music.sandbox.camxora.com/api/v1/public/streaming/tracks/{track['id']}/stream",
                    token,
                )
            else:
                print("skip catalog probe: owner not confirmed/active")

        if task:
            owner = await user_row(task["user_id"])
            print("packaged_create_task=", task["id"], "package_status_ok=", task["package_status_ok"])
            if owner and owner["email_confirmed"] and owner["status"] == "active":
                token = _mint_access(settings, owner)
                stitch_probe(
                    "create-packaged",
                    f"https://music.sandbox.camxora.com/api/v1/web-music/generations/{task['id']}/stream/ok",
                    token,
                )
            else:
                print("skip create probe: owner not confirmed/active")

        if leftover_track:
            print("NOTE leftover unpackaged catalog still exists id=", leftover_track["id"])
        else:
            print("no leftover unpackaged catalog tracks in this batch")
    finally:
        await pool.close()
        for p in ("/tmp/cx-stream-hdr", "/tmp/cx-stream-body"):
            Path(p).unlink(missing_ok=True)
    print("SANDBOX_ENCRYPT_PROBE_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    print("loading sandbox secrets", flush=True)
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}", flush=True)
    if host != CANONICAL_SANDBOX_HOST:
        print(f"REFUSE: expected sandbox {CANONICAL_SANDBOX_HOST}, got {host}")
        return 2
    if host == CANONICAL_PRODUCTION_HOST:
        print("REFUSE: production host")
        return 2
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("uploading probe script", flush=True)
    _, mkdir_out, mkdir_err = client.exec_command("mkdir -p /opt/camxora/tmp && chmod 775 /opt/camxora/tmp")
    mkdir_out.channel.recv_exit_status()
    remote = "/opt/camxora/tmp/sandbox_encrypt_leftover_and_probe_stream.py"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(REMOTE_PY)
        local_py = tmp.name
    sftp = client.open_sftp()
    sftp.put(local_py, remote)
    sftp.close()
    Path(local_py).unlink(missing_ok=True)
    print("uploaded, running backfill+probe", flush=True)
    cmd = r"""
set -e
chown camxora:camxora /opt/camxora/tmp/sandbox_encrypt_leftover_and_probe_stream.py
sudo -u camxora bash -lc 'cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo PYTHONUNBUFFERED=1 /opt/camxora/repo/platform_api/.venv/bin/python -u /opt/camxora/tmp/sandbox_encrypt_leftover_and_probe_stream.py'
rm -f /opt/camxora/tmp/sandbox_encrypt_leftover_and_probe_stream.py
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    sys.stdout.write(out)
    if err.strip():
        sys.stdout.write(err)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
