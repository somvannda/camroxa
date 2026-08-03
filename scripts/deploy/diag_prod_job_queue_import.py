#!/usr/bin/env python3
"""Check whether job-queue dependency modules exist on production."""
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


CMD = r"""
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import importlib, traceback
checks = [
  'platform_api.dependencies',
  'platform_api.services.request_latency',
  'platform_api.repositories.job_queue_repo',
  'platform_api.routers.admin_pipeline',
  'platform_api.services.admin_pipeline_service',
]
for name in checks:
    try:
        m = importlib.import_module(name)
        print('IMPORT_OK', name)
        if name.endswith('dependencies'):
            print(' has get_job_queue_repo', hasattr(m, 'get_job_queue_repo'))
            print(' has get_provider_key_balance_service', hasattr(m, 'get_provider_key_balance_service'))
    except Exception:
        print('IMPORT_FAIL', name)
        traceback.print_exc()

# invoke metrics path pieces
try:
    from platform_api.dependencies import get_job_queue_repo
    import asyncio
    async def main():
        repo = get_job_queue_repo()
        print('repo', type(repo))
        metrics = await repo.get_metrics()
        print('metrics', metrics)
    asyncio.run(main())
except Exception:
    print('METRICS_FAIL')
    traceback.print_exc()
PY
"""


def main() -> int:
    secrets = load_env("secrets.production.env")
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=90)
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii")[:4000], file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
