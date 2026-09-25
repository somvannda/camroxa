#!/usr/bin/env python3
"""Production: backfill Xing/Info headers on archived MP3s in Backblaze B2.

Suno CDN MP3s omit the Xing/Info header, so ffprobe and players over-report the
duration and exported MP4s look shorter than the MP3. New uploads are fixed at
archive time; this sweep re-muxes MP3s already in B2 so every desktop client
(including older builds) downloads a correctly-labelled file.

The header check uses a ranged 8 KiB read, so only objects that actually need
fixing are downloaded and re-uploaded. The sweep runs as a background job on the
server (log: /tmp/mp3xing-backfill.log) so SSH never blocks on a long scan.

Usage:
  python backfill_mp3_duration_headers_production.py --apply          # start fix in background
  python backfill_mp3_duration_headers_production.py --dry-run        # start scan-only in background
  python backfill_mp3_duration_headers_production.py --limit 200 --apply
  python backfill_mp3_duration_headers_production.py --status         # tail log / running state
  python backfill_mp3_duration_headers_production.py --kill           # stop a running sweep
"""
from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")
REMOTE_PROGRAM = "/tmp/mp3xing_backfill.py"
LOG_PATH = "/tmp/mp3xing-backfill.log"

REMOTE_PY = r'''
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/camxora/repo")

env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

import asyncpg
import boto3
from botocore.config import Config as BotoConfig
from platform_api.services.mp3_duration_header import (
    HEADER_SCAN_BYTES,
    ensure_mp3_duration_header,
    looks_like_mpeg_audio,
    mp3_has_duration_header,
)
from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config

APPLY = os.environ.get("APPLY") == "1"
LIMIT = int(os.environ.get("LIMIT") or "0")
HEAD_WORKERS = int(os.environ.get("HEAD_WORKERS") or "24")
FIX_WORKERS = int(os.environ.get("FIX_WORKERS") or "6")
BATCH = 400


async def main() -> None:
    dsn = os.environ.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not dsn:
        print("NO_DSN", flush=True)
        return
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        config = await resolve_streaming_storage_config(pool)
        if not config.configured:
            print("STORAGE_NOT_CONFIGURED", flush=True)
            return
        storage = StorageService.from_config(config)
        client = boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.key_id,
            aws_secret_access_key=config.application_key,
            region_name=config.region,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

        rows = await pool.fetch(
            """
            SELECT DISTINCT key FROM (
                SELECT b2_storage_key_ok AS key FROM suno_tasks
                  WHERE b2_storage_key_ok IS NOT NULL AND btrim(b2_storage_key_ok) <> ''
                UNION ALL
                SELECT b2_storage_key_alt FROM suno_tasks
                  WHERE b2_storage_key_alt IS NOT NULL AND btrim(b2_storage_key_alt) <> ''
                UNION ALL
                SELECT storage_key FROM stream_tracks
                  WHERE storage_key IS NOT NULL AND btrim(storage_key) <> ''
            ) k
            WHERE key NOT LIKE '%.cxa' AND key NOT LIKE '%.cxo' AND key NOT LIKE '%.wav'
            ORDER BY key
            """
        )
        keys = [str(r["key"]) for r in rows]
        if LIMIT > 0:
            keys = keys[:LIMIT]
        print(f"SCAN_KEYS {len(keys)} apply={APPLY}", flush=True)

        import concurrent.futures

        loop = asyncio.get_running_loop()
        loop.set_default_executor(
            concurrent.futures.ThreadPoolExecutor(max_workers=max(HEAD_WORKERS, FIX_WORKERS))
        )

        def _head(key: str) -> bytes:
            resp = client.get_object(
                Bucket=config.bucket, Key=key, Range=f"bytes=0-{HEADER_SCAN_BYTES - 1}"
            )
            return resp["Body"].read()

        async def _scan_one(key: str):
            try:
                return key, await asyncio.to_thread(_head, key)
            except Exception:
                return key, None

        scanned = skipped = need_fix = not_mpeg = normalized = failed = 0
        need_keys: list[str] = []
        not_mpeg_samples: list[str] = []
        for start in range(0, len(keys), BATCH):
            batch = keys[start : start + BATCH]
            for key, head in await asyncio.gather(*(_scan_one(k) for k in batch)):
                scanned += 1
                if head is None:
                    failed += 1
                elif mp3_has_duration_header(head):
                    skipped += 1
                elif not looks_like_mpeg_audio(head):
                    # Opus-in-MP4 / other container stored under a .mp3 key:
                    # there is no Xing header to add; leave it untouched.
                    not_mpeg += 1
                    if len(not_mpeg_samples) < 5:
                        not_mpeg_samples.append(key)
                else:
                    need_fix += 1
                    need_keys.append(key)
            print(
                f"  progress scanned={scanned} already_ok={skipped} "
                f"need_fix={need_fix} not_mpeg={not_mpeg} failed={failed}",
                flush=True,
            )
        if not_mpeg_samples:
            print("NOT_MPEG_SAMPLES " + " | ".join(not_mpeg_samples), flush=True)

        if APPLY and need_keys:
            fix_sem = asyncio.Semaphore(FIX_WORKERS)

            def _has_header_wide(blob: bytes) -> bool:
                # Cover art can push the Xing/Info frame past the 8 KiB probe.
                head = blob[:262144]
                return b"Xing" in head or b"Info" in head

            async def _fix_one(key: str) -> str:
                async with fix_sem:
                    try:
                        data = await storage.download_bytes(key)
                        if not looks_like_mpeg_audio(data):
                            return "not_mpeg"
                        if _has_header_wide(data):
                            return "already_ok"
                        fixed = await asyncio.to_thread(ensure_mp3_duration_header, data)
                        if fixed is data or not _has_header_wide(fixed):
                            print(f"  ERR remux {key}", flush=True)
                            return "failed"
                        await storage.upload_bytes(
                            key=key, data=fixed, content_type="audio/mpeg"
                        )
                        return "fixed"
                    except Exception as exc:
                        print(
                            f"  ERR fix {key}: {type(exc).__name__} {str(exc)[:120]}",
                            flush=True,
                        )
                        return "failed"

            statuses = await asyncio.gather(*(_fix_one(k) for k in need_keys))
            normalized = sum(1 for s in statuses if s == "fixed")
            late_not_mpeg = sum(1 for s in statuses if s == "not_mpeg")
            already = sum(1 for s in statuses if s == "already_ok")
            failed += sum(1 for s in statuses if s == "failed")
            not_mpeg += late_not_mpeg
            skipped += already
            print(
                f"  fixed={normalized} already_ok={already} "
                f"not_mpeg={late_not_mpeg} failed={failed}",
                flush=True,
            )

        print(
            f"BACKFILL_RESULT scanned={scanned} already_ok={skipped} "
            f"need_fix={need_fix} not_mpeg={not_mpeg} normalized={normalized} "
            f"failed={failed} apply={APPLY}",
            flush=True,
        )
    finally:
        await pool.close()


asyncio.run(main())
'''

_SWEEP_PATTERN = r"mp3xing_backfill\.py|\.venv/bin/python -$"

INSPECT_PY = r'''
import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/opt/camxora/repo")
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

import asyncpg
import boto3
from botocore.config import Config as BotoConfig
from platform_api.services.mp3_duration_header import (
    ensure_mp3_duration_header,
    looks_like_mpeg_audio,
    mp3_has_duration_header,
)
from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config


def _probe(blob: bytes, label: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.mp3"
        p.write_bytes(blob)
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(p)],
                capture_output=True, text=True, timeout=60,
            )
            print(f"FFPROBE_{label}={out.stdout.strip()} err={out.stderr.strip()[:120]}", flush=True)
        except Exception as exc:
            print(f"FFPROBE_{label}_ERR={exc}", flush=True)


async def main() -> None:
    dsn = os.environ.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    try:
        config = await resolve_streaming_storage_config(pool)
        client = boto3.client(
            "s3", endpoint_url=config.endpoint, aws_access_key_id=config.key_id,
            aws_secret_access_key=config.application_key, region_name=config.region,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        storage = StorageService.from_config(config)
        key = os.environ["INSPECT_KEY"]
        print("KEY", key, flush=True)
        head = client.get_object(Bucket=config.bucket, Key=key, Range="bytes=0-1048575")["Body"].read()
        print("HEAD_LEN", len(head), "STARTS_ID3", head[:3] == b"ID3", flush=True)
        if head[:3] == b"ID3":
            size = (head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]
            print("ID3_TAG_BYTES", 10 + size, flush=True)
        print("MPEG", looks_like_mpeg_audio(head), flush=True)
        print("HEAD_XING_POS", head.find(b"Xing"), "HEAD_INFO_POS", head.find(b"Info"), flush=True)
        data = await storage.download_bytes(key)
        print("FULL_LEN", len(data), flush=True)
        fixed = ensure_mp3_duration_header(data)
        print("FIXED_IS_SAME", fixed is data, "FIXED_LEN", len(fixed), flush=True)
        print("FIXED_HDR_8K", mp3_has_duration_header(fixed),
              "FIXED_XING_POS", fixed[:1048576].find(b"Xing"),
              "FIXED_INFO_POS", fixed[:1048576].find(b"Info"), flush=True)
        _probe(data, "orig")
        _probe(fixed, "fixed")
    finally:
        await pool.close()


asyncio.run(main())
'''

CDN_PY = r'''
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/camxora/repo")
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

import asyncpg
from platform_api.services.streaming_config_service import resolve_streaming_storage_config


async def main() -> None:
    dsn = os.environ.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    try:
        config = await resolve_streaming_storage_config(pool)
        print("CDN_BASE_URL=" + (config.cdn_base_url or "(none)"), flush=True)
        try:
            rows = await pool.fetch(
                "SELECT key FROM system_settings "
                "WHERE key ILIKE '%cloudflare%' OR key ILIKE '%purge%' "
                "OR key ILIKE '%cache%' OR key ILIKE '%cdn%' ORDER BY key"
            )
            print("SETTINGS_KEYS=" + ",".join(str(r["key"]) for r in rows), flush=True)
        except Exception as exc:
            print("SETTINGS_KEYS_ERR", exc, flush=True)
        env_keys = [
            k for k in os.environ
            if any(t in k.upper() for t in ("CLOUDFLARE", "CF_", "PURGE", "CACHE", "CDN", "BUNNY"))
        ]
        print("ENV_KEYS=" + ",".join(sorted(env_keys)), flush=True)
    finally:
        await pool.close()


asyncio.run(main())
'''

CDNVERIFY_PY = r'''
import asyncio
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/camxora/repo")
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

import asyncpg
import boto3
import httpx
from botocore.config import Config as BotoConfig
from platform_api.services.mp3_duration_header import mp3_has_duration_header
from platform_api.services.streaming_config_service import resolve_streaming_storage_config

HOURS = float(os.environ.get("HOURS") or "3")
N = int(os.environ.get("N") or "8")


async def main() -> None:
    dsn = os.environ.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    try:
        config = await resolve_streaming_storage_config(pool)
        client = boto3.client(
            "s3", endpoint_url=config.endpoint, aws_access_key_id=config.key_id,
            aws_secret_access_key=config.application_key, region_name=config.region,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        rows = await pool.fetch(
            "SELECT storage_key FROM stream_tracks "
            "WHERE storage_key LIKE '%.mp3' AND storage_key NOT LIKE '%.cxa' "
            "ORDER BY random() LIMIT $1",
            N,
        )
        keys = [str(r["storage_key"]) for r in rows]
        print(f"CDN_SAMPLE={len(keys)} (B2 now has headers for all MPEG keys)", flush=True)
        cdn = config.cdn_base_url.rstrip("/")
        if not cdn:
            print("NO_CDN", flush=True)
            return
        def _b2_head(key: str) -> bytes:
            resp = client.get_object(Bucket=config.bucket, Key=key, Range="bytes=0-8191")
            return resp["Body"].read()

        stale = 0
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
            for key in keys:
                url = f"{cdn}/{key}"
                try:
                    b2_head = await asyncio.to_thread(_b2_head, key)
                except Exception as exc:
                    print(f"B2_ERR {key}: {exc}", flush=True)
                    continue
                b2_hdr = mp3_has_duration_header(b2_head)
                try:
                    r = await http.get(url, headers={"Range": "bytes=0-8191"})
                    cdn_hdr = mp3_has_duration_header(r.content)
                    is_stale = b2_hdr and not cdn_hdr
                    if is_stale:
                        stale += 1
                    print(
                        f"b2_hdr={b2_hdr} cdn_hdr={cdn_hdr} cache={r.headers.get('cf-cache-status', '?')} "
                        f"{'STALE ' if is_stale else ''}{key}",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"CDN_ERR {key}: {exc}", flush=True)
        print(f"CDN_STALE={stale}/{len(keys)}", flush=True)
    finally:
        await pool.close()


asyncio.run(main())
'''

STATUS_CMD = r'''
echo "=== running sweep ==="
ps -eo pid,etimes,time,stat,pcpu,args | grep -E "mp3xing_backfill\.py|\.venv/bin/python -$" | grep -v grep || echo "(not running)"
echo "=== detail ==="
for p in $(ps -eo pid,args | grep -E "mp3xing_backfill\.py" | grep -v grep | awk '{print $1}'); do
  echo "PID $p"
  grep -E "State|Threads|VmRSS" /proc/$p/status 2>/dev/null
  echo "sockets=$(ls -l /proc/$p/fd 2>/dev/null | grep -c socket) children=$(pgrep -P $p 2>/dev/null | wc -l)"
done
echo "=== log tail ==="
tail -n 12 /tmp/mp3xing-backfill.log 2>/dev/null || echo "(no log)"
'''

KILL_CMD = r'''
ps -eo pid,args | grep -E "mp3xing_backfill\.py|\.venv/bin/python -$" | grep -v grep | awk '{print $1}' | xargs -r kill
sleep 1
echo KILLED
'''


def _connection():
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    return host, ssh_connect(host, user, ensure_deploy_key(), password)


def main() -> int:
    if "--inspect" in sys.argv:
        idx = sys.argv.index("--inspect")
        key = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if not key:
            raise SystemExit("--inspect requires a B2 object key")
        host, client = _connection()
        print(f"=== inspect {host} ===")
        try:
            sftp = client.open_sftp()
            with sftp.file("/tmp/mp3xing_inspect.py", "wb") as remote_file:
                remote_file.write(INSPECT_PY.encode("utf-8"))
            sftp.close()
            cmd = (
                "cd /opt/camxora/repo/platform_api && "
                f"INSPECT_KEY={shlex.quote(key)} PYTHONPATH=/opt/camxora/repo "
                ".venv/bin/python /tmp/mp3xing_inspect.py"
            )
            _, out, err = client.exec_command(cmd, timeout=300)
            print(out.read().decode("utf-8", errors="replace"))
            e = err.read().decode("utf-8", errors="replace")
            if e.strip():
                print("STDERR:", e[-2000:])
            return 0
        finally:
            client.close()

    if "--cdn-verify" in sys.argv:
        host, client = _connection()
        print(f"=== CDN freshness check {host} ===")
        try:
            sftp = client.open_sftp()
            with sftp.file("/tmp/mp3xing_cdnverify.py", "wb") as remote_file:
                remote_file.write(CDNVERIFY_PY.encode("utf-8"))
            sftp.close()
            _, out, err = client.exec_command(
                "cd /opt/camxora/repo/platform_api && N=60 PYTHONPATH=/opt/camxora/repo "
                ".venv/bin/python /tmp/mp3xing_cdnverify.py",
                timeout=300,
            )
            print(out.read().decode("utf-8", errors="replace"))
            e = err.read().decode("utf-8", errors="replace")
            if e.strip():
                print("STDERR:", e[-1500:])
            return 0
        finally:
            client.close()

    if "--cdn" in sys.argv:
        host, client = _connection()
        print(f"=== CDN config {host} ===")
        try:
            sftp = client.open_sftp()
            with sftp.file("/tmp/mp3xing_cdn.py", "wb") as remote_file:
                remote_file.write(CDN_PY.encode("utf-8"))
            sftp.close()
            _, out, err = client.exec_command(
                "cd /opt/camxora/repo/platform_api && PYTHONPATH=/opt/camxora/repo "
                ".venv/bin/python /tmp/mp3xing_cdn.py",
                timeout=120,
            )
            print(out.read().decode("utf-8", errors="replace"))
            e = err.read().decode("utf-8", errors="replace")
            if e.strip():
                print("STDERR:", e[-1000:])
            return 0
        finally:
            client.close()

    if "--status" in sys.argv:
        host, client = _connection()
        print(f"=== MP3 duration-header backfill status {host} ===")
        try:
            _, out, _ = client.exec_command(STATUS_CMD, timeout=60)
            print(out.read().decode("utf-8", errors="replace"))
            return 0
        finally:
            client.close()

    if "--kill" in sys.argv:
        host, client = _connection()
        print(f"=== stopping MP3 duration-header backfill {host} ===")
        try:
            _, out, _ = client.exec_command(KILL_CMD, timeout=60)
            print(out.read().decode("utf-8", errors="replace"))
            return 0
        finally:
            client.close()

    apply = "--apply" in sys.argv
    limit = "0"
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = sys.argv[idx + 1]

    host, client = _connection()
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== MP3 duration-header backfill [{mode}] {host} limit={limit} ===")
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE_PROGRAM, "wb") as remote_file:
            remote_file.write(REMOTE_PY.encode("utf-8"))
        sftp.close()

        launch = (
            "cd /opt/camxora/repo/platform_api && "
            f"APPLY={'1' if apply else '0'} LIMIT={limit} PYTHONPATH=/opt/camxora/repo "
            f"setsid nohup .venv/bin/python {REMOTE_PROGRAM} </dev/null "
            f">{LOG_PATH} 2>&1 & echo STARTED"
        )
        _, out, _ = client.exec_command(launch, timeout=30)
        try:
            print(out.read().decode("utf-8", errors="replace").strip())
        except Exception:
            pass
        print(f"Started in background. Poll with: --status  (log: {LOG_PATH})")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
