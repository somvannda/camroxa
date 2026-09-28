"""Run credits-only matrix smoke on SANDBOX only. No production. No apply."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (ROOT, Path(r"G:\Developments\Projects\Camxora\MusicGenerator"))
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))
from deploy import ensure_deploy_key, ssh_connect

SANDBOX_HOST = "46.250.235.83"

def load_sandbox():
    for root in HOST_CANDIDATES:
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.sandbox.env")
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data

def run(client, cmd, timeout=180):
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read()
    err = stderr.read()
    sys.stdout.buffer.write(out)
    if err.strip():
        sys.stderr.buffer.write(err[-2000:])
    return stdout.channel.recv_exit_status()

def main():
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print("Target sandbox host: 46.250.235.83")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        for local, remote in [
            (DEPLOY / "_credits_only_sandbox_api_smoke.py", "/tmp/credits_only_sandbox_api_smoke.py"),
            (DEPLOY / "_credits_only_sandbox_leftover_dryrun.py", "/tmp/credits_only_sandbox_leftover_dryrun.py"),
            (DEPLOY / "_matrix_charge_on.py", "/tmp/matrix_charge_on.py"),
        ]:
            if not local.exists():
                print("skip missing", local.name)
                continue
            data = local.read_bytes().replace(b"\r\n", b"\n")
            with sftp.file(remote, "wb") as handle:
                handle.write(data)
            print("uploaded", local.name)
        sftp.close()

        print("=== FLAG BEFORE ===")
        run(client, "sudo -u postgres psql -d camxora_platform -P pager=off -c \"SELECT key, value FROM system_settings WHERE key = 'credits_only_v3_charge'\"")

        print("=== SMOKE (flag expected off) ===")
        code = run(client, "sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/credits_only_sandbox_api_smoke.py'")
        print("SMOKE_EXIT", code)

        print("=== LEFTOVER DRYRUN ===")
        code2 = run(client, "sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/credits_only_sandbox_leftover_dryrun.py'")
        print("DRYRUN_EXIT", code2)

        print("=== TURN FLAG ON ===")
        run(client, "sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c \"INSERT INTO system_settings (key, value, value_type, updated_at) VALUES ('credits_only_v3_charge', 'true', 'boolean', NOW()) ON CONFLICT (key) DO UPDATE SET value = 'true', value_type = 'boolean', updated_at = NOW(); SELECT key, value FROM system_settings WHERE key = 'credits_only_v3_charge';\"")

        print("=== CHARGE-ON CASES ===")
        code3 = run(client, "sudo -u camxora bash -lc 'cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python /tmp/matrix_charge_on.py'")
        print("CHARGE_ON_EXIT", code3)

        print("=== TURN FLAG OFF (restore default) ===")
        run(client, "sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c \"INSERT INTO system_settings (key, value, value_type, updated_at) VALUES ('credits_only_v3_charge', 'false', 'boolean', NOW()) ON CONFLICT (key) DO UPDATE SET value = 'false', value_type = 'boolean', updated_at = NOW(); SELECT key, value FROM system_settings WHERE key = 'credits_only_v3_charge';\"")
        return 0
    finally:
        client.close()

if __name__ == "__main__":
    raise SystemExit(main())
