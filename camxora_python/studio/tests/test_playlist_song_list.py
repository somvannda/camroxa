"""Tests for playlist song list row reorder logic."""

from __future__ import annotations


def _move_row(order: list[str], drag_row: int, insert_at: int) -> list[str] | None:
    """Pure-python mirror of move_table_row."""
    row_count = len(order)
    if drag_row < 0 or drag_row >= row_count:
        return None
    insert_at = max(0, min(insert_at, row_count))
    if insert_at > drag_row:
        new_row = insert_at - 1
    else:
        new_row = insert_at
    if new_row == drag_row:
        return None
    items = order[:]
    row = items.pop(drag_row)
    if insert_at > drag_row:
        insert_at -= 1
    insert_at = max(0, min(insert_at, len(items)))
    items.insert(insert_at, row)
    return items


def test_move_first_to_last() -> None:
    order = ["a", "b", "c", "d"]
    moved = _move_row(order, 0, 4)
    assert moved == ["b", "c", "d", "a"]


def test_move_last_to_first() -> None:
    order = ["a", "b", "c", "d"]
    moved = _move_row(order, 3, 0)
    assert moved == ["d", "a", "b", "c"]


def test_move_down_one() -> None:
    order = ["a", "b", "c", "d"]
    moved = _move_row(order, 0, 2)
    assert moved == ["b", "a", "c", "d"]


def test_move_up_one() -> None:
    order = ["a", "b", "c", "d"]
    moved = _move_row(order, 2, 1)
    assert moved == ["a", "c", "b", "d"]


def test_move_preserves_count() -> None:
    order = [f"s{i}" for i in range(10)]
    for drag in range(len(order)):
        for insert_at in range(len(order) + 1):
            moved = _move_row(order, drag, insert_at)
            if moved is None:
                continue
            assert len(moved) == len(order)
            assert sorted(moved) == sorted(order)


def test_no_op_same_slot() -> None:
    order = ["a", "b", "c"]
    assert _move_row(order, 1, 1) is None
    assert _move_row(order, 1, 2) is None
