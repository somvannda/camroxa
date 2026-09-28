#!/usr/bin/env python3
"""Production: dump every user wallet before/after a credits cutover.

DO NOT RUN until the user explicitly asks for a production cutover snapshot.

  python scripts/deploy/run_credits_cutover_snapshot_production.py --i-mean-production --phase before
  python scripts/deploy/run_credits_cutover_snapshot_production.py --i-mean-production --phase after
  python scripts/deploy/run_credits_cutover_snapshot_production.py --i-mean-production --phase diff
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST_CANDIDATES = (
    ROOT,
    Path(r"G:\Developments\Projects\Camxora\MusicGenerator"),
)
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from _credits_cutover_snapshot import diff_csv  # noqa: E402
from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_PY = DEPLOY / "_credits_cutover_snapshot.py"
OUT_DIR = DEPLOY / "out"


def _phase() -> str:
    if "--phase" in sys.argv:
        idx = sys.argv.index("--phase")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1].strip().lower()
    return ""


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Usage:\n"
            "  python scripts/deploy/run_credits_cutover_snapshot_production.py --i-mean-production --phase before\n"
            "  python scripts/deploy/run_credits_cutover_snapshot_production.py --i-mean-production --phase after\n"
            "  python scripts/deploy/run_credits_cutover_snapshot_production.py --i-mean-production --phase diff\n"
            "Refusing to run. This reads every production wallet."
        )
        return 2

    phase = _phase()
    if phase not in {"before", "after", "diff"}:
        print("Need --phase before|after|diff")
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before_local = OUT_DIR / "credits-snapshot-production-before.csv"
    after_local = OUT_DIR / "credits-snapshot-production-after.csv"
    if phase == "diff":
        if not before_local.is_file() or not after_local.is_file():
            raise SystemExit(f"Need {before_local} and {after_local}.")
        return diff_csv(before_local, after_local)

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    remote_csv = f"/tmp/credits-snapshot-{phase}.csv"
    local_csv = OUT_DIR / f"credits-snapshot-production-{phase}.csv"
    print(f"Target production host: {host} phase={phase}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/credits_cutover_snapshot.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        cmd = (
            "if ! ip -4 addr | grep -q '82.197.71.248'; then echo Refusing non-production host; exit 1; fi; "
            "python3 /tmp/credits_cutover_snapshot.py dump " + remote_csv
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=180)
        sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            sys.stderr.write(err[:2000] + "\n")
        status = stdout.channel.recv_exit_status()
        if status != 0:
            return status
        sftp = client.open_sftp()
        sftp.get(remote_csv, str(local_csv))
        sftp.close()
        print(f"SAVED {local_csv}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
