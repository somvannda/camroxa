"""Credit-cutover snapshot diff: leftover mint is expected, stacked daily grants are not."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[2] / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY))

from _credits_cutover_snapshot import diff_csv  # noqa: E402


HEADER = [
    "user_id",
    "email",
    "wallet_credits",
    "grant_remaining",
    "daily_remaining",
    "conversion_remaining",
    "pack_remaining",
    "admin_remaining",
    "daily_grant_txn_count",
    "daily_grant_credit_sum",
    "period_grant_credit_sum",
    "quota_conversion_credit_sum",
    "web_remaining_credit_sum",
    "pack_credit_sum",
    "debit_credit_sum",
    "leftover_packages_applied",
    "leftover_credits_applied",
]


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "email": "duke@test.com",
        "wallet_credits": "50.0000",
        "grant_remaining": "0",
        "daily_remaining": "50.0000",
        "conversion_remaining": "0",
        "pack_remaining": "0",
        "admin_remaining": "0",
        "daily_grant_txn_count": "1",
        "daily_grant_credit_sum": "50.0000",
        "period_grant_credit_sum": "0",
        "quota_conversion_credit_sum": "0",
        "web_remaining_credit_sum": "0",
        "pack_credit_sum": "0",
        "debit_credit_sum": "0",
        "leftover_packages_applied": "0",
        "leftover_credits_applied": "0",
    }
    base.update(overrides)
    return base


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)


def test_diff_ok_when_wallets_unchanged(tmp_path: Path) -> None:
    before = tmp_path / "before.csv"
    after = tmp_path / "after.csv"
    _write(before, [_row()])
    _write(after, [_row()])
    assert diff_csv(before, after) == 0


def test_diff_ok_when_leftover_conversion_matches_wallet(tmp_path: Path) -> None:
    before = tmp_path / "before.csv"
    after = tmp_path / "after.csv"
    _write(before, [_row(wallet_credits="0", daily_grant_credit_sum="0", daily_grant_txn_count="0")])
    _write(
        after,
        [
            _row(
                wallet_credits="2200.0000",
                quota_conversion_credit_sum="2200.0000",
                leftover_packages_applied="220",
                leftover_credits_applied="2200",
                daily_grant_credit_sum="0",
                daily_grant_txn_count="0",
                daily_remaining="0",
            )
        ],
    )
    assert diff_csv(before, after) == 0


def test_diff_fails_stacked_daily_grant(tmp_path: Path) -> None:
    before = tmp_path / "before.csv"
    after = tmp_path / "after.csv"
    _write(before, [_row(wallet_credits="0", daily_grant_credit_sum="0", daily_grant_txn_count="0")])
    _write(
        after,
        [
            _row(
                wallet_credits="4150.0000",
                daily_grant_credit_sum="4150.0000",
                daily_grant_txn_count="83",
            )
        ],
    )
    assert diff_csv(before, after) == 1
