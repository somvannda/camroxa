#!/usr/bin/env python3
"""Sandbox: priority fix + stage multi-workers (draft/suno/images x2)."""
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
    "platform_api/repositories/job_queue_repo.py",
    "platform_api/worker.py",
    "platform_api/routers/batch.py",
    "platform_api/routers/image_jobs.py",
    "platform_api/routers/youtube.py",
    "platform_api/routers/callbacks.py",
    "platform_api/routers/generation.py",
    "platform_api/services/batch_service.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-02-api-phase1c-stage-workers.md",
    "scripts/deploy/systemd/camxora-worker-draft@.service",
    "scripts/deploy/systemd/camxora-worker-suno@.service",
    "scripts/deploy/systemd/camxora-worker-images@.service",
]

SANDBOX_HOST = "46.250.235.83"

REMOTE_INSTALL = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/phase1c-api.tar.gz -C $REPO
chown -R camxora:camxora $REPO/platform_api $REPO/docs/changelog $REPO/scripts/deploy/systemd

install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-draft@.service /etc/systemd/system/camxora-worker-draft@.service
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-suno@.service /etc/systemd/system/camxora-worker-suno@.service
install -m 644 $REPO/scripts/deploy/systemd/camxora-worker-images@.service /etc/systemd/system/camxora-worker-images@.service
systemctl daemon-reload

# Retire monolithic worker if present
systemctl disable --now camxora-worker.service 2>/dev/null || true

systemctl enable --now \
  camxora-worker-draft@{1..4}.service \
  camxora-worker-suno@{1..2}.service \
  camxora-worker-images@{1..2}.service

systemctl disable --now \
  camxora-worker-draft@{5..8}.service \
  camxora-worker-suno@{3..8}.service \
  camxora-worker-images@{3..8}.service 2>/dev/null || true

systemctl restart camxora-api
sleep 3

# Raise priority on already-queued starvation-prone jobs
sudo -u postgres psql -d camxora_platform -c "UPDATE job_queue SET priority=25, updated_at=NOW() WHERE job_type='execute_batch' AND status IN ('queued','delayed') AND priority < 25;"
sudo -u postgres psql -d camxora_platform -c "UPDATE job_queue SET priority=12, updated_at=NOW() WHERE job_type='run_image_jobs' AND status IN ('queued','delayed') AND priority < 12;"

echo === WORKERS ===
systemctl is-active camxora-api
systemctl is-active camxora-worker-draft@{1..4}
systemctl is-active camxora-worker-suno@{1..2}
systemctl is-active camxora-worker-images@{1..2}
echo --- extras should be inactive ---
systemctl is-active camxora-worker-draft@{5..6} 2>/dev/null || true
systemctl is-active camxora-worker-suno@3 2>/dev/null || true
systemctl is-active camxora-worker-images@3 2>/dev/null || true
ps -eo pid,cmd | grep 'platform_api.worker' | grep -v grep | wc -l
ps -eo pid,cmd | grep 'platform_api.worker' | grep -v grep || true
journalctl -u 'camxora-worker-draft@1' -n 5 --no-pager --no-hostname
echo PHASE1C_SANDBOX_DONE
"""


def load_sandbox() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.sandbox.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="phase1c-sbx-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/phase1c-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_INSTALL, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
