"""File-scoped sandbox deploy: Admin Plans credits form + flagged v3 generate."""

from __future__ import annotations

import sys
import tarfile
import tempfile
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
    "platform_api/config.py",
    "platform_api/services/usage_enforcement_service.py",
    "platform_api/services/v3/generate_charge.py",
    "platform_api/CHANGELOG.md",
    "admin_portal/src/types/v3-billing.ts",
    "admin_portal/src/hooks/use-v3-plans.ts",
    "admin_portal/src/pages/plans/credits-only-plan-fields.tsx",
    "admin_portal/src/pages/plans/credits-only-section.tsx",
    "admin_portal/CHANGELOG.md",
    "docs/changelog/2026-08-22-credits-only-admin-plans-and-generate-flag.md",
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

    archive = Path(tempfile.mkdtemp(prefix="v3-admin-sbx-")) / "slice.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/credits-only-admin.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()
        cmd = r"""
set -e
REPO=/opt/camxora/repo
tar -xzf /tmp/credits-only-admin.tar.gz -C $REPO
python3 - <<'PY'
from pathlib import Path
path = Path("/opt/camxora/repo/admin_portal/src/pages/plans/index.tsx")
text = path.read_text(encoding="utf-8")
changed = False
import_line = "import { CreditsOnlySection } from '@/pages/plans/credits-only-section';\n"
if "credits-only-section" not in text:
    needle = "import { MusicWebFreeCreditsSection } from '@/pages/plans/music-web-free-credits-section';\n"
    if needle not in text:
        raise SystemExit("sandbox Plans page is missing MusicWebFreeCreditsSection import")
    text = text.replace(needle, import_line + needle, 1)
    changed = True
if "<CreditsOnlySection />" not in text:
    needle = "      <MusicWebFreeCreditsSection />"
    if needle not in text:
        raise SystemExit("sandbox Plans page is missing MusicWebFreeCreditsSection")
    text = text.replace(needle, "      <CreditsOnlySection />\n\n" + needle, 1)
    changed = True
if changed:
    path.write_text(text, encoding="utf-8")
    print("patched admin Plans index.tsx")
else:
    print("admin Plans index.tsx already wired")
PY
chown -R camxora:camxora \
  $REPO/platform_api/config.py \
  $REPO/platform_api/services/usage_enforcement_service.py \
  $REPO/platform_api/services/v3/generate_charge.py \
  $REPO/platform_api/CHANGELOG.md \
  $REPO/admin_portal/src/types/v3-billing.ts \
  $REPO/admin_portal/src/hooks/use-v3-plans.ts \
  $REPO/admin_portal/src/pages/plans \
  $REPO/admin_portal/CHANGELOG.md \
  $REPO/docs/changelog/2026-08-22-credits-only-admin-plans-and-generate-flag.md
systemctl restart camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
sleep 3
systemctl is-active camxora-api
curl -sS -o /tmp/v3-plans.json -w '%{http_code}' https://api.sandbox.camxora.com/api/v3/plans/public || true
echo
grep -n "CreditsOnlySection\|credits_only_v3_charge" \
  $REPO/admin_portal/src/pages/plans/index.tsx \
  $REPO/admin_portal/src/pages/plans/credits-only-section.tsx | head
echo CREDITS_ONLY_ADMIN_PLANS_SANDBOX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
