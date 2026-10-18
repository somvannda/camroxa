"""Selection logic for automatic missing-MP3 recovery (Progress auto path)."""

from __future__ import annotations

import pytest

from shared.lib.missing_mp3 import AutoMissingMp3Target, pick_auto_missing_mp3_target
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(
    *,
    batch_id: str = "batch-1",
    profile_id: str = "profile-1",
    role: str = "OK",
    run_dir: str = "F:/Suno/chan/2026-10-24_Album",
) -> ProgressRow:
    meta = ProgressRowMeta(
        batch_id=batch_id,
        profile_id=profile_id,
        role=role,
        run_dir=run_dir,
        expected=15,
        saved=0,
        download_ready=15,
        download_pending=15,
    )
    return ProgressRow(
        batch=batch_id,
        run_date="2026-10-24",
        channel="Demo",
        status="Preparing",
        music="0/15",
        image="—",
        converter="—",
        merge="—",
        youtube="—",
        stage="Music",
        notes="",
        updated="10:00:00",
        meta=meta,
    )


@pytest.fixture(autouse=True)
def _stable_run_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep run-dir resolution platform-independent; selection is what we test."""
    monkeypatch.setattr(
        "shared.lib.missing_mp3.resolve_row_local_run_dir",
        lambda row, local_suno_base=None: str(row.meta.run_dir or "").strip(),
    )


def test_picks_first_row_with_missing_tracks() -> None:
    rows = [_row(), _row(batch_id="batch-2", profile_id="profile-2")]
    # Only batch-2 reports a gap.
    target = pick_auto_missing_mp3_target(
        rows,
        attempted_at={},
        now=1000.0,
        cooldown_s=600.0,
        missing_counter=lambda row: 3 if row.meta.batch_id == "batch-2" else 0,
    )
    assert isinstance(target, AutoMissingMp3Target)
    assert target.batch_id == "batch-2"
    assert target.role == "OK"
    assert target.missing_n == 3
    assert target.key == ("batch-2", "profile-2", "OK")
    assert target.run_dir == "F:/Suno/chan/2026-10-24_Album"


def test_returns_none_when_nothing_missing() -> None:
    assert (
        pick_auto_missing_mp3_target(
            [_row()],
            attempted_at={},
            now=1000.0,
            cooldown_s=600.0,
            missing_counter=lambda row: 0,
        )
        is None
    )


def test_returns_none_for_empty_rows() -> None:
    assert (
        pick_auto_missing_mp3_target(
            [],
            attempted_at={},
            now=1000.0,
            cooldown_s=600.0,
            missing_counter=lambda row: 5,
        )
        is None
    )


def test_cooldown_skips_recent_attempt() -> None:
    row = _row()
    key = ("batch-1", "profile-1", "OK")
    # Attempted 60s ago with a 600s cooldown -> skipped.
    assert (
        pick_auto_missing_mp3_target(
            [row],
            attempted_at={key: 940.0},
            now=1000.0,
            cooldown_s=600.0,
            missing_counter=lambda r: 4,
        )
        is None
    )
    # Attempted 700s ago -> allowed again.
    target = pick_auto_missing_mp3_target(
        [row],
        attempted_at={key: 300.0},
        now=1000.0,
        cooldown_s=600.0,
        missing_counter=lambda r: 4,
    )
    assert target is not None and target.missing_n == 4


def test_cooldown_is_per_channel() -> None:
    rows = [_row(batch_id="batch-1"), _row(batch_id="batch-2")]
    target = pick_auto_missing_mp3_target(
        rows,
        attempted_at={("batch-1", "profile-1", "OK"): 990.0},
        now=1000.0,
        cooldown_s=600.0,
        missing_counter=lambda r: 2,
    )
    assert target is not None and target.batch_id == "batch-2"


def test_skips_rows_without_ids_and_other_types() -> None:
    rows: list[object] = [
        {"not": "a row"},
        _row(batch_id="", profile_id="profile-1"),
        _row(batch_id="batch-1", profile_id=""),
        _row(batch_id="batch-ok", profile_id="profile-ok"),
    ]
    target = pick_auto_missing_mp3_target(
        rows,  # type: ignore[arg-type]
        attempted_at={},
        now=1000.0,
        cooldown_s=600.0,
        missing_counter=lambda r: 1,
    )
    assert target is not None and target.batch_id == "batch-ok"


def test_dedupes_repeated_channel_key() -> None:
    calls: list[str] = []

    def _counter(row: ProgressRow) -> int:
        calls.append(str(row.meta.batch_id))
        return 0

    pick_auto_missing_mp3_target(
        [_row(), _row(), _row()],
        attempted_at={},
        now=1000.0,
        cooldown_s=600.0,
        missing_counter=_counter,
    )
    # Same (batch, profile, role) must only be counted once.
    assert calls == ["batch-1"]


def test_role_defaults_and_normalizes() -> None:
    row = _row(role=" alt ")
    target = pick_auto_missing_mp3_target(
        [row],
        attempted_at={},
        now=1000.0,
        cooldown_s=600.0,
        missing_counter=lambda r: 1,
    )
    assert target is not None and target.role == "ALT"


def test_skips_when_run_dir_unresolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.lib.missing_mp3.resolve_row_local_run_dir",
        lambda row, local_suno_base=None: "",
    )
    assert (
        pick_auto_missing_mp3_target(
            [_row()],
            attempted_at={},
            now=1000.0,
            cooldown_s=600.0,
            missing_counter=lambda r: 3,
        )
        is None
    )
