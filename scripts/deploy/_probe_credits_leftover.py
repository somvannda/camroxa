from pathlib import Path
import json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"D:\Development\Projects\Electron\MusicGenerator-credits-only-api-v3")
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))
from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect
secrets = load_sandbox_secrets()
host, user, password = resolve_sandbox_ssh(secrets)
client = ssh_connect(host, user, ensure_deploy_key(), password)
cmd = r"""
curl -sS https://api.sandbox.camxora.com/api/v3/plans/public | python3 -c "import sys,json; d=json.load(sys.stdin); rows=d if isinstance(d,list) else d.get('plans',d.get('items',[]));
[print(p.get('name'), p.get('price_cents'), 'month', p.get('monthly_credits'), 'day', p.get('daily_credits'), 'lyric', p.get('lyric_credits') or p.get('amounts',{}).get('lyric') if isinstance(p.get('amounts'),dict) else p.get('lyric')) for p in rows]
"
echo '---sql---'
cd /tmp && sudo -u postgres psql -d camxora_platform -A -F '|' -c "SELECT id, email FROM users WHERE email ILIKE '%camxora%' OR email ILIKE '%somvannda%' OR email ILIKE '%duke%' ORDER BY created_at DESC LIMIT 8;"
"""
_, stdout, stderr = client.exec_command(cmd, timeout=40)
print(stdout.read().decode("utf-8","replace"))
err = stderr.read().decode("utf-8","replace")
if err.strip():
    print("ERR", err[:1500])
client.close()
