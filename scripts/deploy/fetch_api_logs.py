#!/usr/bin/env python3
"""Fetch recent camxora-api journal lines."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    client = ssh_connect(
        load_secrets()["VPS_HOST"],
        load_secrets()["VPS_USER"],
        ensure_deploy_key(),
        None,
    )
    _, stdout, _ = client.exec_command("journalctl -u camxora-api -n 60 --no-pager")
    text = stdout.read().decode("utf-8", errors="replace")
    client.close()
    out = Path(__file__).resolve().parent / "api-journal.txt"
    out.write_text(text, encoding="utf-8")
    for line in text.splitlines()[-35:]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
