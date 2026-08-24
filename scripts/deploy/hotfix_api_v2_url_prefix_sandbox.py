#!/usr/bin/env python3
"""File-scoped sandbox hotfix: un-nest web-music billing onto /api/v2.

Does not replace platform_api/ as a tree (sandbox has credits-only v3 mounts
in main.py / config.py that are not on origin/main).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
SIBLING_VENV = ROOT.parent / "MusicGenerator" / "scripts" / "deploy" / ".venv" / "Lib" / "site-packages"
for candidate in (DEPLOY / ".venv" / "Lib" / "site-packages", SIBLING_VENV):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

SANDBOX_HOST = "46.250.235.83"

UPLOAD_FILES = [
    "platform_api/http_paths.py",
    "platform_api/middleware/legacy_api_paths.py",
    "platform_api/middleware/rate_limit.py",
    "platform_api/middleware/audit.py",
    "platform_api/routers/v2_subscriptions.py",
    "platform_api/routers/v2_credits.py",
    "platform_api/routers/v2_topups.py",
    "music_web/src/lib/subscription-api.ts",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== API v2 URL prefix -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in UPLOAD_FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
python3 - <<'PY'
from pathlib import Path

cfg = Path("/opt/camxora/repo/platform_api/config.py")
text = cfg.read_text(encoding="utf-8")
if 'api_v2_prefix' not in text:
    needle = '    api_v1_prefix: str = "/api/v1"\n'
    if needle not in text:
        raise SystemExit("api_v1_prefix line not found in config.py")
    text = text.replace(
        needle,
        needle + '    api_v2_prefix: str = "/api/v2"\n',
        1,
    )
    cfg.write_text(text, encoding="utf-8")
    print("patched config.py api_v2_prefix")
else:
    print("config.py already has api_v2_prefix")

main = Path("/opt/camxora/repo/platform_api/main.py")
src = main.read_text(encoding="utf-8")
changed = False
if "LegacyNestedV2PathMiddleware" not in src:
    marker = "    app.add_middleware(MusicWebGeoMiddleware)\n"
    insert = (
        marker
        + "\n"
        + "    # Last added = first to run: rewrite /api/v1/v2 → /api/v2 before routing.\n"
        + "    from platform_api.middleware.legacy_api_paths import LegacyNestedV2PathMiddleware\n"
        + "\n"
        + "    app.add_middleware(LegacyNestedV2PathMiddleware)\n"
    )
    if marker not in src:
        raise SystemExit("MusicWebGeoMiddleware marker not found in main.py")
    src = src.replace(marker, insert, 1)
    changed = True
    print("patched main.py legacy rewrite middleware")
else:
    print("main.py already has legacy rewrite middleware")

old = "app.include_router(v2_subscriptions.router, prefix=settings.api_v1_prefix)"
new = "app.include_router(v2_subscriptions.router, prefix=settings.api_v2_prefix)"
if old in src:
    src = src.replace(old, new)
    src = src.replace(
        "app.include_router(v2_credits.router, prefix=settings.api_v1_prefix)",
        "app.include_router(v2_credits.router, prefix=settings.api_v2_prefix)",
    )
    src = src.replace(
        "app.include_router(v2_topups.router, prefix=settings.api_v1_prefix)",
        "app.include_router(v2_topups.router, prefix=settings.api_v2_prefix)",
    )
    changed = True
    print("patched main.py v2 routers onto api_v2_prefix")
elif new in src:
    print("main.py v2 routers already on api_v2_prefix")
else:
    raise SystemExit("v2 router include_router lines not found in main.py")

if changed:
    main.write_text(src, encoding="utf-8")
PY

chown camxora:camxora \
  $REPO/platform_api/http_paths.py \
  $REPO/platform_api/config.py \
  $REPO/platform_api/main.py \
  $REPO/platform_api/middleware/legacy_api_paths.py \
  $REPO/platform_api/middleware/rate_limit.py \
  $REPO/platform_api/middleware/audit.py \
  $REPO/platform_api/routers/v2_subscriptions.py \
  $REPO/platform_api/routers/v2_credits.py \
  $REPO/platform_api/routers/v2_topups.py \
  $REPO/music_web/src/lib/subscription-api.ts

grep -n "api_v2_prefix\|LegacyNestedV2PathMiddleware\|v2_subscriptions.router" \
  $REPO/platform_api/config.py $REPO/platform_api/main.py | head -40
grep -n "APIRouter(prefix=" \
  $REPO/platform_api/routers/v2_subscriptions.py \
  $REPO/platform_api/routers/v2_credits.py \
  $REPO/platform_api/routers/v2_topups.py

systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"

sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
echo URL_PREFIX_HOTFIX_DONE
"""
        _stdin, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
        code = stdout.channel.recv_exit_status()
        return int(code)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
