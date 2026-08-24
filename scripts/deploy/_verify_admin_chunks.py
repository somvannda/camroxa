import sys
from pathlib import Path
d = Path(r"D:\Development\Projects\Electron\MusicGenerator-credits-only-api-v3\scripts\deploy")
sys.path.insert(0, str(d / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(d))
from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect
s = load_sandbox_secrets()
h, u, p = resolve_sandbox_ssh(s)
assert h == "46.250.235.83"
c = ssh_connect(h, u, ensure_deploy_key(), p)
cmd = r"""
ls /opt/camxora/repo/admin_portal/dist/assets | grep -Ei 'credits-only|plans-index|user-spent|finance|user-detail' || true
echo ---
python3 - <<'PY'
from pathlib import Path
root = Path('/opt/camxora/repo/admin_portal/dist/assets')
needles = (b'CreditsOnly', b'credits_only_v3', b'monthly_credits')
for p in root.glob('*.js'):
    data = p.read_bytes()
    hits = [n.decode() for n in needles if n in data]
    if hits:
        print(p.name, hits)
PY
"""
_, o, e = c.exec_command(cmd)
print(o.read().decode())
c.close()
