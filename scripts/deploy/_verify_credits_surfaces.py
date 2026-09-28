import sys
from pathlib import Path
d = Path(r"G:\Developments\Projects\Camxora\MusicGenerator-credits-only-api-v3\scripts\deploy")
sys.path.insert(0, str(d / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(d))
from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect
s = load_sandbox_secrets()
h, u, p = resolve_sandbox_ssh(s)
assert h == "46.250.235.83"
c = ssh_connect(h, u, ensure_deploy_key(), p)
cmd = r"""
ls /opt/camxora/repo/admin_portal/dist/assets | grep -Ei 'credit|v3-plan|usage-label' || true
echo ---
grep -l CreditsOnlySection /opt/camxora/repo/admin_portal/dist/assets/* 2>/dev/null || true
echo ---FLAG---
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT key || '=' || value FROM system_settings WHERE key ILIKE '%credits_only%' OR key ILIKE '%v3_charge%';"
echo ---SRC---
test -f /opt/camxora/repo/admin_portal/src/pages/plans/credits-only-section.tsx && echo plans_section_ok
test -f /opt/camxora/repo/website/src/lib/credits-only-public.ts && echo website_lib_ok
test -f /opt/camxora/repo/user_portal/src/lib/credits-only-public.ts && echo portal_lib_ok
test -f /opt/camxora/repo/music_web/src/components/available-plans-grid.tsx && echo mw_grid_ok
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode())
c.close()
