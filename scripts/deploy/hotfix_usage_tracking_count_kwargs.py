#!/usr/bin/env python3
"""Deploy usage_tracking_repo count/include_monthly kwargs (Suno absorb spike fix)."""
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
UID = "2baeaae8-0121-4d98-872d-eff832237f46"

FILES = [
    "platform_api/repositories/usage_tracking_repo.py",
    "docs/changelog/2026-08-03-usage-tracking-count-kwargs.md",
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
    print(f"=== usage_tracking count kwargs -> {label} ({host}) ===")
    archive = Path(tempfile.mkdtemp(prefix=f"usage-count-{label}-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))
            print(f"Packed {rel}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote_tar = f"/tmp/usage-count-{label}.tar.gz"
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
            "systemctl try-restart camxora-worker-suno@1 camxora-worker-suno@2 "
            "camxora-worker-draft@1 camxora-worker-draft@2 "
            "camxora-worker-draft@3 camxora-worker-draft@4 "
            "camxora-worker-images@1 camxora-worker-images@2 2>/dev/null || true; "
            "sleep 4; "
            "systemctl is-active camxora-api; "
            "grep -n 'include_monthly' "
            "$REPO/platform_api/repositories/usage_tracking_repo.py | head -5; "
            "python3 - <<'PY'\n"
            "import inspect, sys\n"
            "sys.path.insert(0, '/opt/camxora/repo')\n"
            "from platform_api.repositories.usage_tracking_repo import UsageTrackingRepository\n"
            "sig = str(inspect.signature(UsageTrackingRepository.increment_usage))\n"
            "print('SIGNATURE', sig)\n"
            "assert 'count' in sig and 'include_monthly' in sig, sig\n"
            "print('SIGNATURE_OK')\n"
            "PY\n"
            # Clear fail-absorb for the known affected user on this host's redis via API env
            "cd $REPO; "
            "PYTHONPATH=$REPO $REPO/platform_api/.venv/bin/python - <<'PY'\n"
            "import asyncio, os\n"
            "from pathlib import Path\n"
            "UID = '2baeaae8-0121-4d98-872d-eff832237f46'\n"
            "for line in Path('platform_api/.env').read_text(encoding='utf-8', errors='replace').splitlines():\n"
            "    line=line.strip()\n"
            "    if not line or line.startswith('#') or '=' not in line: continue\n"
            "    k,_,v=line.partition('=')\n"
            "    os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))\n"
            "import redis.asyncio as redis\n"
            "async def main():\n"
            "    r = redis.from_url(os.environ['PLATFORM_REDIS_URL'], decode_responses=True)\n"
            "    keys=[]; cur=0\n"
            "    while True:\n"
            "        cur, batch = await r.scan(cursor=cur, match=f'fail_absorb:{UID}:*', count=50)\n"
            "        keys.extend(batch)\n"
            "        if cur==0: break\n"
            "    before={}\n"
            "    for k in keys:\n"
            "        before[k]=await r.get(k)\n"
            "        await r.delete(k)\n"
            "    print('ABSORB_CLEARED', before)\n"
            "    await r.aclose()\n"
            "asyncio.run(main())\n"
            "PY\n"
            f"echo {done_token}"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print("STDERR:", err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if done_token not in out:
            raise SystemExit(f"{label} deploy did not finish cleanly.")
        if "SIGNATURE_OK" not in out:
            raise SystemExit(f"{label} signature check failed.")
    finally:
        client.close()


def main() -> None:
    target = (sys.argv[1] if len(sys.argv) > 1 else "both").strip().lower()
    if target not in {"sandbox", "production", "both", "prod"}:
        raise SystemExit("Usage: hotfix_usage_tracking_count_kwargs.py [sandbox|production|both]")

    if target in {"sandbox", "both"}:
        env = load_env("secrets.sandbox.env")
        deploy(
            env.get("SANDBOX_VPS_HOST") or env["VPS_HOST"],
            env.get("SANDBOX_VPS_USER") or env["VPS_USER"],
            env.get("SANDBOX_VPS_PASSWORD") or env.get("VPS_PASSWORD"),
            "sandbox",
            "USAGE_COUNT_SANDBOX_DONE",
        )
    if target in {"production", "prod", "both"}:
        env = load_env("secrets.production.env")
        host = env.get("PRODUCTION_VPS_HOST") or env["VPS_HOST"]
        if host != PRODUCTION_HOST:
            raise SystemExit(f"Refusing non-production host: {host}")
        deploy(
            host,
            env.get("PRODUCTION_VPS_USER") or env["VPS_USER"],
            env.get("PRODUCTION_VPS_PASSWORD") or env.get("VPS_PASSWORD"),
            "production",
            "USAGE_COUNT_PRODUCTION_DONE",
        )


if __name__ == "__main__":
    main()
