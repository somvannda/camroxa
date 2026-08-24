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
CMD = r"""
set -e
sudo -u camxora bash -lc 'cd /opt/camxora/repo && platform_api/.venv/bin/python - <<"PY"
from platform_api.models.domain import Plan
from platform_api.services.subscription_entitlement_service import (
    effective_daily_limit_for_operation,
    effective_monthly_limit_for_operation,
    resolve_effective_entitlements,
)
plan = Plan(
    id="00000000-0000-0000-0000-000000000001",
    name="Monthly - 2-channel",
    price_cents=7900,
    profile_allowance=2,
    is_active=True,
    monthly_song_limit=300,
    monthly_image_limit=1200,
    monthly_draft_limit=100000,
    monthly_video_limit=3000,
    monthly_merge_limit=3000,
    daily_song_limit_per_channel=999,
    daily_image_limit_per_channel=7,
    daily_draft_limit_per_channel=300,
    daily_video_limit=1000,
    daily_merge_limit=1000,
)
base = resolve_effective_entitlements(plan, addon_slots=0)
eight = resolve_effective_entitlements(plan, addon_slots=8)
print("songs", base.monthly_song_limit, eight.monthly_song_limit)
print("draft", base.monthly_draft_limit, eight.monthly_draft_limit)
print("image", base.monthly_image_limit, eight.monthly_image_limit)
print("video", base.monthly_video_limit, eight.monthly_video_limit)
print("merge", base.monthly_merge_limit, eight.monthly_merge_limit)
print("quota_channels", base.quota_channels, eight.quota_channels)
print("daily_video", effective_daily_limit_for_operation(plan, 0, "video"), effective_daily_limit_for_operation(plan, 8, "video"))
assert base.monthly_song_limit == eight.monthly_song_limit == 300
assert base.monthly_draft_limit == eight.monthly_draft_limit
assert base.monthly_image_limit == eight.monthly_image_limit
assert base.monthly_video_limit == eight.monthly_video_limit
assert base.monthly_merge_limit == eight.monthly_merge_limit
print("H04_H08_PASS")
PY'
echo REMOTE_DONE
"""
def main():
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit("bad host")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=60)
        print(stdout.read().decode("utf-8", "replace"))
        err=stderr.read().decode("utf-8","replace")
        if err.strip(): print(err)
    finally:
        client.close()
if __name__ == "__main__":
    raise SystemExit(main())
