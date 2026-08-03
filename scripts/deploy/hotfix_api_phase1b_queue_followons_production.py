#!/usr/bin/env python3
"""Phase 1b: file-scoped production hotfix (API + worker). Run only when explicitly asked."""
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
    "platform_api/services/job_types.py",
    "platform_api/services/request_latency.py",
    "platform_api/repositories/job_queue_repo.py",
    "platform_api/worker.py",
    "platform_api/services/batch_service.py",
    "platform_api/routers/image_jobs.py",
    "platform_api/routers/youtube.py",
    "platform_api/routers/callbacks.py",
    "platform_api/routers/generation.py",
    "platform_api/routers/admin.py",
    "platform_api/middleware/request_log.py",
    "platform_api/wire_dependencies.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-02-api-phase1b-queue-followons.md",
]

PRODUCTION_HOST = "82.197.71.248"


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
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

    archive = Path(tempfile.mkdtemp(prefix="phase1b-prod-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/phase1b-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/phase1b-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api $REPO/docs/changelog; "
            "systemctl restart camxora-api; "
            "systemctl restart camxora-worker; "
            "sleep 5; "
            "systemctl is-active camxora-api; "
            "systemctl is-active camxora-worker; "
            "journalctl -u camxora-worker -n 25 --no-pager; "
            "echo PHASE1B_PRODUCTION_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
