#!/usr/bin/env python3
"""Phase 1: deploy job_queue + worker to production (migrate, unit, restart)."""
from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

FILES = [
    "platform_api/migrations/versions/080_job_queue.py",
    "platform_api/repositories/job_queue_repo.py",
    "platform_api/worker.py",
    "platform_api/routers/batch.py",
    "platform_api/dependencies.py",
    "platform_api/wire_dependencies.py",
    "platform_api/CHANGELOG.md",
]

PRODUCTION_HOST = "82.197.71.248"

WORKER_UNIT = r"""
[Unit]
Description=CamXora Platform Job Worker
After=network.target postgresql.service redis-server.service camxora-api.service
Wants=postgresql.service redis-server.service

[Service]
User=camxora
Group=camxora
WorkingDirectory=/opt/camxora/repo
Environment=PYTHONPATH=/opt/camxora/repo
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/opt/camxora/repo/platform_api/.env
ExecStart=/opt/camxora/repo/platform_api/.venv/bin/python -m platform_api.worker
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="phase1-prod-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/phase1-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        with sftp.file("/tmp/camxora-worker.service", "w") as remote:
            remote.write(WORKER_UNIT.lstrip())
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/phase1-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api; "
            "install -m 644 /tmp/camxora-worker.service /etc/systemd/system/camxora-worker.service; "
            "systemctl daemon-reload; "
            "systemctl restart camxora-api; "
            "sleep 8; "
            "systemctl is-active camxora-api; "
            "sudo -u postgres psql -d camxora_platform -tAc "
            "\"SELECT to_regclass('public.job_queue');\"; "
            "systemctl enable camxora-worker; "
            "systemctl restart camxora-worker; "
            "sleep 3; "
            "systemctl is-active camxora-worker; "
            "curl -sS -m 15 -o /dev/null -w 'health=%{http_code}\\n' http://127.0.0.1:8100/health || true; "
            "journalctl -u camxora-worker -n 25 --no-pager; "
            "echo PHASE1_PROD_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
