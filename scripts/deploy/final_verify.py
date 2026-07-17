#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy import ensure_deploy_key, load_secrets, ssh_connect

secrets = load_secrets()
client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
cmd = r"""
echo '=== /invite redirect ==='
curl -sI https://app.sandbox.camxora.com/invite | grep -iE 'HTTP|location'
echo '=== /register page ==='
curl -sI https://app.sandbox.camxora.com/register | grep -iE 'HTTP|content-type'
echo '=== admin format-datetime bundle ==='
grep -l format-datetime /opt/camxora/repo/admin_portal/dist/assets/*.js | head -3
echo '=== portal env ==='
cat /opt/camxora/repo/user_portal/.env.production
echo '=== portal systemd env ==='
grep Environment /etc/systemd/system/camxora-portal.service
"""
_, stdout, stderr = client.exec_command(cmd)
sys.stdout.buffer.write(stdout.read())
sys.stdout.buffer.write(stderr.read())
client.close()
