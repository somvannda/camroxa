#!/usr/bin/env python3
"""Production-only leftover B2 audio encrypt + Range probe. Host 82.197.71.248."""

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
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

REMOTE_PY = r'''
import asyncio
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

MAX_BATCHES = 8
BATCH_SIZE = 10


def classify(data: bytes, content_type: str, status: str) -> str:
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "PLAYABLE_MP3"
    if data.startswith(b"RIFF") and b"WAVE" in data[:16]:
        return "PLAYABLE_WAV"
    if data.startswith(b"CXA1") or data.startswith(b"CXO1"):
        return "ENCRYPTED_CAMXORA"
    low = data.lower()
    if b"encrypted" in low or b"encrypted_playback_required" in low:
        return "REFUSED_ENCRYPTED_PLAYER"
    if status in {"401", "403"}:
        return "AUTH_BLOCKED"
    if status in {"404", "422"}:
        return "REFUSED_HTTP"
    return f"OTHER status={status} ct={content_type!r} head={data[:20]!r}"


def curl(url: str, token: str, range_header: str) -> tuple[str, str, bytes]:
    hdr = "/tmp/cx-prod-probe-hdr"
    body = "/tmp/cx-prod-probe-body"
    subprocess.run(
        [
            "curl", "-sS", "-o", body, "-D", hdr,
            "--connect-timeout", "15", "--max-time", "45",
            "-H", "CF-IPCountry: KH",
            "-H", "accept-encoding: identity",
            "-H", "user-agent: Camxora-Production-Probe",
            "-H", f"range: bytes={range_header}",
            "-b", f"camxora_access_token={token}",
            url,
        ],
        check=False,
    )
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


async def counts(pool):
    tracks_ready = await pool.fetchval(
        "SELECT COUNT(*) FROM stream_tracks WHERE COALESCE(package_status, 'none') = 'ready'"
    )
    tracks_left = await pool.fetchval(
        """
        SELECT COUNT(*) FROM stream_tracks
        WHERE COALESCE(package_status, 'none') = 'none'
          AND storage_key IS NOT NULL AND storage_key <> ''
        """
    )
    tasks_ready = await pool.fetchval(
        """
        SELECT COUNT(*) FROM suno_tasks
        WHERE source = 'web_music' AND COALESCE(package_status_ok, 'none') = 'ready'
        """
    )
    tasks_left = await pool.fetchval(
        """
        SELECT COUNT(*) FROM suno_tasks
        WHERE source = 'web_music'
          AND (
            (COALESCE(package_status_ok, 'none') = 'none' AND COALESCE(b2_storage_key_ok, '') <> '')
            OR (COALESCE(package_status_alt, 'none') = 'none' AND COALESCE(b2_storage_key_alt, '') <> '')
          )
        """
    )
    return int(tracks_ready), int(tracks_left), int(tasks_ready), int(tasks_left)


async def main() -> int:
    settings = get_settings()
    print("env=", settings.environment, flush=True)
    if not is_production(settings):
        print("REFUSE: not production environment")
        return 2
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        cfg = await resolve_streaming_storage_config(pool, settings=settings)
        print("b2_bucket=", cfg.bucket, flush=True)
        print("cdn=", cfg.cdn_base_url, flush=True)
        if not cfg.configured:
            print("REFUSE: storage not configured")
            return 2
        cdn = (cfg.cdn_base_url or "").lower()
        bucket = (cfg.bucket or "").lower()
        if "sandbox" in cdn or "sandbox" in bucket:
            print("REFUSE: sandbox storage markers present")
            return 2
        if "camxora.com" not in cdn and "backblaze" not in (cfg.endpoint or "").lower():
            print("REFUSE: CDN/endpoint does not look like production")
            return 2

        ready_t, left_t, ready_s, left_s = await counts(pool)
        print(
            f"before ready_catalog={ready_t} leftover_catalog={left_t} ready_create={ready_s} leftover_create={left_s}",
            flush=True,
        )
        svc = AudioPackageService(pool)
        packaged_total = 0
        for i in range(MAX_BATCHES):
            result = await svc.backfill(limit=BATCH_SIZE)
            n = int(result.get("packaged") or 0)
            packaged_total += n
            print(f"batch={i+1} result={result}", flush=True)
            if n == 0:
                break
        ready_t, left_t, ready_s, left_s = await counts(pool)
        print(
            f"after packaged_this_run={packaged_total} ready_catalog={ready_t} leftover_catalog={left_t} ready_create={ready_s} leftover_create={left_s}",
            flush=True,
        )

        track = await pool.fetchrow(
            """
            SELECT t.id, t.user_id, t.package_status
            FROM stream_tracks t
            JOIN users u ON u.id = t.user_id
            WHERE COALESCE(t.package_status, 'none') = 'ready'
              AND COALESCE(u.email_confirmed, false) = true
              AND u.status = 'active'
            ORDER BY t.updated_at DESC NULLS LAST
            LIMIT 1
            """
        )
        if track is None:
            print("NO_PACKAGED_TRACK_TO_PROBE", flush=True)
            return 0
        user = await pool.fetchrow(
            """
            SELECT id, email, role, COALESCE(token_version, 0) AS token_version
            FROM users WHERE id = $1
            """,
            track["user_id"],
        )
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "user_id": str(user["id"]),
                "email": user["email"],
                "role": str(user["role"] or "user"),
                "token_version": int(user["token_version"] or 0),
                "exp": now + timedelta(minutes=10),
                "iat": now,
                "type": "access",
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        if isinstance(token, bytes):
            token = token.decode("ascii")
        url = f"https://music.camxora.com/api/v1/public/streaming/tracks/{track['id']}/stream"
        print("probe_track=", track["id"], flush=True)
        print("url=", url, flush=True)
        glued = bytearray()
        for rng in ("0-0", "0-", "262144-"):
            status, ctype, body = curl(url, token, rng)
            kind = classify(body, ctype, status)
            print(f"range={rng} status={status} bytes={len(body)} class={kind}", flush=True)
            if status in {"200", "206"} and body:
                glued.extend(body)
            if kind != "PLAYABLE_MP3":
                break
        glued_kind = classify(bytes(glued), "", "206") if glued else "EMPTY"
        print("concat_bytes=", len(glued), "concat_class=", glued_kind, flush=True)
        print("FULL_PLAYABLE_MP3=", glued_kind == "PLAYABLE_MP3" and len(glued) > 1024, flush=True)
    finally:
        await pool.close()
        for p in ("/tmp/cx-prod-probe-hdr", "/tmp/cx-prod-probe-body"):
            Path(p).unlink(missing_ok=True)
    print("PROD_BACKFILL_PROBE_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}", flush=True)
    if host != CANONICAL_PRODUCTION_HOST:
        print(f"REFUSE: expected production {CANONICAL_PRODUCTION_HOST}, got {host}")
        return 2
    if host == CANONICAL_SANDBOX_HOST:
        print("REFUSE: sandbox host")
        return 2
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("uploading backfill script", flush=True)
    _, mkdir_out, _ = client.exec_command("mkdir -p /opt/camxora/tmp && chmod 775 /opt/camxora/tmp")
    mkdir_out.channel.recv_exit_status()
    remote = "/opt/camxora/tmp/production_backfill_protected_audio.py"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(REMOTE_PY)
        local_py = tmp.name
    sftp = client.open_sftp()
    sftp.put(local_py, remote)
    sftp.close()
    Path(local_py).unlink(missing_ok=True)
    print("running leftover encrypt (max 8 x 10)", flush=True)
    cmd = r"""
set -e
chown camxora:camxora /opt/camxora/tmp/production_backfill_protected_audio.py
sudo -u camxora bash -lc 'cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo PYTHONUNBUFFERED=1 /opt/camxora/repo/platform_api/.venv/bin/python -u /opt/camxora/tmp/production_backfill_protected_audio.py'
rm -f /opt/camxora/tmp/production_backfill_protected_audio.py
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    sys.stdout.buffer.write((out + ("\n" + err if err.strip() else "")).encode("utf-8", errors="replace"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
