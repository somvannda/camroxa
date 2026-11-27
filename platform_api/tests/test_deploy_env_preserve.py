"""Deploy guard: a missing secret must not blank a configured integration."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "deploy"
        / "env_preserve.py"
    )
    spec = importlib.util.spec_from_file_location("deploy_env_preserve", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


KEYS = ("PLATFORM_GOOGLE_CLIENT_ID", "PLATFORM_GOOGLE_CLIENT_SECRET")


def _env(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_empty_value_is_restored(tmp_path: Path) -> None:
    module = _load()
    previous = _env(
        tmp_path,
        "previous.env",
        "PLATFORM_GOOGLE_CLIENT_ID=client-123\n"
        "PLATFORM_GOOGLE_CLIENT_SECRET=secret-456\n",
    )
    current = _env(
        tmp_path,
        "current.env",
        "PLATFORM_PORT=8100\n"
        "PLATFORM_GOOGLE_CLIENT_ID=\n"
        "PLATFORM_GOOGLE_CLIENT_SECRET=\n",
    )
    assert module.preserve_missing(previous, current, KEYS) == list(KEYS)
    text = current.read_text(encoding="utf-8")
    assert "PLATFORM_GOOGLE_CLIENT_ID=client-123" in text
    assert "PLATFORM_GOOGLE_CLIENT_SECRET=secret-456" in text
    assert "PLATFORM_PORT=8100" in text


def test_supplied_value_wins(tmp_path: Path) -> None:
    module = _load()
    previous = _env(tmp_path, "previous.env", "PLATFORM_GOOGLE_CLIENT_ID=old\n")
    current = _env(tmp_path, "current.env", "PLATFORM_GOOGLE_CLIENT_ID=new-rotated\n")
    assert module.preserve_missing(previous, current, KEYS) == []
    assert "PLATFORM_GOOGLE_CLIENT_ID=new-rotated" in current.read_text(encoding="utf-8")


def test_missing_key_is_appended(tmp_path: Path) -> None:
    module = _load()
    previous = _env(
        tmp_path,
        "previous.env",
        "PLATFORM_GOOGLE_CLIENT_ID=client-123\n"
        "PLATFORM_GOOGLE_CLIENT_SECRET=secret-456\n",
    )
    current = _env(tmp_path, "current.env", "PLATFORM_PORT=8100\n")
    assert module.preserve_missing(previous, current, KEYS) == list(KEYS)
    text = current.read_text(encoding="utf-8")
    assert "PLATFORM_GOOGLE_CLIENT_ID=client-123" in text
    assert "PLATFORM_GOOGLE_CLIENT_SECRET=secret-456" in text


def test_first_install_without_previous_env_is_unchanged(tmp_path: Path) -> None:
    module = _load()
    previous = tmp_path / "missing.env"
    current = _env(tmp_path, "current.env", "PLATFORM_GOOGLE_CLIENT_ID=\n")
    assert module.preserve_missing(previous, current, KEYS) == []
    assert current.read_text(encoding="utf-8") == "PLATFORM_GOOGLE_CLIENT_ID=\n"


def test_other_keys_and_comments_are_untouched(tmp_path: Path) -> None:
    module = _load()
    previous = _env(
        tmp_path,
        "previous.env",
        "PLATFORM_SMTP_PASSWORD=\n"
        "# PLATFORM_GOOGLE_CLIENT_ID=commented-out\n"
    )
    current = _env(
        tmp_path,
        "current.env",
        "PLATFORM_SMTP_PASSWORD=\n"
        "# PLATFORM_GOOGLE_CLIENT_ID=commented-out\n",
    )
    assert module.preserve_missing(previous, current, KEYS) == []
    text = current.read_text(encoding="utf-8")
    assert "# PLATFORM_GOOGLE_CLIENT_ID=commented-out" in text


def test_remote_script_uses_the_guard_before_overwriting_env() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "deploy"
        / "camxora-production-remote.sh"
    ).read_text(encoding="utf-8")
    snapshot = script.index('cp -p "${REPO_DIR}/platform_api/.env" "${PREV_ENV}"')
    overwrite = script.index('sudo -u camxora tee "${REPO_DIR}/platform_api/.env"')
    guard = script.index("scripts/deploy/env_preserve.py")
    assert snapshot < overwrite < guard
    for key in (
        "PLATFORM_GOOGLE_CLIENT_ID",
        "PLATFORM_GOOGLE_CLIENT_SECRET",
        "PLATFORM_POSTFORME_API_KEY",
        "PLATFORM_POSTFORME_WEBHOOK_SECRET",
    ):
        assert key in script
