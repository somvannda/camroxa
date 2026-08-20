#!/usr/bin/env python3
"""Start a single production B2 encrypt loop until leftover MP3/WAV/LRC are sealed.

Host must be 82.197.71.248. Does not touch sandbox. SRT is derived from LRC.
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
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

REMOTE_PY = r'''
import asyncio
import os
import sys
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

import asyncpg
from platform_api.config import get_settings, is_production
from platform_api.services.audio_package_service import AudioPackageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config

BATCH = 10
LOG = Path("/opt/camxora/tmp/production_mp3_backfill.log")


def log(msg: str) -> None:
    line = msg.rstrip() + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)


async def leftover(pool) -> dict:
    catalog = await pool.fetchval(
        """
        SELECT COUNT(*) FROM stream_tracks t
        INNER JOIN suno_tasks s ON s.id = t.suno_task_id AND s.source = 'web_music'
        WHERE COALESCE(t.package_status, 'none') = 'none'
          AND t.storage_key IS NOT NULL AND t.storage_key <> ''
        """
    )
    create = await pool.fetchval(
        """
        SELECT COUNT(*) FROM suno_tasks
        WHERE source = 'web_music'
          AND (
            (COALESCE(package_status_ok, 'none') = 'none' AND COALESCE(b2_storage_key_ok, '') <> '')
            OR (COALESCE(package_status_alt, 'none') = 'none' AND COALESCE(b2_storage_key_alt, '') <> '')
          )
        """
    )
    catalog_src = await pool.fetchval(
        """
        SELECT COUNT(*) FROM stream_tracks t
        INNER JOIN suno_tasks s ON s.id = t.suno_task_id AND s.source = 'web_music'
        WHERE COALESCE(t.package_status, 'none') = 'ready'
          AND t.storage_key IS NOT NULL AND t.storage_key <> ''
          AND t.content_key_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM audio_package_jobs j
            WHERE j.subject_type = 'stream_track_source'
              AND j.subject_id = t.id AND j.status = 'ready'
          )
        """
    )
    create_src = await pool.fetchval(
        """
        SELECT COUNT(*) FROM suno_tasks
        WHERE source = 'web_music'
          AND (
            (
              COALESCE(package_status_ok, 'none') = 'ready'
              AND content_key_id_ok IS NOT NULL
              AND COALESCE(b2_storage_key_ok, '') <> ''
              AND NOT EXISTS (
                SELECT 1 FROM audio_package_jobs j
                WHERE j.subject_type = 'suno_task_source'
                  AND j.subject_id = suno_tasks.id AND j.variant = 'ok' AND j.status = 'ready'
              )
            )
            OR (
              COALESCE(package_status_alt, 'none') = 'ready'
              AND content_key_id_alt IS NOT NULL
              AND COALESCE(b2_storage_key_alt, '') <> ''
              AND NOT EXISTS (
                SELECT 1 FROM audio_package_jobs j
                WHERE j.subject_type = 'suno_task_source'
                  AND j.subject_id = suno_tasks.id AND j.variant = 'alt' AND j.status = 'ready'
              )
            )
          )
        """
    )
    wav = await pool.fetchval(
        """
        SELECT COUNT(*) FROM suno_tasks
        WHERE source = 'web_music'
          AND (
            (content_key_id_ok IS NOT NULL AND COALESCE(b2_wav_storage_key_ok, '') <> ''
             AND NOT EXISTS (
               SELECT 1 FROM audio_package_jobs j
               WHERE j.subject_type = 'suno_wav' AND j.subject_id = suno_tasks.id
                 AND j.variant = 'ok' AND j.status = 'ready'
             ))
            OR (content_key_id_alt IS NOT NULL AND COALESCE(b2_wav_storage_key_alt, '') <> ''
             AND NOT EXISTS (
               SELECT 1 FROM audio_package_jobs j
               WHERE j.subject_type = 'suno_wav' AND j.subject_id = suno_tasks.id
                 AND j.variant = 'alt' AND j.status = 'ready'
             ))
          )
        """
    )
    lrc = await pool.fetchval(
        """
        SELECT COUNT(*) FROM suno_tasks
        WHERE source = 'web_music'
          AND (
            (content_key_id_ok IS NOT NULL AND COALESCE(b2_lrc_storage_key_ok, '') <> ''
             AND NOT EXISTS (
               SELECT 1 FROM audio_package_jobs j
               WHERE j.subject_type = 'suno_lrc' AND j.subject_id = suno_tasks.id
                 AND j.variant = 'ok' AND j.status = 'ready'
             ))
            OR (content_key_id_alt IS NOT NULL AND COALESCE(b2_lrc_storage_key_alt, '') <> ''
             AND NOT EXISTS (
               SELECT 1 FROM audio_package_jobs j
               WHERE j.subject_type = 'suno_lrc' AND j.subject_id = suno_tasks.id
                 AND j.variant = 'alt' AND j.status = 'ready'
             ))
          )
        """
    )
    return {
        "catalog_mp3": int(catalog or 0),
        "create_mp3": int(create or 0),
        "catalog_source": int(catalog_src or 0),
        "create_source": int(create_src or 0),
        "wav": int(wav or 0),
        "lrc": int(lrc or 0),
    }


async def main() -> int:
    settings = get_settings()
    if not is_production(settings):
        log("REFUSE: not production")
        return 2
    pool = await asyncpg.create_pool(
        settings.database_url.replace("postgresql+asyncpg://", "postgresql://"),
        min_size=1,
        max_size=3,
    )
    try:
        cfg = await resolve_streaming_storage_config(pool, settings=settings)
        cdn = (cfg.cdn_base_url or "").lower()
        bucket = (cfg.bucket or "").lower()
        log(f"env={settings.environment} bucket={cfg.bucket} cdn={cfg.cdn_base_url}")
        log("scope=web_music_only skip_studio=true")
        if "sandbox" in cdn or "sandbox" in bucket:
            log("REFUSE: sandbox storage")
            return 2
        svc = AudioPackageService(pool)
        totals = {"packaged": 0, "sealed_sources": 0, "sealed_exports": 0}
        empty = 0
        while True:
            q = await leftover(pool)
            remaining = sum(q.values())
            log(f"queue={q} remaining={remaining} totals={totals}")
            if remaining == 0:
                log("QUEUE_EMPTY")
                break
            result = await svc.backfill(limit=BATCH, web_music_only=True)
            n = (
                int(result.get("packaged") or 0)
                + int(result.get("sealed_sources") or 0)
                + int(result.get("sealed_exports") or 0)
            )
            totals["packaged"] += int(result.get("packaged") or 0)
            totals["sealed_sources"] += int(result.get("sealed_sources") or 0)
            totals["sealed_exports"] += int(result.get("sealed_exports") or 0)
            log(f"batch={result}")
            if n == 0:
                empty += 1
                if empty >= 5:
                    log("STOP: five empty batches with leftover remaining (failed objects?)")
                    log(f"remaining={await leftover(pool)}")
                    break
                await asyncio.sleep(2)
            else:
                empty = 0
        log(f"DONE totals={totals}")
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}", flush=True)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        print("REFUSE host", host)
        return 2
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    _, mkdir_out, _ = client.exec_command(
        "sudo mkdir -p /opt/camxora/tmp && sudo chown camxora:camxora /opt/camxora/tmp && sudo chmod 775 /opt/camxora/tmp"
    )
    mkdir_out.channel.recv_exit_status()
    remote = "/opt/camxora/tmp/production_mp3_backfill_loop.py"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(REMOTE_PY)
        local_py = tmp.name
    sftp = client.open_sftp()
    sftp.put(local_py, remote)
    sftp.close()
    Path(local_py).unlink(missing_ok=True)
    cmd = r"""
set -e
LOOP=/opt/camxora/tmp/production_mp3_backfill_loop.py
LOG=/opt/camxora/tmp/production_mp3_backfill.log
UNIT=camxora-b2-encrypt-loop.service
sudo mkdir -p /opt/camxora/tmp
sudo chown camxora:camxora /opt/camxora/tmp
sudo chmod 775 /opt/camxora/tmp
sudo chown camxora:camxora "$LOOP"
sudo touch "$LOG"
sudo chown camxora:camxora "$LOG"
if systemctl list-units --all --no-legend "$UNIT" | grep -q camxora-b2-encrypt-loop; then
  echo STOPPING_STALE_UNIT
  sudo systemctl stop "$UNIT" || true
  sudo systemctl reset-failed "$UNIT" || true
fi
ps -eo pid,cmd | awk '$2 == "/opt/camxora/repo/platform_api/.venv/bin/python" && /production_mp3_backfill_loop.py/ {print $1}' | while read -r p; do
  echo KILL_STALE_PYTHON pid=$p
  sudo kill "$p" || true
done
sleep 1
sudo systemd-run --unit=camxora-b2-encrypt-loop --uid=camxora --gid=camxora \
  --working-directory=/opt/camxora/repo \
  --property=StandardOutput=append:/opt/camxora/tmp/production_mp3_backfill.log \
  --property=StandardError=append:/opt/camxora/tmp/production_mp3_backfill.log \
  --setenv=PYTHONPATH=/opt/camxora/repo \
  --setenv=PYTHONUNBUFFERED=1 \
  /opt/camxora/repo/platform_api/.venv/bin/python -u /opt/camxora/tmp/production_mp3_backfill_loop.py
sleep 2
systemctl is-active camxora-b2-encrypt-loop || true
systemctl show camxora-b2-encrypt-loop -p MainPID -p ActiveState --no-pager || true
sudo tail -n 50 "$LOG" || true
echo BACKFILL_LOOP_STARTED
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    sys.stdout.buffer.write((out + ("\n" + err if err.strip() else "")).encode("utf-8", errors="replace"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
