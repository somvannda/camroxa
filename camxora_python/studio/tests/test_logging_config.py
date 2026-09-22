import logging

import pytest

from studio.app import logging_config


@pytest.fixture(autouse=True)
def _reset_logging_config():
    logging_config._CONFIGURED = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    yield
    logging_config._CONFIGURED = False
    for handler in list(root.handlers):
        root.removeHandler(handler)


def test_setup_logging_defaults_to_debug_console_and_file(monkeypatch):
    monkeypatch.delenv("CAMXORA_LOG_LEVEL", raising=False)
    monkeypatch.delenv("CAMXORA_LOG_CONSOLE_LEVEL", raising=False)
    monkeypatch.delenv("CAMXORA_LOG_FILE_LEVEL", raising=False)

    path = logging_config.setup_logging()

    assert path == logging_config.LOG_FILE
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    levels = {type(h).__name__: h.level for h in root.handlers}
    assert levels["StreamHandler"] == logging.DEBUG
    assert levels["RotatingFileHandler"] == logging.DEBUG


def test_setup_logging_respects_env_overrides(monkeypatch):
    monkeypatch.setenv("CAMXORA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("CAMXORA_LOG_CONSOLE_LEVEL", "WARNING")

    logging_config.setup_logging()

    root = logging.getLogger()
    by_type = {type(h).__name__: h for h in root.handlers}
    assert by_type["StreamHandler"].level == logging.WARNING
    assert by_type["RotatingFileHandler"].level == logging.INFO
