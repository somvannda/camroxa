#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy import ensure_deploy_key, load_secrets, ssh_connect

secrets = load_secrets()
client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
cmd = r"""
curl -sf http://127.0.0.1:8100/api/v1/auth/signup-mode; echo
curl -sf https://app.sandbox.camxora.com/api/v1/auth/signup-mode; echo
cat /etc/systemd/system/camxora-portal.service
"""
_, stdout, stderr = client.exec_command(cmd)
sys.stdout.buffer.write(stdout.read())
sys.stdout.buffer.write(stderr.read())
client.close()
