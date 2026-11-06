"""Decide whether a finished merge should be published automatically.

Kept pure so the rule is testable without a QApplication or network: the caller
passes the persisted settings and the merge context, and gets a yes/no plus the
context the publishing worker needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

AUTO_UPLOAD_SETTING_KEY = "autoUploadYouTube"

# Merged files already claimed for publishing in this process. Both the video
# page and the pipeline automation service can finish the same merge; this keeps
# one upload per file so a path is never published (and charged) twice.
_CLAIMED_PATHS: set[str] = set()


def _path_key(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/")
    return normalized.lower() if normalized else ""


def claim_publish(path: str | None) -> bool:
    """Reserve ``path`` for publishing. False when it was already claimed."""
    key = _path_key(path or "")
    if not key:
        return False
    if key in _CLAIMED_PATHS:
        return False
    _CLAIMED_PATHS.add(key)
    return True


def release_publish(path: str | None) -> None:
    """Allow a retry after a failed upload."""
    _CLAIMED_PATHS.discard(_path_key(path or ""))



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
    context = dict(merge_context or {})
    # The batch stores the choice it was created with; fall back to live settings
    # only for runs created before that flag existed.
    explicit = context.get(AUTO_UPLOAD_SETTING_KEY)
    enabled = _truthy(explicit) if explicit is not None else _truthy(
        (settings or {}).get(AUTO_UPLOAD_SETTING_KEY)
    )
    if not enabled:
        return None
    path = str(merged_path or "").strip()
    if not path:
        return None
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


def discover_merged_path(run_dir: str | None) -> str:
    """Newest long-form MERGED_*.mp4 under a run folder ("" when none).

    The Progress row does not always have a manual inspection, and relying on it
    hid the Upload action; the run folder is written by the desktop itself.
    """
    root_text = str(run_dir or "").strip()
    if not root_text:
        return ""
    root = Path(root_text)
    if not root.is_dir():
        return ""
    candidates = [
        item
        for item in root.glob("MERGED_*.mp4")
        if item.is_file() and not item.name.upper().startswith("MERGED_REEL_")
    ]
    if not candidates:
        sub = root / "merged"
        if sub.is_dir():
            candidates = [
                item
                for item in sub.glob("*.mp4")
                if item.is_file() and not item.name.upper().startswith("MERGED_REEL_")
            ]
    if not candidates:
        return ""
    newest = max(candidates, key=lambda item: item.stat().st_mtime)
    return str(newest)


def manual_publish_context(
    row: object,
    merged_path: str | None,
) -> dict[str, object] | None:
    """Context for the Progress "Upload to YouTube" action (no toggle required).

    Unlike the automation path this is an explicit user action, so it only needs
    a merged file and the row's channel profile.
    """
    path = str(merged_path or "").strip()
    if not path:
        return None
    meta = getattr(row, "meta", None)
    profile_id = str(getattr(meta, "profile_id", "") or "").strip()
    if not profile_id:
        return None
    return {
        "profile_id": profile_id,
        "merged_path": path,
        "run_dir": str(getattr(meta, "run_dir", "") or "").strip(),
        "batch_id": str(getattr(meta, "batch_id", "") or "").strip() or None,
        "role": str(getattr(meta, "role", "") or "OK").strip().upper() or "OK",
    }
