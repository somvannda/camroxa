#!/usr/bin/env python3
"""Read-only diagnosis of the chronic "B2 backfill sweep / wav_failed" alert.

Shows the exact web-music tasks that ``list_web_music_tasks_missing_wav`` keeps
returning, their WAV conversion state, and the recent WAV-related API log lines
so the failing branch in ``_upload_web_music_wav`` is identifiable.

Makes no changes to production.
"""
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
echo '=== [1] Rows the sweep keeps retrying (missing WAV) ==='
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT st.id,
       st.created_at,
       st.wav_status_ok,  st.wav_task_id_ok,  st.wav_url_ok,
       st.wav_status_alt, st.wav_task_id_alt, st.wav_url_alt,
       (coalesce(st.audio_id_ok,'')<>'')  AS has_audio_ok,
       (coalesce(st.audio_id_alt,'')<>'') AS has_audio_alt,
       (coalesce(st.external_task_id,'')<>'') AS has_ext_task
FROM suno_tasks st
WHERE st.status = 'success' AND st.source = 'web_music'
  AND (
    (coalesce(st.b2_wav_storage_key_ok,'')=''  AND coalesce(st.audio_id_ok,'')<>'')
    OR
    (coalesce(st.b2_wav_storage_key_alt,'')='' AND coalesce(st.audio_id_alt,'')<>'')
  )
ORDER BY st.created_at DESC
LIMIT 25;
"
echo
echo '=== [2] WAV status distribution (web_music, last 30 days) ==='
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT wav_status_ok  AS status_ok,  count(*) AS n
FROM suno_tasks
WHERE source='web_music' AND status='success'
  AND created_at > now() - interval '30 days'
GROUP BY 1 ORDER BY 2 DESC;
"
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT wav_status_alt AS status_alt, count(*) AS n
FROM suno_tasks
WHERE source='web_music' AND status='success'
  AND created_at > now() - interval '30 days'
GROUP BY 1 ORDER BY 2 DESC;
"
echo
echo '=== [3] Log source sanity check ==='
systemctl is-active camxora-api
journalctl -u camxora-api -n 3 --no-pager 2>&1 | tail -5
echo
echo '=== [4] Log lines for the current failing task d587f6d5 (last 6 days) ==='
journalctl -u camxora-api --since '6 days ago' --no-pager 2>/dev/null \
  | grep -i 'd587f6d5' | tail -40
echo
echo '=== [5] All WAV-related API log lines (last 6 days) ==='
journalctl -u camxora-api --since '6 days ago' --no-pager 2>/dev/null \
  | grep -iE 'wav' | tail -60
echo
echo '=== [6] Backfill sweep alerts/iterations (last 6 days) ==='
journalctl -u camxora-api --since '6 days ago' --no-pager 2>/dev/null \
  | grep -iE 'backfill sweep' | tail -30
echo
echo '=== [7] WAV conversion logs from the upstream musicapi service (last 6 days) ==='
journalctl -u camxora-musicapi --since '6 days ago' --no-pager 2>/dev/null \
  | grep -iE 'wav|convert' | tail -80
echo
echo '=== [8] musicapi unit sanity check ==='
systemctl is-active camxora-musicapi 2>&1
journalctl -u camxora-musicapi -n 3 --no-pager 2>&1 | tail -5
echo
echo '=== [9] musicapi WAV conversion jobs for the current failing task ==='
sudo -u postgres psql -d sunoapi -P pager=off -c "
SELECT id, type, status,
       left(coalesce(error,''), 400) AS error,
       left(coalesce(result_json::text,''), 300) AS result_json,
       account_id, created_at
FROM jobs
WHERE id IN ('06b1897b-005e-44c6-bd0a-794712c59c2a',
             'fe7bd103-c05a-4e41-a629-436124511b02');
"
echo
echo '=== [10] Recent musicapi WAV job failures by error message (30 days) ==='
sudo -u postgres psql -d sunoapi -P pager=off -c "
SELECT coalesce(left(error,200),'(none)') AS error, count(*) AS n
FROM jobs
WHERE type = 'wav'
  AND status = 'error'
  AND created_at > now() - interval '30 days'
GROUP BY 1 ORDER BY 2 DESC LIMIT 15;
"
echo
echo '=== [11] Overall musicapi WAV job outcome (30 days) ==='
sudo -u postgres psql -d sunoapi -P pager=off -c "
SELECT status, count(*) AS n
FROM jobs
WHERE type = 'wav'
  AND created_at > now() - interval '30 days'
GROUP BY 1 ORDER BY 2 DESC;
"
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=120)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
