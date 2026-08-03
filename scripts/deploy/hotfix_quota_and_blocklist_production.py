"""File-scoped production hotfix: secondary quota + Suno blocklist hyphen variants."""
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
    # Multi-channel daily song/draft attribution + quota display
    "platform_api/repositories/usage_tracking_repo.py",
    "platform_api/services/usage_enforcement_service.py",
    "platform_api/services/batch_service.py",
    "platform_api/services/quota_display_service.py",
    "platform_api/models/schemas.py",
    "platform_api/routers/credits.py",
    # Suno blocklist spaced/hyphen matching
    "platform_api/services/suno_lyrics_sanitize.py",
    "platform_api/CHANGELOG.md",
]

PRODUCTION_HOST = "82.197.71.248"


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(
        encoding="utf-8"
    ).splitlines():
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
    print("Files:")
    for rel in FILES:
        print(f"  - {rel}")

    archive = Path(tempfile.mkdtemp(prefix="quota-blocklist-prod-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/quota-blocklist-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        sftp.close()

        # Longer wait: workers run alembic on startup and hang requests until ready.
        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/quota-blocklist-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora "
            "$REPO/platform_api/repositories/usage_tracking_repo.py "
            "$REPO/platform_api/services/usage_enforcement_service.py "
            "$REPO/platform_api/services/batch_service.py "
            "$REPO/platform_api/services/quota_display_service.py "
            "$REPO/platform_api/services/suno_lyrics_sanitize.py "
            "$REPO/platform_api/models/schemas.py "
            "$REPO/platform_api/routers/credits.py "
            "$REPO/platform_api/CHANGELOG.md; "
            "systemctl restart camxora-api; "
            "echo waiting_for_api...; "
            "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do "
            "  if curl -sS -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health | grep -q 200; then "
            "    echo health_ok_attempt_$i; break; "
            "  fi; "
            "  sleep 3; "
            "done; "
            "systemctl is-active camxora-api; "
            "grep -n blocked_term_pattern "
            "$REPO/platform_api/services/suno_lyrics_sanitize.py | head -2; "
            "grep -n attribute_secondary_daily_usage "
            "$REPO/platform_api/services/usage_enforcement_service.py | head -2; "
            "curl -sS -m 10 -o /tmp/login.txt -w 'login=%{http_code} t=%{time_total}\\n' "
            "-X POST http://127.0.0.1:8100/api/v1/auth/login "
            "-H 'Content-Type: application/json' "
            "-d '{\"email\":\"x@y.com\",\"password\":\"badpass123\"}'; "
            "curl -sS -m 10 -o /dev/null -w 'pub_health=%{http_code} t=%{time_total}\\n' "
            "https://api.camxora.com/health; "
            "echo PROD_HOTFIX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR", err[-2000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
