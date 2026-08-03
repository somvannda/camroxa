#!/usr/bin/env python3
"""Check production stream_tracks for LRC karaoke coverage."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    pr = load_env("secrets.production.env")
    host = pr.get("PRODUCTION_VPS_HOST") or pr["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        pr.get("PRODUCTION_VPS_USER") or pr["VPS_USER"],
        ensure_deploy_key(),
        pr.get("PRODUCTION_VPS_PASSWORD") or pr.get("VPS_PASSWORD"),
    )
    try:
        cmd = r"""
sudo -u postgres psql -d camxora_platform -c "
SELECT
  count(*) AS tracks,
  count(*) FILTER (WHERE lyrics IS NOT NULL AND lyrics <> '') AS has_lyrics,
  count(*) FILTER (WHERE lyrics ~ '\[[0-9]{1,2}:[0-9]{2}') AS has_lrc_tag,
  count(*) FILTER (WHERE suno_audio_id IS NOT NULL AND suno_audio_id <> '') AS has_audio_id,
  count(*) FILTER (WHERE suno_task_id IS NOT NULL) AS has_suno_task
FROM stream_tracks;
"
echo ---RECENT---
sudo -u postgres psql -d camxora_platform -c "
SELECT left(title,35) AS title,
  (lyrics ~ '\[[0-9]{1,2}:[0-9]{2}') AS is_lrc,
  left(coalesce(suno_audio_id,''),12) AS audio_id,
  (suno_task_id IS NOT NULL) AS has_task,
  created_at
FROM stream_tracks
ORDER BY created_at DESC
LIMIT 12;
"
echo ---SUNO TASK IDS---
sudo -u postgres psql -d camxora_platform -c "
SELECT
  count(*) FILTER (WHERE st.suno_audio_id IS NOT NULL AND st.suno_audio_id <> '') AS track_audio,
  count(*) FILTER (WHERE t.external_task_id IS NOT NULL AND t.external_task_id <> '') AS ext_task,
  count(*) FILTER (
    WHERE st.suno_audio_id IS NOT NULL AND st.suno_audio_id <> ''
      AND t.external_task_id IS NOT NULL AND t.external_task_id <> ''
      AND NOT (st.lyrics ~ '\[[0-9]{1,2}:[0-9]{2}')
  ) AS recoverable_no_lrc
FROM stream_tracks st
LEFT JOIN suno_tasks t ON t.id = st.suno_task_id;
"
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=60)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
