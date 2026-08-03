#!/usr/bin/env python3
"""Inspect production streaming upload-jobs UI vs DB (fast)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
OUT = ROOT / "tmp" / "prod-upload-jobs.tsx"


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
        cmd = (
            "sudo -u postgres psql -d camxora_platform -tAc "
            "\"SELECT kind, count(*), count(user_id), count(song_id), count(batch_id), count(album_id) "
            "FROM stream_upload_jobs GROUP BY kind ORDER BY 1;\"; "
            "echo '---SAMPLE---'; "
            "sudo -u postgres psql -d camxora_platform -tAc "
            "\"SELECT kind||'|'||status||'|u='||(user_id IS NOT NULL)||'|s='||(song_id IS NOT NULL)"
            "||'|b='||(batch_id IS NOT NULL)||'|a='||(album_id IS NOT NULL)||'|'||left(coalesce(storage_key,''),50) "
            "FROM stream_upload_jobs ORDER BY created_at DESC LIMIT 6;\"; "
            "echo '---API---'; "
            "sed -n '106,125p' /opt/camxora/repo/platform_api/routers/streaming_admin.py; "
            "echo '---LIST---'; "
            "sed -n '304,330p' /opt/camxora/repo/platform_api/routers/streaming_admin.py"
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=45)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err)

        OUT.parent.mkdir(parents=True, exist_ok=True)
        sftp = client.open_sftp()
        with sftp.file("/opt/camxora/repo/admin_portal/src/pages/streaming/upload-jobs.tsx", "rb") as rf:
            OUT.write_bytes(rf.read())
        # also hook + types if any
        for remote, local_name in (
            ("/opt/camxora/repo/admin_portal/src/hooks/use-streaming.ts", "prod-use-streaming.ts"),
            ("/opt/camxora/repo/platform_api/routers/streaming_admin.py", "prod-streaming_admin.py"),
        ):
            try:
                with sftp.file(remote, "rb") as rf:
                    (ROOT / "tmp" / local_name).write_bytes(rf.read())
                print(f"saved {local_name}")
            except OSError as exc:
                print(f"skip {local_name}: {exc}")
        sftp.close()
        print(f"saved UI to {OUT} ({OUT.stat().st_size} bytes)")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
