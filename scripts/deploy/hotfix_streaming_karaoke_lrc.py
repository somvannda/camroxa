#!/usr/bin/env python3
"""Deploy karaoke LRC retry fix + optional backfill (sandbox/production)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

API_FILES = [
    "platform_api/services/suno_audio_resolver.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-03-streaming-karaoke-lrc-retry.md",
]

SANDBOX_HOST = "46.250.235.83"
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


def deploy(host: str, user: str, password: str | None, label: str, *, backfill: int) -> None:
    print(f"=== Karaoke LRC hotfix → {label} ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in API_FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote_path = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote_path.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote_path, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        with sftp.file("/tmp/remote_backfill_stream_lrc.py", "wb") as rf:
            rf.write((DEPLOY / "remote_backfill_stream_lrc.py").read_bytes())
        sftp.close()

        cmd = (
            "set -e; "
            "chown camxora:camxora /opt/camxora/repo/platform_api/services/suno_audio_resolver.py "
            "/opt/camxora/repo/platform_api/services/streaming_upload_service.py; "
            "systemctl restart camxora-api; "
            "sleep 4; "
            "systemctl is-active camxora-api; "
            "grep -n 'attempts: int = 4\\|exhausted retries' "
            "/opt/camxora/repo/platform_api/services/suno_audio_resolver.py | head -5; "
            "echo KARAOKE_LRC_HOTFIX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)

        if backfill > 0:
            print(f"=== Backfilling up to {backfill} tracks on {label} ===")
            bf = (
                "set -a; . /opt/camxora/repo/platform_api/.env; set +a; "
                "cd /opt/camxora/repo && "
                f"PYTHONPATH=/opt/camxora/repo "
                f"/opt/camxora/repo/platform_api/.venv/bin/python "
                f"/tmp/remote_backfill_stream_lrc.py {backfill}"
            )
            _, stdout, stderr = client.exec_command(bf, timeout=max(180, backfill * 8))
            print(stdout.read().decode(errors="replace"))
            err = stderr.read().decode(errors="replace")
            if err.strip():
                print(err, file=sys.stderr)
    finally:
        client.close()


def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "sandbox").strip().lower()
    backfill = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    if target in {"sandbox", "both"}:
        sb = load_env("secrets.sandbox.env")
        host = sb.get("SANDBOX_VPS_HOST") or sb["VPS_HOST"]
        if host != SANDBOX_HOST:
            raise SystemExit(f"Refusing non-sandbox host: {host}")
        deploy(
            host,
            sb.get("SANDBOX_VPS_USER") or sb["VPS_USER"],
            sb.get("SANDBOX_VPS_PASSWORD") or sb.get("VPS_PASSWORD"),
            "sandbox",
            backfill=backfill,
        )
    if target in {"production", "prod", "both"}:
        pr = load_env("secrets.production.env")
        host = pr.get("PRODUCTION_VPS_HOST") or pr["VPS_HOST"]
        if host != PRODUCTION_HOST:
            raise SystemExit(f"Refusing non-production host: {host}")
        deploy(
            host,
            pr.get("PRODUCTION_VPS_USER") or pr["VPS_USER"],
            pr.get("PRODUCTION_VPS_PASSWORD") or pr.get("VPS_PASSWORD"),
            "production",
            backfill=backfill,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
