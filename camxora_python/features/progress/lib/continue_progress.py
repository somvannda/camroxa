"""Resolve the next Progress recovery action for a row (Continue Progress)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from features.progress.widgets.operational_rows_card import EffectiveProgressRow
from shared.lib.manual_asset_paths import ManualAssetInspection
from shared.models.platform import ProgressRow

ContinueAction = Literal[
    "retry_drafts",
    "retry_suno",
    "enqueue_images",
    "retry_images",
    "sync_manual",
    "start_export",
    "start_merge",
    "none",
]


@dataclass(frozen=True, slots=True)
class ContinueProgressPlan:
    action: ContinueAction
    label: str
    row: ProgressRow
    batch_id: str = ""
    song_ids: list[str] = field(default_factory=list)


def resolve_continue_progress(
    entry: EffectiveProgressRow,
    *,
    manual_mode: bool = False,
    inspection: ManualAssetInspection | None = None,
) -> ContinueProgressPlan:
    """Pick the next pipeline step for this row (music → image → export → merge)."""
    row = entry.row
    meta = row.meta
    batch_id = str(meta.batch_id or row.batch or "").strip()
    stage = str(entry.effective_stage or "").strip().lower()

    draft_ids = [str(item).strip() for item in (meta.draft_failed_song_ids or []) if str(item).strip()]
    if draft_ids:
        return ContinueProgressPlan(
            action="retry_drafts",
            label=f"Retry {len(draft_ids)} failed draft(s)",
            row=row,
            batch_id=batch_id,
            song_ids=draft_ids,
        )

    suno_ids = [str(item).strip() for item in (meta.suno_failed_song_ids or []) if str(item).strip()]
    if suno_ids:
        return ContinueProgressPlan(
            action="retry_suno",
            label=f"Retry {len(suno_ids)} failed Suno job(s)",
            row=row,
            batch_id=batch_id,
            song_ids=suno_ids,
        )

    if manual_mode and stage == "image" and inspection is not None and inspection.ready:
        return ContinueProgressPlan(
            action="sync_manual",
            label="Sync manual images and continue",
            row=row,
            batch_id=batch_id,
        )

    if not manual_mode:
        bg_total = int(meta.bg_total or 0)
        th_total = int(meta.th_total or 0)
        music = str(row.music or "").upper()
        music_ready = any(token in music for token in ("READY", "SUCCESS", "DONE", "COMPLETE"))
        image_failed = (
            str(meta.bg_status or "").upper() == "FAILED"
            or str(meta.th_status or "").upper() == "FAILED"
            or (stage == "error" and "FAILED" in str(row.image or "").upper())
        )
        if image_failed or stage == "image":
            return ContinueProgressPlan(
                action="retry_images",
                label="Retry image jobs",
                row=row,
                batch_id=batch_id,
            )
        if bg_total == 0 and th_total == 0 and music_ready:
            return ContinueProgressPlan(
                action="enqueue_images",
                label="Start image generation",
                row=row,
                batch_id=batch_id,
            )

    if _prefer_merge_over_export(entry):
        return ContinueProgressPlan(
            action="start_merge",
            label="Continue / start video merge",
            row=row,
            batch_id=batch_id,
        )

    if _can_continue_export(entry):
        return ContinueProgressPlan(
            action="start_export",
            label="Continue / start video export",
            row=row,
            batch_id=batch_id,
        )

    if _can_continue_merge(entry):
        return ContinueProgressPlan(
            action="start_merge",
            label="Continue / start video merge",
            row=row,
            batch_id=batch_id,
        )

    if stage in {"youtube", "done"}:
        return ContinueProgressPlan(
            action="none",
            label="This run is already complete",
            row=row,
            batch_id=batch_id,
        )

    return ContinueProgressPlan(
        action="none",
        label="Nothing to continue for this row yet",
        row=row,
        batch_id=batch_id,
    )


def _prefer_merge_over_export(entry: EffectiveProgressRow) -> bool:
    """When local MP4s already exist for the run, Continue should merge — not re-export."""
    meta = entry.row.meta
    run_dir = str(meta.run_dir or "").strip()
    if not run_dir:
        return False
    stage = entry.effective_stage.strip().lower()
    if stage in {"youtube", "done", "completed", "error"}:
        return False
    try:
        from features.video.lib.pipeline_merge import list_branch_export_outputs
    except Exception:
        return False
    long_mp4s = list_branch_export_outputs(run_dir, "long")
    expected = int(meta.expected or 0)
    if expected > 0 and len(long_mp4s) >= expected:
        return True
    if stage in {"merge", "merger"} and long_mp4s:
        return True
    converter = str(entry.effective_converter or entry.row.converter or "").lower()
    if long_mp4s and ("completed" in converter or "merged" in converter):
        return True
    return False


def _can_continue_export(entry: EffectiveProgressRow) -> bool:
    meta = entry.row.meta
    if not str(meta.run_dir or "").strip():
        return False
    stage = entry.effective_stage.strip().lower()
    if stage in {"youtube", "done", "completed", "error", "merge", "merger"}:
        return False
    if stage in {"export", "converter"}:
        return True
    return bool(meta.long_ready or meta.reel_ready)


def _can_continue_merge(entry: EffectiveProgressRow) -> bool:
    meta = entry.row.meta
    if not str(meta.run_dir or "").strip():
        return False
    stage = entry.effective_stage.strip().lower()
    if stage in {"youtube", "done", "completed", "error"}:
        return False
    if stage in {"merge", "merger"}:
        return True
    export_text = str(entry.effective_converter or entry.row.converter or "").lower()
    if "long " in export_text or "reel " in export_text or "merged" in export_text or "completed" in export_text:
        return True
    return False
