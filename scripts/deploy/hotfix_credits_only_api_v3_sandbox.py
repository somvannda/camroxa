"""File-scoped sandbox deploy for credits-only /api/v3. Does not touch production."""

from __future__ import annotations

import sys
import tarfile
import tempfile
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
FILES = [
    "platform_api/config.py",
    "platform_api/main.py",
    "platform_api/dependencies.py",
    "platform_api/CHANGELOG.md",
    "platform_api/routers/v3_billing.py",
    "platform_api/services/v3/__init__.py",
    "platform_api/services/v3/ops.py",
    "platform_api/services/v3/store.py",
    "platform_api/services/v3/credits_only_billing_service.py",
    "platform_api/services/v3/period_grant_service.py",
    "platform_api/services/v3/quota_conversion_service.py",
    "platform_api/migrations/versions/116_credits_only_v3.py",
    "docs/changelog/2026-08-22-credits-only-api-v3.md",
]


def _secrets_path() -> Path:
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            return path
    raise SystemExit("No .deploy/secrets.sandbox.env found")


def load_sandbox() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in _secrets_path().read_text(encoding="utf-8").splitlines():
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

    archive = Path(tempfile.mkdtemp(prefix="v3-sbx-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/credits-only-v3.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/credits-only-v3.tar.gz -C $REPO
chown -R camxora:camxora $REPO/platform_api $REPO/docs/changelog
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic current && alembic heads' || true
sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 <<'SQL'
ALTER TABLE plans
    ADD COLUMN IF NOT EXISTS daily_credits INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS lyric_credits INTEGER,
    ADD COLUMN IF NOT EXISTS title_credits INTEGER,
    ADD COLUMN IF NOT EXISTS album_credits INTEGER,
    ADD COLUMN IF NOT EXISTS music_credits INTEGER,
    ADD COLUMN IF NOT EXISTS style_credits INTEGER,
    ADD COLUMN IF NOT EXISTS image_credits INTEGER,
    ADD COLUMN IF NOT EXISTS video_credits INTEGER,
    ADD COLUMN IF NOT EXISTS merge_credits INTEGER;
CREATE TABLE IF NOT EXISTS credit_wallet_lots (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    amount_units BIGINT NOT NULL,
    remaining_units BIGINT NOT NULL,
    expires_at TIMESTAMPTZ,
    period_start DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT credit_wallet_lots_tag_check
        CHECK (tag IN ('grant', 'quota_conversion', 'pack', 'admin')),
    CONSTRAINT credit_wallet_lots_remaining_check
        CHECK (remaining_units >= 0 AND remaining_units <= amount_units)
);
CREATE INDEX IF NOT EXISTS idx_credit_wallet_lots_user
    ON credit_wallet_lots (user_id, tag, expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_wallet_lots_period_grant
    ON credit_wallet_lots (user_id, period_start)
    WHERE tag = 'grant' AND period_start IS NOT NULL;
CREATE TABLE IF NOT EXISTS billing_conversion_runs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES plans(id) ON DELETE SET NULL,
    leftover_packages INTEGER NOT NULL,
    credits_minted INTEGER NOT NULL,
    amount_units BIGINT NOT NULL,
    status TEXT NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT billing_conversion_runs_status_check
        CHECK (status IN ('dry_run', 'applied', 'skipped'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_conversion_applied_user
    ON billing_conversion_runs (user_id)
    WHERE status = 'applied';
SQL
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic stamp 116_credits_only_v3' || true
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
systemctl restart camxora-api
sleep 4
systemctl is-active camxora-api
curl -sS -o /tmp/v3-public.json -w '%{http_code}' https://api.sandbox.camxora.com/api/v3/plans/public || true
echo
curl -sS -o /tmp/v1-public.json -w '%{http_code}' https://api.sandbox.camxora.com/api/v1/plans/public || true
echo
python3 - <<'PY'
import json
from pathlib import Path
v3 = json.loads(Path("/tmp/v3-public.json").read_text() or "[]")
v1 = json.loads(Path("/tmp/v1-public.json").read_text() or "[]")
print("v3_public_rows", len(v3) if isinstance(v3, list) else type(v3).__name__)
print("v1_public_rows", len(v1) if isinstance(v1, list) else type(v1).__name__)
if isinstance(v1, list) and v1:
    keys = set(v1[0])
    print("v1_has_music_credits", "music_credits" in keys)
    print("v1_has_monthly_song_limit", "monthly_song_limit" in keys)
print("CREDITS_ONLY_V3_SANDBOX_DONE")
PY
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
