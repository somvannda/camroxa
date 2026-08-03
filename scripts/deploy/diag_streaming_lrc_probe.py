#!/usr/bin/env python3
"""Probe one recent track's LRC fetch prerequisites on production."""
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
SELECT st.id::text, st.title, st.suno_audio_id, t.external_task_id,
       left(coalesce(st.lyrics,''),80) AS lyrics_head,
       (st.lyrics ~ '\[[0-9]{1,2}:[0-9]{2}') AS is_lrc
FROM stream_tracks st
LEFT JOIN suno_tasks t ON t.id = st.suno_task_id
WHERE st.suno_audio_id IS NOT NULL AND st.suno_audio_id <> ''
ORDER BY st.created_at DESC
LIMIT 3;
"
echo ---LRC WITH AUDIO---
sudo -u postgres psql -d camxora_platform -c "
SELECT
  count(*) FILTER (WHERE lyrics ~ '\[[0-9]{1,2}:[0-9]{2}' AND suno_audio_id IS NOT NULL AND suno_audio_id <> '') AS lrc_with_audio,
  count(*) FILTER (WHERE lyrics ~ '\[[0-9]{1,2}:[0-9]{2}' AND (suno_audio_id IS NULL OR suno_audio_id = '')) AS lrc_without_audio
FROM stream_tracks;
"
echo ---API LOGS---
journalctl -u camxora-api --since '2 days ago' --no-pager 2>/dev/null | grep -i 'timestamped lyrics' | tail -30
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=90)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
