#!/usr/bin/env python3
"""Diff two credit-cutover snapshots (local files).

  python scripts/deploy/diff_credits_cutover_snapshots.py before.csv after.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY))

from _credits_cutover_snapshot import diff_csv  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/deploy/diff_credits_cutover_snapshots.py <before.csv> <after.csv>")
        return 2
    return diff_csv(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
