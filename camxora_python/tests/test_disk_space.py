from __future__ import annotations

from pathlib import Path

from shared.lib.disk_space import get_free_bytes, has_sufficient_free_space


def test_get_free_bytes_returns_value_for_existing_path(tmp_path: Path) -> None:
    free = get_free_bytes(str(tmp_path))
    assert free is not None
    assert free >= 0


def test_get_free_bytes_walks_up_to_existing_ancestor(tmp_path: Path) -> None:
    missing_child = tmp_path / "does" / "not" / "exist" / "yet"
    free = get_free_bytes(str(missing_child))
    assert free is not None
    assert free == get_free_bytes(str(tmp_path))


def test_get_free_bytes_returns_none_for_empty_path() -> None:
    assert get_free_bytes("") is None
    assert get_free_bytes(None) is None  # type: ignore[arg-type]


def test_has_sufficient_free_space_true_when_above_minimum(tmp_path: Path) -> None:
    assert has_sufficient_free_space(str(tmp_path), minimum_bytes=1) is True


def test_has_sufficient_free_space_false_when_drive_is_too_small(tmp_path: Path) -> None:
    # No real drive has this much free space, so this always fails the floor.
    huge_minimum = 10**18
    assert has_sufficient_free_space(str(tmp_path), minimum_bytes=huge_minimum) is False


def test_has_sufficient_free_space_treats_unknown_as_sufficient() -> None:
    # A path that can't be resolved to any existing ancestor (e.g. an
    # unreachable UNC share) must not block callers — only *known*-bad
    # drives should be steered away from.
    assert has_sufficient_free_space("") is True
