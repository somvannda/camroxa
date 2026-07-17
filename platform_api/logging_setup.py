"""Central logging setup for the Platform API process."""

from __future__ import annotations

import logging

from platform_api.terminal_log import configure_terminal_logging

_CONFIGURED = False


def configure_api_logging() -> None:
    """Ensure all platform_api logs appear immediately in the dev terminal."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    configure_terminal_logging()

    for name in (
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
    ):
        logging.getLogger(name).setLevel(logging.INFO)

    logging.getLogger().setLevel(logging.INFO)
    _CONFIGURED = True


def default_log_config_path() -> str:
    from pathlib import Path

    return str(Path(__file__).with_name("log_config.json"))
