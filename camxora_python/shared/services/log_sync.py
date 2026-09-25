"""Upload local client logs to platform_api without exposing the raw Log UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from shared.constants.app_version import get_app_version
from shared.services.app_logger import (
    SYNC_MAX_CHARS,
    SYNC_MAX_LINES,
    get_app_logger,
)
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError


def build_client_log_payload() -> dict[str, Any] | None:
    """Build the upload payload from the in-memory logger, or None if empty."""
    text = get_app_logger().snapshot_text(max_lines=SYNC_MAX_LINES, max_chars=SYNC_MAX_CHARS)
    if not text.strip():
        return None
    line_count = text.count("\n") + 1
    return {
        "content": text,
        "lineCount": line_count,
        "appVersion": get_app_version(),
        "clientLabel": "desktop",
    }


class SyncLogsWorker(QThread):
    """Background upload of the current log snapshot."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, payload: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SyncLogsWorker")
        self._api = api
        self._payload = payload

    def run(self) -> None:
        try:
            result = self._api.upload_client_logs(self._payload)
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc) or "Log sync failed.")
        except Exception as exc:
            self.failed.emit(str(exc) or "Log sync failed.")
