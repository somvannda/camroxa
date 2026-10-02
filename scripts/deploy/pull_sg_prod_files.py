#!/usr/bin/env python3
"""Read-only: download live prod files needed for the signup-domain-guard admin UI hotfix.

Files land under scripts/deploy/_sg_stage/ (gitignored scratch) so edits can be
built against the REAL production tree, not the main branch (provenance rule).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

REMOTE_FILES = {
    "platform_api/routers/admin.py": "_sg_stage/admin.prod.py",
    "platform_api/services/generation_freeze.py": "_sg_stage/generation_freeze.prod.py",
    "admin_portal/src/pages/settings/index.tsx": "_sg_stage/settings-index.prod.tsx",
    "admin_portal/src/hooks/use-settings.ts": "_sg_stage/use-settings.prod.ts",
    "admin_portal/src/hooks/use-suno-blocklist.ts": "_sg_stage/use-suno-blocklist.prod.ts",
    "admin_portal/src/types/suno-blocklist.ts": "_sg_stage/suno-blocklist-types.prod.ts",
}


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    stage = Path(__file__).resolve().parent / "_sg_stage"
    stage.mkdir(exist_ok=True)

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for remote_rel, local_name in REMOTE_FILES.items():
            remote = f"/opt/camxora/repo/{remote_rel}"
            local = stage / Path(local_name).name
            try:
                # Some SFTP servers reject a leading "/" for get(); retry relative.
                try:
                    sftp.get(remote, str(local))
                except FileNotFoundError:
                    sftp.get(remote.lstrip("/"), str(local))
                print(f"ok   {remote} -> {local_name}")
            except Exception as exc:  # noqa: BLE001
                # Last resort: read bytes through the sftp file handle.
                try:
                    with sftp.open(remote, "rb") as fh:
                        local.write_bytes(fh.read())
                    print(f"ok(r) {remote} -> {local_name}")
                except Exception as exc2:  # noqa: BLE001
                    print(f"MISS {remote}: {exc} | {exc2}")
        sftp.close()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
