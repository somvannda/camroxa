"""Central logging setup for the Platform API process."""

from __future__ import annotations

import logging

from platform_api.terminal_log import configure_terminal_logging

_API_LOGGERS = (
    "platform_api",
    "platform_api.music",
    "platform_api.credits",
    "platform_api.images",
    "platform_api.access",
    "platform_api.services",
    "platform_api.routers",
    "platform_api.clients",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
)


def configure_api_logging() -> None:
    """Ensure all platform_api logs appear immediately in the dev terminal.

    Re-asserts on every call instead of short-circuiting on a module flag:
    a logger can be disabled (or pushed above INFO) by a later re-configuration,
    which drops records silently. Keeping this idempotent makes a second call
    from a worker or a test a cheap repair rather than a no-op.
    """
    configure_terminal_logging()

    for name in _API_LOGGERS:
        logger = logging.getLogger(name)
        logger.disabled = False
        logger.setLevel(logging.INFO)

    root = logging.getLogger()
    root.disabled = False
    root.setLevel(logging.INFO)


def default_log_config_path() -> str:
    from pathlib import Path

    return str(Path(__file__).with_name("log_config.json"))
