"""Structured debug probe emitter for YouTube upload diagnostics.

Replaces inline exec()/urllib.request debug probes with a safe, structured
logging approach that is a complete no-op unless MG_DEBUG_PROBES=1.
"""
from __future__ import annotations

import logging
import os


class DebugProbeEmitter:
    """Emits structured debug log records when MG_DEBUG_PROBES=1.

    When the environment variable is absent or not "1", `emit()` returns
    immediately without opening any file, creating any network connection,
    or writing to stdout/stderr.
    """

    def __init__(self, env_file: str) -> None:
        self._env_file: str = env_file
        self._logger: logging.Logger = logging.getLogger("mg.debug_probe")

    def emit(
        self,
        *,
        hypothesis: str,
        location: str,
        msg: str,
        data: dict[str, object],
    ) -> None:
        """Emit a structured debug probe record.

        Returns immediately (no-op) when MG_DEBUG_PROBES != "1".
        When enabled, reads session_id and hypothesis_id from the env file
        and logs a DEBUG record with all five structured fields.
        """
        if os.environ.get("MG_DEBUG_PROBES") != "1":
            return

        session_id: str = ""
        hypothesis_id: str = ""

        try:
            with open(self._env_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if not stripped or "=" not in stripped:
                        continue
                    key, _, value = stripped.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key == "session_id":
                        session_id = value
                    elif key == "hypothesis_id":
                        hypothesis_id = value
        except (OSError, ValueError, UnicodeDecodeError):
            # Silently ignore missing file and parse errors
            pass

        try:
            self._logger.debug(
                msg,
                extra={
                    "session_id": session_id,
                    "hypothesis_id": hypothesis_id,
                    "location": location,
                    "msg": msg,
                    "data": data,
                },
            )
        except Exception:  # noqa: BLE001
            # A misconfigured log handler must not crash the upload worker
            pass


_probe: DebugProbeEmitter = DebugProbeEmitter(".dbg/youtube-upload-issues.env")
