#!/usr/bin/env python3
"""Resize stage workers only (no code tarball) — draft×4 suno×2 images×2."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

RESIZE_CMD = r"""
set -e
systemctl enable --now \
  camxora-worker-draft@{1..4}.service \
  camxora-worker-suno@{1..2}.service \
  camxora-worker-images@{1..2}.service
systemctl disable --now \
  camxora-worker-draft@{5..8}.service \
  camxora-worker-suno@{3..8}.service \
  camxora-worker-images@{3..8}.service 2>/dev/null || true
sleep 2
echo === ACTIVE ===
systemctl is-active camxora-api
systemctl is-active camxora-worker-draft@{1..4}
systemctl is-active camxora-worker-suno@{1..2}
systemctl is-active camxora-worker-images@{1..2}
echo === SHOULD_BE_INACTIVE ===
systemctl is-active camxora-worker-draft@5 camxora-worker-draft@6 camxora-worker-suno@3 camxora-worker-images@3 2>/dev/null || true
echo worker_procs=$(ps -eo cmd | grep -c '[p]latform_api.worker' || true)
ps -eo pid,rss,cmd | grep '[p]latform_api.worker' || true
echo RESIZE_DONE
"""


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def resize(host: str, user: str, password: str | None, label: str) -> None:
    print(f"Resizing {label} ({host}) → draft×4 / suno×2 / images×2")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(RESIZE_CMD, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()


def main() -> int:
    sb = load_env("secrets.sandbox.env")
    resize(
        sb.get("SANDBOX_VPS_HOST") or sb["VPS_HOST"],
        sb.get("SANDBOX_VPS_USER") or sb["VPS_USER"],
        sb.get("SANDBOX_VPS_PASSWORD") or sb.get("VPS_PASSWORD"),
        "sandbox",
    )
    pr = load_env("secrets.production.env")
    host = pr.get("PRODUCTION_VPS_HOST") or pr["VPS_HOST"]
    if host != "82.197.71.248":
        raise SystemExit(f"Refusing non-production host: {host}")
    resize(
        host,
        pr.get("PRODUCTION_VPS_USER") or pr["VPS_USER"],
        pr.get("PRODUCTION_VPS_PASSWORD") or pr.get("VPS_PASSWORD"),
        "production",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
