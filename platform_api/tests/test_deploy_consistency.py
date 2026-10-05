"""Deploy consistency guard: migration-head and revision parsing."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[2] / "scripts" / "deploy" / "consistency.py"
    spec = importlib.util.spec_from_file_location("deploy_consistency", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_local_heads_single_chain() -> None:
    module = _load()
    revisions = {"a": set(), "b": {"a"}, "c": {"b"}}
    assert module.local_heads(revisions) == {"c"}


def test_local_heads_multiple() -> None:
    module = _load()
    revisions = {"a": set(), "b": {"a"}, "c": {"a"}}
    assert module.local_heads(revisions) == {"b", "c"}


def test_parse_down_revision_string() -> None:
    module = _load()
    assert module._parse_down_revisions('down_revision = "abc"') == {"abc"}


def test_parse_down_revision_tuple() -> None:
    module = _load()
    assert module._parse_down_revisions('down_revision = ("a", "b")') == {"a", "b"}


def test_parse_down_revision_none() -> None:
    module = _load()
    assert module._parse_down_revisions("down_revision = None") == set()


class _FakeStdout:
    def __init__(self, value: str) -> None:
        self._value = value

    def read(self) -> bytes:
        return self._value.encode()


class _FakeClient:
    def __init__(self, revision: str) -> None:
        self._revision = revision

    def exec_command(self, _cmd: str):
        return (None, _FakeStdout(self._revision), None)


def test_check_refuses_when_db_revision_unknown(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "local_revision_map", lambda: {"130_x": {"129"}})
    try:
        module.check_consistency(_FakeClient("133_credit_grant_claims"))
    except SystemExit:
        return
    raise AssertionError("expected SystemExit for unknown DB revision")


def test_check_passes_when_db_revision_present(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "local_revision_map", lambda: {"133_x": {"130"}})
    module.check_consistency(_FakeClient("133_x"))


def test_check_refuses_multiple_heads(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(
        module, "local_revision_map", lambda: {"a": set(), "b": {"a"}, "c": {"a"}}
    )
    try:
        module.check_consistency(_FakeClient("a"))
    except SystemExit:
        return
    raise AssertionError("expected SystemExit for multiple heads")


def test_check_allows_uninitialised_db(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "local_revision_map", lambda: {"133_x": {"130"}})
    module.check_consistency(_FakeClient(""))
