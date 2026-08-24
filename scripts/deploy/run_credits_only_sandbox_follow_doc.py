"""Sandbox: v1 public filter + catalog from the unification spec + v3 API smoke.

Does not touch production. Leaves credits_only_v3_charge Off.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (
    ROOT,
    Path(r"D:\Development\Projects\Electron\MusicGenerator"),
)
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
UPLOADS = [
    (ROOT / "platform_api/routers/plans.py", "/opt/camxora/repo/platform_api/routers/plans.py"),
    (ROOT / "platform_api/services/v3/store.py", "/opt/camxora/repo/platform_api/services/v3/store.py"),
    (ROOT / "platform_api/CHANGELOG.md", "/opt/camxora/repo/platform_api/CHANGELOG.md"),
    (
        ROOT / "docs/changelog/2026-08-22-v1-plans-public-is-public.md",
        "/opt/camxora/repo/docs/changelog/2026-08-22-v1-plans-public-is-public.md",
    ),
    (DEPLOY / "_credits_only_sandbox_catalog.sql", "/tmp/credits_only_sandbox_catalog.sql"),
    (DEPLOY / "_credits_only_sandbox_api_smoke.py", "/tmp/credits_only_sandbox_api_smoke.py"),
]


def load_sandbox() -> dict[str, str]:
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.sandbox.env")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        for local, remote in UPLOADS:
            data = local.read_bytes().replace(b"\r\n", b"\n")
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            with sftp.file(remote, "wb") as handle:
                handle.write(data)
            print(f"uploaded {local.name}")
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/platform_api/routers/plans.py $REPO/platform_api/services/v3/store.py $REPO/platform_api/CHANGELOG.md
sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -f /tmp/credits_only_sandbox_catalog.sql
echo '=== catalog snapshot ==='
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT name, price_cents, profile_allowance, monthly_song_limit, monthly_credits,
       daily_credits, is_active, is_public, plan_type, music_credits
FROM plans
ORDER BY is_public DESC, price_cents, name;
"
systemctl restart camxora-api
sleep 5
systemctl is-active camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/credits_only_sandbox_api_smoke.py'
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        sys.stdout.buffer.write(stdout.read())
        err = stderr.read()
        if err.strip():
            sys.stderr.buffer.write(err[-2000:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
