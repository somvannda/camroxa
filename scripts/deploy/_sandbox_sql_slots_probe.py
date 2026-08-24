#!/usr/bin/env python3
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
from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect
SANDBOX_HOST = "46.250.235.83"
SQL = r"""
set -e
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT left(u.email,40) email, l.status, l.profile_addon_slots, l.profile_addon_pending,
       p.monthly_song_limit, p.monthly_draft_limit, p.monthly_image_limit, p.monthly_video_limit, p.monthly_merge_limit,
       p.daily_song_limit_per_channel, p.daily_video_limit, p.daily_merge_limit
FROM licenses l
JOIN users u ON u.id=l.user_id
JOIN plans p ON p.id=l.plan_id;
"
echo SQL3_DONE
"""
def main():
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit("bad host")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(SQL, get_pty=True, timeout=60)
        print(stdout.read().decode("utf-8", "replace"))
    finally:
        client.close()
if __name__ == "__main__":
    raise SystemExit(main())
