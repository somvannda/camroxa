#!/usr/bin/env python3
"""Restore admin routes that regressed on sandbox/production.

Deploys path-scoped files so pipeline board, job-queue metrics,
provider-key balances wiring, and fail-absorb admin APIs are live again.
"""
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

SANDBOX_HOST = "46.250.235.83"
PRODUCTION_HOST = "82.197.71.248"

FILES = [
    "platform_api/main.py",
    "platform_api/wire_dependencies.py",
    "platform_api/dependencies.py",
    "platform_api/routers/users.py",
    "platform_api/routers/admin.py",
    "platform_api/routers/admin_pipeline.py",
    "platform_api/routers/batch.py",
    "platform_api/routers/youtube.py",
    "platform_api/routers/image_jobs.py",
    "platform_api/routers/generation.py",
    "platform_api/services/usage_enforcement_service.py",
    "platform_api/services/admin_pipeline_service.py",
    "platform_api/services/admin_pipeline_retry_costs.py",
    "platform_api/services/provider_key_balance_service.py",
    "platform_api/services/key_pool_service.py",
    "platform_api/services/request_latency.py",
    "platform_api/repositories/job_queue_repo.py",
    "platform_api/services/pipeline_board_notifications.py",
    "platform_api/services/pipeline_waive_retry_executor.py",
    "docs/changelog/2026-08-03-admin-routes-production-restore.md",
]


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def deploy(host: str, user: str, password: str | None, label: str, done_token: str) -> None:
    print(f"=== Admin routes restore -> {label} ({host}) ===")
    archive = Path(tempfile.mkdtemp(prefix=f"admin-routes-{label}-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                print(f"SKIP missing {rel}")
                continue
            tar.add(path, arcname=rel.replace("\\", "/"))
            print(f"Packed {rel}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote_tar = f"/tmp/admin-routes-restore-{label}.tar.gz"
        with sftp.file(remote_tar, "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            f"tar -xzf {remote_tar} -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api $REPO/docs/changelog 2>/dev/null || "
            "chown -R camxora:camxora $REPO/platform_api; "
            "systemctl restart camxora-api; "
            "systemctl try-restart camxora-worker 2>/dev/null || true; "
            "sleep 3; "
            "systemctl is-active camxora-api; "
            "python3 - <<'PY'\n"
            "import urllib.request, urllib.error, json\n"
            "def hit(path):\n"
            "  try:\n"
            "    with urllib.request.urlopen('http://127.0.0.1:8100'+path, timeout=20) as r:\n"
            "      return r.status, r.read()[:120].decode()\n"
            "  except urllib.error.HTTPError as e:\n"
            "    return e.code, e.read()[:160].decode()\n"
            "  except Exception as e:\n"
            "    return 0, str(e)\n"
            "checks=[\n"
            " '/api/v1/admin/job-queue/metrics',\n"
            " '/api/v1/admin/pipeline/board?limit=5&active_only=true',\n"
            " '/api/v1/admin/provider-key-balances',\n"
            " '/api/v1/users/2baeaae8-0121-4d98-872d-eff832237f46/fail-absorb',\n"
            "]\n"
            "for p in checks:\n"
            "  code, body = hit(p)\n"
            "  print(code, p, body.replace('\\n',' '))\n"
            "PY\n"
            "grep -n 'admin_pipeline' $REPO/platform_api/main.py | head -5; "
            "grep -n 'get_job_queue_repo' $REPO/platform_api/dependencies.py | head -5; "
            "grep -n 'fail-absorb' $REPO/platform_api/routers/users.py | head -5; "
            f"echo {done_token}"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print("STDERR:", err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if done_token not in out:
            raise SystemExit(f"{label} admin routes restore did not finish cleanly.")
    finally:
        client.close()


def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
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
            "ADMIN_ROUTES_SANDBOX_DONE",
        )
    if target in {"production", "prod", "both"}:
        prod = load_env("secrets.production.env")
        host = prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"]
        if host != PRODUCTION_HOST:
            raise SystemExit(f"Refusing non-production host: {host}")
        deploy(
            host,
            prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
            prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
            "production",
            "ADMIN_ROUTES_PRODUCTION_DONE",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
