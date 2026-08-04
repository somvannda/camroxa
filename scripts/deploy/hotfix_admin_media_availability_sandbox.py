#!/usr/bin/env python3
"""File-scoped sandbox hotfix: admin media availability uses on-disk existence."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_sandbox_secrets,
    resolve_sandbox_ssh,
    ssh_connect,
)

ROOT = Path(__file__).resolve().parents[2]
REMOTE_REPO = "/opt/camxora/repo"

UPLOADS = (
    (
        ROOT / "platform_api" / "utils" / "__init__.py",
        f"{REMOTE_REPO}/platform_api/utils/__init__.py",
    ),
    (
        ROOT / "platform_api" / "utils" / "upload_paths.py",
        f"{REMOTE_REPO}/platform_api/utils/upload_paths.py",
    ),
    (
        ROOT / "platform_api" / "routers" / "media.py",
        f"{REMOTE_REPO}/platform_api/routers/media.py",
    ),
)

REMOTE_PATCH = r'''
set -e
REPO=/opt/camxora/repo
python3 - <<'PY'
from pathlib import Path

path = Path("/opt/camxora/repo/platform_api/routers/users.py")
text = path.read_text(encoding="utf-8")
old_avail = (
    "logo_available=bool(str(row.get(\"logo_path\") or \"\").strip()),\n"
    "                cover_count=len([x for x in cover_paths if str(x or \"\").strip()]),"
)
new_avail = (
    "logo_available=upload_path_exists(row.get(\"logo_path\")),\n"
    "                cover_count=len([x for x in cover_paths if upload_path_exists(x)]),"
)
import_line = "from platform_api.utils.upload_paths import upload_path_exists\n"
if "upload_path_exists" not in text:
    anchor = "from platform_api.services.credit_units import units_to_credits\n"
    if anchor not in text:
        raise SystemExit("ANCHOR_IMPORT_MISSING")
    text = text.replace(anchor, anchor + import_line, 1)
if old_avail not in text:
    if new_avail in text:
        print("USERS_ALREADY_PATCHED")
    else:
        raise SystemExit("AVAIL_BLOCK_MISSING")
else:
    text = text.replace(old_avail, new_avail, 1)
    path.write_text(text, encoding="utf-8")
    print("USERS_PATCHED")
PY
chown -R camxora:camxora $REPO/platform_api/utils $REPO/platform_api/routers/media.py $REPO/platform_api/routers/users.py
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api
curl -s -o /dev/null -w 'HEALTH_%{http_code}\n' --max-time 10 http://127.0.0.1:8100/health || true
# Verify helper import and users detail semantics without auth (import check only)
sudo -u camxora env PYTHONPATH=$REPO $REPO/platform_api/.venv/bin/python - <<'PY'
from platform_api.utils.upload_paths import upload_path_exists
print('IMPORT_OK', upload_path_exists('uploads/logos/missing.png') is False)
print(
    'BASS_DRIVE_LOGO',
    upload_path_exists('uploads/logos/b1bed705-14a7-4973-8c18-ab21c9c097b1/bass-drive-logo.png'),
)
print(
    'EXISTING_LOGO',
    upload_path_exists('uploads/logos/b1bed705-14a7-4973-8c18-ab21c9c097b1/thunder-bass-logo.png'),
)
PY
echo MEDIA_404_HOTFIX_DONE
'''


def main() -> int:
    for local, _remote in UPLOADS:
        if not local.is_file():
            print(f"Missing {local}")
            return 1

    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)

    sftp = client.open_sftp()
    try:
        try:
            sftp.stat(f"{REMOTE_REPO}/platform_api/utils")
        except OSError:
            sftp.mkdir(f"{REMOTE_REPO}/platform_api/utils")
        for local, remote in UPLOADS:
            print(f"Uploading {local.relative_to(ROOT)} -> {remote}")
            sftp.put(str(local), remote)
    finally:
        sftp.close()

    _, stdout, stderr = client.exec_command(REMOTE_PATCH, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err[:2000])
    client.close()
    return 0 if "MEDIA_404_HOTFIX_DONE" in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
