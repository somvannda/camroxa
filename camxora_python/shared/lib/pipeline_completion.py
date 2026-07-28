"""Mark a Progress channel row as desktop-pipeline complete on the API."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def mark_desktop_pipeline_complete(
    api: Any,
    *,
    batch_id: str,
    profile_id: str,
    role: str,
    run_dir: str | None = None,
) -> None:
    """Persist conclusive Completed status so moved/archived folders do not reopen work."""
    batch = str(batch_id or "").strip()
    profile = str(profile_id or "").strip()
    channel_role = str(role or "OK").strip().upper() or "OK"
    if not batch or not profile:
        return
    try:
        from shared.models.platform import ProgressLocalSyncItem

        api.sync_local_progress(
            [
                ProgressLocalSyncItem(
                    batch_id=batch,
                    profile_id=profile,
                    role=channel_role,
                    run_dir=str(run_dir or "").strip() or None,
                    pipeline_complete=True,
                )
            ]
        )
    except Exception:
        logger.warning(
            "Failed to mark desktop pipeline complete for batch=%s profile=%s role=%s",
            batch,
            profile,
            channel_role,
            exc_info=True,
        )
