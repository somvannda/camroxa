"""Workflow step derivation from progress rows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from shared.lib.video_runtime_inspection import ProgressRuntimePresentation, run_includes_reel
from shared.models.platform import ProgressRow

STEP_ORDER = ("music", "image", "converter", "merger", "distrokid", "youtube")
ACTIVE_VERB_STATUSES = frozenset(
    {
        "running",
        "rendering",
        "generating",
        "downloading",
        "converting",
        "merging",
        "uploading",
        "processing",
        "queued",
        "in progress",
    }
)


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    key: str
    title: str
    percent: int
    state: str
    duration: str
    details: tuple[str, ...]


def clamp_percent(value: float) -> int:
    return max(0, min(100, round(value)))


def format_role_label(role: str) -> str:
    return "Secondary" if str(role or "").strip().lower() == "secondary" else "Primary"


def normalize_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def is_active_verb_status(status: str) -> bool:
    return normalize_key(status) in ACTIVE_VERB_STATUSES


def looks_partial_text(value: str) -> bool:
    text = normalize_key(value)
    return (
        "pending" in text
        or "partial" in text
        or "in progress" in text
        or bool(re.search(r"/\s*0\b", text))
        or bool(re.search(r"\b0/", text))
    )


def normalize_pipeline_stage(stage: str) -> str:
    key = normalize_key(stage)
    if key in {"export", "converter"}:
        return "converter"
    if key in {"merge", "merger"}:
        return "merger"
    return key


def format_branch_copy(text: str, *, include_reel: bool) -> str:
    """Strip reel metrics/copy when reel is not part of the run."""
    value = str(text or "").strip()
    if include_reel or not value:
        return value
    cleaned = re.sub(
        r"\s*[·•]\s*reel\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\breel\b[^.]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ·•")
    return cleaned or value


def looks_complete_branch_pair(text: str, *, include_reel: bool = True) -> bool:
    raw = str(text or "")
    if not include_reel:
        if re.search(r"long\s+ready\b", raw, flags=re.IGNORECASE):
            return True
        match = re.search(r"long\s+(\d+)\s*/\s*(\d+)", raw, flags=re.IGNORECASE)
        if match is None:
            return False
        long_ready = int(match.group(1))
        long_total = int(match.group(2))
        return long_ready >= long_total and long_total > 0

    match = re.search(
        r"long\s+(\d+)\s*/\s*(\d+)\s*·\s*reel\s+(\d+)\s*/\s*(\d+)",
        raw,
        flags=re.IGNORECASE,
    )
    if match is None:
        return False
    long_ready = int(match.group(1))
    long_total = int(match.group(2))
    reel_ready = int(match.group(3))
    reel_total = int(match.group(4))
    return long_ready >= long_total and reel_ready >= reel_total and long_total > 0


def looks_complete_merge_pair(text: str, *, include_reel: bool = True) -> bool:
    normalized = normalize_key(text)
    if not normalized:
        return False
    if not include_reel:
        if "reel pending" in normalized and "long merged" not in normalized and "long completed" not in normalized and "long single" not in normalized:
            return False
        # Ignore trailing reel-pending noise left by runtime merge labels.
        long_only = re.sub(r"\s*[·•]\s*reel\b.*$", "", normalized)
        if "pending" in long_only and "not required" not in long_only:
            return False
        return (
            "long merged" in long_only
            or "long completed" in long_only
            or "long single" in long_only
            or "not required" in long_only
        )
    if "pending" in normalized:
        return False
    return ("long merged" in normalized or "long completed" in normalized) and (
        "reel merged" in normalized
        or "reel completed" in normalized
        or "reel single" in normalized
        or "not required" in normalized
    )


def format_upload_status(row: ProgressRow) -> str:
    if row.meta.youtube_success > 0 or bool(row.meta.youtube_url):
        return "Uploaded"
    if row.meta.youtube_failed > 0 or normalize_key(row.meta.youtube_status) == "failed":
        return "Failed"
    if normalize_key(row.meta.youtube_status) == "blocked":
        return "Blocked"
    if row.meta.youtube_pending > 0 or normalize_key(row.meta.youtube_status) in {
        "uploading",
        "queued",
        "processing",
    }:
        return "Uploading"
    if normalize_key(row.youtube) == "ready":
        return "Ready"
    return "Not started"


def resolve_run_status_label(
    stage: str,
    status: str,
    row: ProgressRow,
    converter_text: str | None = None,
    merge_text: str | None = None,
    *,
    include_reel: bool | None = None,
) -> str:
    """Honest run-level status: Completed only when Done; Partial/Ready otherwise."""
    stage_key = normalize_pipeline_stage(stage)
    status_key = normalize_key(status)
    reel_included = run_includes_reel(row) if include_reel is None else include_reel

    if stage_key == "error" or status_key == "failed":
        return "Failed"
    if stage_key == "done":
        return "Completed"
    if stage_key == "youtube":
        return format_upload_status(row)

    converter = converter_text if converter_text is not None else row.converter
    merge = merge_text if merge_text is not None else row.merge

    if stage_key == "converter" or stage_key == "export":
        if is_active_verb_status(status):
            return "In Progress"
        if (
            status_key in {"partial", "in progress"}
            or looks_partial_text(converter)
            or (
                status_key == "completed"
                and not looks_complete_branch_pair(converter, include_reel=reel_included)
            )
        ):
            return "In Progress"
        if status_key == "completed":
            return "Completed"

    if stage_key == "merger" or stage_key == "merge":
        if is_active_verb_status(status):
            return "In Progress"
        if status_key in {"partial", "in progress"} or looks_partial_text(merge):
            if not reel_included and looks_complete_merge_pair(merge, include_reel=False):
                return "Completed"
            return "In Progress"
        if status_key == "completed":
            return "Completed" if looks_complete_merge_pair(merge, include_reel=reel_included) else "In Progress"

    if status_key in {"completed", "done"}:
        return "Completed"
    if status_key in {"partial", "in progress"}:
        return "In Progress"
    return str(status or "").strip() or "Pending"


def lane_needs_attention(
    row: ProgressRow,
    runtime: ProgressRuntimePresentation | None = None,
) -> bool:
    """Failed/blocked rows plus pending image or merge blockers."""
    stage = normalize_pipeline_stage(runtime.stage if runtime else row.stage)
    status = normalize_key(runtime.status if runtime else row.status)
    merge_text = normalize_key(runtime.merge if runtime else row.merge)
    youtube_status = normalize_key(row.meta.youtube_status)
    bg_status = normalize_key(row.meta.bg_status)
    th_status = normalize_key(row.meta.th_status)

    if stage == "error" or status == "failed":
        return True
    if row.meta.youtube_failed > 0 or youtube_status in {"failed", "blocked"}:
        return True
    if bg_status == "failed" or th_status == "failed":
        return True
    if "blocked" in merge_text:
        return True

    images_incomplete = (
        row.meta.bg_total > 0 and row.meta.bg_ready < row.meta.bg_total
    ) or (row.meta.th_total > 0 and row.meta.th_ready < row.meta.th_total)
    if images_incomplete and stage in {"image", "converter", "merger", "export", "merge", "youtube"}:
        return True

    if stage in {"merger", "merge"} and ("pending" in merge_text or status in {"partial", "in progress"}):
        return True
    return False


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_duration(start: datetime | str | None, end: datetime | str | None) -> str:
    start_date = _parse_datetime(start)
    end_date = _parse_datetime(end)
    if start_date is None or end_date is None:
        return "--"
    seconds = max(0, round((end_date - start_date).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds / 60:.1f} min"


def _state_for(
    step_key: str,
    percent: int,
    *,
    effective_stage: str,
    effective_status: str,
    failed: bool,
    row_done: bool,
    detail_text: str,
) -> str:
    stage = normalize_pipeline_stage(effective_stage)
    if failed and step_key in STEP_ORDER and stage == step_key:
        return "failed"
    order = list(STEP_ORDER)
    current_index = order.index(stage) if stage in order else -1
    step_index = order.index(step_key)
    if row_done or stage == "done":
        return "done"
    if failed and current_index < 0:
        return "failed"
    if current_index < 0:
        return "done" if percent >= 100 else "inactive"
    if step_index < current_index:
        return "done"
    if step_index == current_index:
        if failed:
            return "failed"
        if percent >= 100:
            return "done"
        if is_active_verb_status(effective_status):
            return "running"
        if percent > 0 or looks_partial_text(detail_text) or normalize_key(effective_status) == "partial":
            return "partial"
        return "running"
    return "inactive"


def build_workflow_steps(
    row: ProgressRow | None,
    runtime: ProgressRuntimePresentation | None = None,
) -> list[WorkflowStep]:
    if row is None:
        return [
            WorkflowStep(key, title, 0, "inactive", "--", ("No run selected",))
            for key, title in (
                ("music", "Music Generation"),
                ("image", "Background + Thumbnail"),
                ("converter", "Convert (MP4)"),
                ("merger", "Merger"),
                ("distrokid", "DistroKid"),
                ("youtube", "YouTube Upload"),
            )
        ]

    effective_stage = runtime.stage if runtime else row.stage
    effective_status = runtime.status if runtime else row.status
    stage_lower = normalize_pipeline_stage(effective_stage)
    failed = stage_lower == "error" or effective_status.lower() == "failed"
    row_done = row.stage == "Done"
    include_reel = run_includes_reel(row, runtime)
    converter_text = format_branch_copy(
        runtime.converter if runtime else row.converter,
        include_reel=include_reel,
    )
    merge_text = format_branch_copy(
        runtime.merge if runtime else row.merge,
        include_reel=include_reel,
    )
    youtube_detail = format_upload_status(row)

    expected = max(1, row.meta.expected)
    music_percent = clamp_percent((row.meta.saved / expected) * 100)
    bg_percent = row.meta.bg_ready / row.meta.bg_total if row.meta.bg_total > 0 else 0
    th_percent = row.meta.th_ready / row.meta.th_total if row.meta.th_total > 0 else 0
    image_percent = clamp_percent(((bg_percent + th_percent) / 2) * 100)
    youtube_percent = (
        100
        if row.meta.youtube_success > 0
        else 50
        if row.meta.youtube_pending > 0
        else 100
        if row.meta.youtube_failed > 0
        else 0
    )
    downstream_complete = row.meta.youtube_success > 0 or row.stage == "Done"
    converter_percent = 100 if downstream_complete else (runtime.converter_percent if runtime else 0)
    merge_percent = 100 if downstream_complete else (runtime.merge_percent if runtime else 0)

    distrokid_summary = {"status": "inactive", "percent": 0, "detail": "DistroKid not started"}
    try:
        from features.distrokid.lib.distrokid_job_store import DistroKidJobStore

        run_dir = str((row.meta.run_dir if row.meta else "") or "")
        distrokid_summary = DistroKidJobStore().summary_for_workflow(
            batch_id=str(row.meta.batch_id or ""),
            run_dir=run_dir,
            role=str(row.meta.role or ""),
        )
    except Exception:
        if merge_percent >= 100:
            distrokid_summary = {
                "status": "partial",
                "percent": 40,
                "detail": "DistroKid soft stage (status unavailable)",
            }

    def status_detail(step_name: str) -> str:
        if normalize_pipeline_stage(effective_stage) != normalize_key(step_name):
            return "--"
        if step_name == "YouTube":
            return youtube_detail
        return resolve_run_status_label(
            effective_stage,
            effective_status,
            row,
            converter_text,
            merge_text,
            include_reel=include_reel,
        )

    music_detail = f"{row.meta.saved}/{expected} songs"
    return [
        WorkflowStep(
            "music",
            "Music Generation",
            music_percent,
            _state_for(
                "music",
                music_percent,
                effective_stage=effective_stage,
                effective_status=effective_status,
                failed=failed,
                row_done=row_done,
                detail_text=music_detail,
            ),
            format_duration(row.meta.music_started_at, row.meta.music_updated_at),
            (music_detail, status_detail("Music")),
        ),
        WorkflowStep(
            "image",
            "Background + Thumbnail",
            image_percent,
            _state_for(
                "image",
                image_percent,
                effective_stage=effective_stage,
                effective_status=effective_status,
                failed=failed,
                row_done=row_done,
                detail_text=row.image,
            ),
            format_duration(row.meta.image_started_at, row.meta.image_updated_at),
            (row.image, status_detail("Image")),
        ),
        WorkflowStep(
            "converter",
            "Convert (MP4)",
            converter_percent,
            _state_for(
                "converter",
                converter_percent,
                effective_stage=effective_stage,
                effective_status=effective_status,
                failed=failed,
                row_done=row_done,
                detail_text=converter_text,
            ),
            "--",
            (converter_text, status_detail("Converter")),
        ),
        WorkflowStep(
            "merger",
            "Merger",
            merge_percent,
            _state_for(
                "merger",
                merge_percent,
                effective_stage=effective_stage,
                effective_status=effective_status,
                failed=failed,
                row_done=row_done,
                detail_text=merge_text,
            ),
            "--",
            (merge_text, status_detail("Merger")),
        ),
        WorkflowStep(
            "distrokid",
            "DistroKid",
            int(distrokid_summary.get("percent") or 0),
            str(distrokid_summary.get("status") or "inactive"),
            "--",
            (
                str(distrokid_summary.get("detail") or "Soft DistroKid stage"),
                "Does not fail the video run.",
            ),
        ),
        WorkflowStep(
            "youtube",
            "YouTube Upload",
            youtube_percent,
            _state_for(
                "youtube",
                youtube_percent,
                effective_stage=effective_stage,
                effective_status=effective_status,
                failed=failed,
                row_done=row_done,
                detail_text=youtube_detail,
            ),
            format_duration(row.meta.youtube_created_at, row.meta.youtube_updated_at),
            (youtube_detail, status_detail("YouTube")),
        ),
    ]


def build_current_focus(
    row: ProgressRow,
    runtime: ProgressRuntimePresentation | None = None,
) -> str:
    stage = normalize_pipeline_stage(str((runtime.stage if runtime else row.stage) or ""))
    include_reel = run_includes_reel(row, runtime)
    if stage == "music":
        if row.meta.download_pending > 0:
            return (
                f"Waiting on {row.meta.download_pending} remaining desktop MP3 download(s) "
                "before downstream video work can begin."
            )
        return "Music generation is still finishing before the downstream pipeline advances."
    if stage == "image":
        assets_ready = row.meta.long_ready and (row.meta.reel_ready if include_reel else True)
        if not assets_ready:
            if include_reel:
                return "Waiting for the required long/reel background image(s) before video export can start."
            return "Waiting for the required long background image before video export can start."
        return "Image generation is finishing and the lane is preparing the video inputs."
    if stage == "converter":
        converter = runtime.converter if runtime else row.converter
        status = runtime.status if runtime else row.status
        if looks_partial_text(converter) or normalize_key(status) == "partial":
            if include_reel:
                return (
                    "Convert is partial — long and reel exports finish independently "
                    "before merge can complete."
                )
            return "Convert is partial — long export is still finishing before merge can complete."
        if include_reel:
            return "The lane is in per-track MP4 export. Long export always starts before reel export."
        return "The lane is in per-track MP4 export for the long video branch."
    if stage == "merger":
        merge = runtime.merge if runtime else row.merge
        status = runtime.status if runtime else row.status
        if looks_partial_text(merge) or normalize_key(status) == "partial":
            if include_reel:
                return "Merge is partial — one deliverable branch is ready while the other is still pending."
            return "Merge is partial — the long deliverable is still finishing."
        return "Track-level exports exist and the lane is now focused on producing merged deliverables."
    if stage == "youtube":
        if row.meta.youtube_success > 0 or row.meta.youtube_url:
            return "YouTube handoff completed for the long merged output."
        return "Waiting for YouTube upload — the long merged output is the only valid handoff target."
    if stage == "done":
        return "This lane has completed the visible pipeline successfully."
    if stage == "error":
        notes = str((runtime.notes if runtime else row.notes) or "").strip()
        return notes or "This lane needs operator attention in Progress."
    return "Select a lane to inspect where it currently sits in the pipeline."


def stage_tone_object_name(stage: str, status: str) -> str:
    """Legacy combined tone helper — prefer split role/stage/status helpers."""
    from shared.themes.badge_pills import stage_tone_object_name as _tone

    return _tone(stage, status)


def step_empty_hint(step: WorkflowStep) -> str | None:
    if step.state != "inactive":
        return None
    if step.key == "merger":
        return "Waiting for converter outputs before merge can start."
    if step.key == "youtube":
        return "Waiting — upload starts after the long merged deliverable is ready."
    if step.key == "converter":
        return "Waiting for music and image assets to be ready."
    if step.key == "image":
        return "Waiting for music downloads to finish."
    if step.key == "distrokid":
        return "Soft DistroKid stage — starts after long merge when the Music DistroKid checkbox is on."
    if step.key == "music":
        return "Waiting for music generation to start."
    return None


def detail_looks_empty(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or normalized in {"--", "empty", "n/a", "none"}


def state_label(state: str) -> str:
    return {
        "done": "Done",
        "running": "In progress",
        "partial": "Partial",
        "failed": "Failed",
        "inactive": "Not started",
    }.get(state, "Not started")
