"""Background worker for Manual Export billing (non-blocking UI)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from features.video.lib.video_billing import VideoBillingResult, consume_video_operation


class VideoBillingWorker(QThread):
    """Charge video_manual / merge on a short QThread so the UI stays responsive."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: Any,
        *,
        operation_type: str,
        count: int = 1,
        channel_profile_id: str | None = None,
        ref_id: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("VideoBillingWorker")
        self._api = api
        self._operation_type = str(operation_type or "video_manual").strip().lower()
        self._count = max(1, int(count))
        self._channel_profile_id = channel_profile_id
        self._ref_id = ref_id

    def run(self) -> None:
        try:
            result = consume_video_operation(
                self._api,
                operation_type=self._operation_type,
                count=self._count,
                channel_profile_id=self._channel_profile_id,
                ref_id=self._ref_id,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc) or "Video billing failed.")
