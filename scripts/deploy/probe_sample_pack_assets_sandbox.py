#!/usr/bin/env python3
"""Check sandbox image sample pack catalog and VPS asset counts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
sudo -u postgres psql -d camxora_platform -t -A -F'|' -c "SELECT category, name, COALESCE(asset_count,0), COALESCE(storage_path,'') FROM image_sample_packs ORDER BY category, name;"
echo ---
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT COUNT(1) FROM image_sample_pack_assets;"
echo ---
find /opt/camxora/data/sample-pack-storage -type f 2>/dev/null | wc -l
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
