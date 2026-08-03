#!/usr/bin/env python3
"""Check whether production streaming upload fetches LRC."""
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
echo === UPLOAD SERVICE LRC ===
grep -n 'fetch_timestamped_lrc\|looks_like_lrc\|suno_audio_id\|external_task_id' /opt/camxora/repo/platform_api/services/streaming_upload_service.py | head -40
echo === RESOLVER ===
grep -n 'get_timestamped_lyrics\|fetch_timestamped' /opt/camxora/repo/platform_api/services/suno_audio_resolver.py | head -20
echo === CLIENT ===
grep -n 'timestamped\|get_timestamped' /opt/camxora/repo/platform_api/services/suno_client.py /opt/camxora/repo/platform_api/**/*.py 2>/dev/null | head -30
echo === SAMPLE PACK PATHS ===
sudo -u postgres psql -d camxora_platform -c "SELECT category, count(*) AS packs, sum(asset_count) AS assets FROM image_sample_packs WHERE is_active GROUP BY 1;"
sudo -u postgres psql -d camxora_platform -c "SELECT kind, count(*) AS n, sum(used_count) AS uses, max(used_count) AS max_used, min(used_count) AS min_used FROM image_random_history GROUP BY 1 ORDER BY 1;"
sudo -u postgres psql -d camxora_platform -c "SELECT kind, left(value,80) AS value, used_count FROM image_random_history ORDER BY used_count DESC LIMIT 15;"
echo === VPS ASSET SAMPLE ===
sudo -u postgres psql -d camxora_platform -c "SELECT left(storage_path,80), asset_count, category, name FROM image_sample_packs WHERE is_active ORDER BY asset_count DESC LIMIT 8;"
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
