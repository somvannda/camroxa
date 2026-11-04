"""Decide whether a finished merge should be published automatically.

Kept pure so the rule is testable without a QApplication or network: the caller
passes the persisted settings and the merge context, and gets a yes/no plus the
context the publishing worker needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

AUTO_UPLOAD_SETTING_KEY = "autoUploadYouTube"


@dataclass(frozen=True, slots=True)
class AutoPublishPlan:
    profile_id: str
    merged_path: str
    run_dir: str
    batch_id: str | None
    role: str


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def auto_publish_plan(
    settings: Mapping[str, Any] | None,
    merge_context: Mapping[str, Any] | None,
    merged_path: str | None,
) -> AutoPublishPlan | None:
    """The auto-publish context, or None when this merge must not be published.

    Requires the YouTube Upload toggle, a channel profile, and a merged file.
    Credits and provider errors stay the worker's job (it quotes before upload).
    """
    if not _truthy((settings or {}).get(AUTO_UPLOAD_SETTING_KEY)):
        return None
    path = str(merged_path or "").strip()
    if not path:
        return None
    context = dict(merge_context or {})
    profile_id = str(context.get("profile_id") or "").strip()
    if not profile_id:
        return None
    return AutoPublishPlan(
        profile_id=profile_id,
        merged_path=path,
        run_dir=str(context.get("run_dir") or "").strip(),
        batch_id=str(context.get("batch_id") or "").strip() or None,
        role=str(context.get("role") or "OK").strip().upper() or "OK",
    )


def worker_context(plan: AutoPublishPlan) -> dict[str, object]:
    """Shape the plan the way CreatePublishJobWorker's auto_context expects."""
    return {
        "profile_id": plan.profile_id,
        "merged_path": plan.merged_path,
        "run_dir": plan.run_dir,
        "batch_id": plan.batch_id,
        "role": plan.role,
    }
