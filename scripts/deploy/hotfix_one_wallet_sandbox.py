"""Sandbox-only: one-wallet fulfill + leftover APIs + v3-only generate/UI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (
    ROOT,
    Path(r"G:\Developments\Projects\Camxora\MusicGenerator"),
)
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/services/v3/period_grant_service.py",
    "platform_api/services/v3/store.py",
    "platform_api/services/v3/wallet_sync.py",
    "platform_api/services/v3/web_ledger_conversion.py",
    "platform_api/services/v3/web_music_charge.py",
    "platform_api/services/v3/__init__.py",
    "platform_api/services/v2/subscription_service.py",
    "platform_api/services/v2/topup_service.py",
    "platform_api/services/usage_transaction_labels.py",
    "platform_api/routers/v3_billing.py",
    "platform_api/dependencies.py",
    "platform_api/CHANGELOG.md",
    "music_web/src/lib/subscription-api.ts",
    "music_web/CHANGELOG.md",
    "docs/changelog/2026-08-23-one-wallet-web-ledger.md",
    "docs/credits-only-plan-unification.md",
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
        for rel in FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as handle:
                handle.write(local.read_bytes().replace(b"\r\n", b"\n"))
            print(f"uploaded {rel}")
        sftp.close()
        cmd = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing production host
  exit 1
fi
python3 -m py_compile \
  /opt/camxora/repo/platform_api/services/v3/wallet_sync.py \
  /opt/camxora/repo/platform_api/services/v3/web_ledger_conversion.py \
  /opt/camxora/repo/platform_api/services/v3/web_music_charge.py \
  /opt/camxora/repo/platform_api/services/v3/period_grant_service.py \
  /opt/camxora/repo/platform_api/routers/v3_billing.py \
  /opt/camxora/repo/platform_api/dependencies.py
systemctl restart camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
if systemctl list-unit-files | grep -q '^camxora-music'; then
  systemctl restart camxora-music || true
fi
sleep 4
systemctl is-active camxora-api
grep -n "web-ledger\|_charge_v3\|sync_subscription_grant\|fetchCreditBalance" \
  /opt/camxora/repo/platform_api/routers/v3_billing.py \
  /opt/camxora/repo/platform_api/services/v3/web_music_charge.py \
  /opt/camxora/repo/platform_api/services/v2/subscription_service.py \
  /opt/camxora/repo/music_web/src/lib/subscription-api.ts
echo ONE_WALLET_SANDBOX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "ONE_WALLET_SANDBOX_OK" not in out:
            raise SystemExit("Sandbox one-wallet hotfix did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
