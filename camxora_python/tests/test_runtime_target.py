"""Tests for `python main.py local|sandbox` runtime target selection."""

from __future__ import annotations

import pytest

from shared.services import runtime_target as rt


@pytest.fixture(autouse=True)
def _clear_target_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("CAMXORA_BUILD_ENV", "CAMXORA_API_BASE_URL", "CAMXORA_PORTAL_BASE_URL"):
        monkeypatch.delenv(key, raising=False)


def test_consume_positional_sandbox() -> None:
    target, remaining = rt.consume_runtime_target_argv(["sandbox", "--foo"])
    assert target == "sandbox"
    assert remaining == ["--foo"]


def test_consume_env_flag() -> None:
    target, remaining = rt.consume_runtime_target_argv(["--env", "local"])
    assert target == "local"
    assert remaining == []
    target, remaining = rt.consume_runtime_target_argv(["--env=production"])
    assert target == "production"
    assert remaining == []


def test_apply_sandbox_sets_api(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    (tmp_path / ".env.sandbox").write_text(
        "CAMXORA_BUILD_ENV=sandbox\n"
        "CAMXORA_API_BASE_URL=https://api.sandbox.camxora.com/api/v1\n"
        "CAMXORA_PORTAL_BASE_URL=https://app.sandbox.camxora.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rt, "_module_root", lambda: tmp_path)
    assert rt.apply_runtime_target("sandbox") == "sandbox"
    assert rt.os.environ["CAMXORA_BUILD_ENV"] == "sandbox"
    assert "sandbox.camxora.com" in rt.os.environ["CAMXORA_API_BASE_URL"]


def test_apply_local_sets_localhost() -> None:
    assert rt.apply_runtime_target("local") == "local"
    assert rt.os.environ["CAMXORA_BUILD_ENV"] == "development"
    assert "localhost:8000" in rt.os.environ["CAMXORA_API_BASE_URL"]


def test_unknown_target_raises() -> None:
    with pytest.raises(ValueError, match="Unknown runtime target"):
        rt.apply_runtime_target("staging")
