#!/usr/bin/env python3
"""Smoke-check enriched upload-jobs SQL on a host."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

HOSTS = {
    "sandbox": ("46.250.235.83", "secrets.sandbox.env"),
    "production": ("82.197.71.248", "secrets.production.env"),
}


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
    target = (sys.argv[1] if len(sys.argv) > 1 else "sandbox").strip().lower()
    expected, secrets_name = HOSTS[target]
    env = load_env(secrets_name)
    host = env.get("SANDBOX_VPS_HOST") or env.get("PRODUCTION_VPS_HOST") or env["VPS_HOST"]
    if host != expected:
        raise SystemExit(f"Refusing host {host}")
    client = ssh_connect(
        host,
        env.get("SANDBOX_VPS_USER") or env.get("PRODUCTION_VPS_USER") or env["VPS_USER"],
        ensure_deploy_key(),
        env.get("SANDBOX_VPS_PASSWORD") or env.get("PRODUCTION_VPS_PASSWORD") or env.get("VPS_PASSWORD"),
    )
    try:
        sql = (
            "SELECT j.kind, left(coalesce(u.email,''),30), left(coalesce(s.title, sa_cover.album_name, ''),40), "
            "left(j.batch_id::text,8), j.updated_at IS NOT NULL "
            "FROM stream_upload_jobs j "
            "LEFT JOIN users u ON u.id = j.user_id "
            "LEFT JOIN songs s ON s.id = j.song_id "
            "LEFT JOIN stream_albums sa_cover ON j.album_id IS NULL AND j.kind = 'cover' "
            "AND sa_cover.user_id = j.user_id AND sa_cover.batch_id = j.batch_id "
            "AND sa_cover.cover_storage_key IS NOT DISTINCT FROM j.storage_key "
            "ORDER BY j.created_at DESC LIMIT 5;"
        )
        cmd = f"sudo -u postgres psql -d camxora_platform -c \"{sql}\""
        _, stdout, stderr = client.exec_command(cmd, timeout=45)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
