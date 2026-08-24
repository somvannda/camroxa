from pathlib import Path
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"D:\Development\Projects\Electron\MusicGenerator-credits-only-api-v3")
DEPLOY = Path(r"D:\Development\Projects\Electron\MusicGenerator\scripts\deploy")
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))
from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect
secrets = load_sandbox_secrets()
host, user, password = resolve_sandbox_ssh(secrets)
client = ssh_connect(host, user, ensure_deploy_key(), password)
cmd = r"""cd /tmp && sudo -u postgres psql -d camxora_platform -A -F '|' -c "SELECT name, price_cents, monthly_credits, daily_credits, is_public, is_active FROM plans ORDER BY price_cents LIMIT 20;" """
_, stdout, stderr = client.exec_command(cmd, timeout=30)
print(stdout.read().decode("utf-8","replace"))
client.close()
