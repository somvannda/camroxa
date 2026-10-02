"""Music credit cost calculations — port of MusicWorkspacePage cost helpers."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.auth import ProfileResponse
from shared.models.platform import OperationCostResponse

# One Suno song package yields one track per channel (Primary + Secondary).
TRACKS_PER_SONG_PACKAGE = 2
# Each album/channel is merged once.
MERGE_OPS_PER_BATCH = 2


@dataclass(frozen=True, slots=True)
class MusicPlanCostBreakdown:
    planned_day_count: int
    pair_count: int
    planned_batch_count: int
    songs_per_batch: int
    planned_song_count: int
    draft_unit_cost: float | None
    draft_total_cost: float | None
    suno_unit_cost: float | None
    suno_total_cost: float | None
    image_unit_cost: float | None
    # Album BG/TH jobs for one Primary+Secondary pair (not per song).
    image_jobs_per_batch: int
    image_total_jobs: int
    image_total_cost: float | None
    video_unit_cost: float | None
    video_ops: int
    video_total_cost: float | None
    merge_unit_cost: float | None
    merge_ops: int
    merge_total_cost: float | None
    total_cost: float | None

    @property
    def image_jobs_per_song(self) -> int:
        """Backward-compatible alias — historically misnamed; means jobs per batch."""
        return self.image_jobs_per_batch

    @property
    def video_merge_total_cost(self) -> float | None:
        if self.video_total_cost is None or self.merge_total_cost is None:
            return None
        return self.video_total_cost + self.merge_total_cost


def map_operation_costs(items: list[OperationCostResponse] | None) -> dict[str, OperationCostResponse]:
    return {item.operation_type: item for item in (items or [])}


def get_operation_unit_cost(item: OperationCostResponse | None) -> float | None:
    if item is None or not item.available or item.credits_per_operation is None:
        return None
    return float(item.credits_per_operation)


def _fmt_credits(value: float | int) -> str:
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def format_plan_credits(value: float | int | None) -> str:
    if value is None:
        return "unavailable"
    return _fmt_credits(value)


def format_operation_cost_label(item: OperationCostResponse | None, fallback: str) -> str:
    if item is None or not item.available or item.credits_per_operation is None:
        return f"{fallback}: unavailable"
    return f"{fallback}: {_fmt_credits(item.credits_per_operation)} credits"


def format_button_credit_label(
    label: str, credits: float | int | None, unavailable_label: str = "Unavailable"
) -> str:
    if credits is None:
        return f"{label} ({unavailable_label})"
    return f"{label} ({_fmt_credits(credits)} credits)"


def format_draft_slot_button_label(label: str, slots: int = 1) -> str:
    """Label for ops that consume plan draft allowance (e.g. 1 polish = 1 draft)."""
    unit = "Draft" if slots == 1 else "Drafts"
    return f"{label} ({slots} {unit})"


def get_profile_image_job_count(profile: ProfileResponse | None) -> int:
    if profile is None:
        return 2
    image_config = profile.image_config or {}
    raw_mode = str(image_config.get("mode", "bg_thumb")).strip().lower()
    if raw_mode in {"bg_only", "thumb_only"}:
        return 1
    return 2


def _image_jobs_for_pairs(
    primary_profiles: list[ProfileResponse],
    secondary_profiles: list[ProfileResponse],
) -> tuple[int, int]:
    """Return (jobs_per_batch_for_first_pair_or_avg_display, total_jobs_across_pairs).

    Album images are one BG/TH set per channel per batch — not per song.
    """
    per_pair = [
        get_profile_image_job_count(ok) + get_profile_image_job_count(alt)
        for ok, alt in zip(primary_profiles, secondary_profiles, strict=False)
    ]
    if not per_pair:
        return 0, 0
    # UI shows a single "per batch" figure; pairs usually share the same mode.
    return per_pair[0], sum(per_pair)


def get_music_plan_cost_breakdown(
    lyric_cost: OperationCostResponse | None,
    music_cost: OperationCostResponse | None,
    image_cost: OperationCostResponse | None,
    primary_profiles: list[ProfileResponse],
    secondary_profiles: list[ProfileResponse],
    song_count: int,
    auto_gen_image: bool,
    auto_gsuno: bool,
    planned_day_count: int | None,
    image_source_mode: str,
    video_cost: OperationCostResponse | None = None,
    merge_cost: OperationCostResponse | None = None,
    auto_video: bool = False,
    auto_merge: bool = False,
    auto_reel: bool = False,
) -> MusicPlanCostBreakdown | None:
    if (
        song_count <= 0
        or not primary_profiles
        or len(primary_profiles) != len(secondary_profiles)
        or planned_day_count is None
        or planned_day_count <= 0
    ):
        return None

    pair_count = len(primary_profiles)
    planned_batch_count = pair_count * planned_day_count
    planned_song_count = planned_batch_count * song_count
    draft_unit_cost = get_operation_unit_cost(lyric_cost)
    suno_unit_cost = get_operation_unit_cost(music_cost)
    image_unit_cost = get_operation_unit_cost(image_cost)
    jobs_per_batch, jobs_all_pairs = _image_jobs_for_pairs(primary_profiles, secondary_profiles)
    image_jobs_per_batch = jobs_per_batch if auto_gen_image and image_source_mode != "manual" else 0
    image_total_jobs = (
        jobs_all_pairs * planned_day_count
        if auto_gen_image and image_source_mode != "manual"
        else 0
    )

    draft_total_cost = None if draft_unit_cost is None else draft_unit_cost * planned_song_count
    suno_total_cost = 0 if not auto_gsuno else None if suno_unit_cost is None else suno_unit_cost * planned_song_count
    if not auto_gen_image or image_source_mode == "manual":
        image_total_cost = 0.0
    elif image_unit_cost is None:
        image_total_cost = None
    else:
        image_total_cost = image_unit_cost * image_total_jobs

    # Local export/merge run after music + images. Only meaningful with Suno.
    video_unit_cost = get_operation_unit_cost(video_cost)
    merge_unit_cost = get_operation_unit_cost(merge_cost)
    branch_multiplier = 2 if auto_reel else 1
    billable_video = bool(auto_video and auto_gsuno)
    billable_merge = billable_video and bool(auto_merge)
    video_ops = planned_song_count * TRACKS_PER_SONG_PACKAGE * branch_multiplier if billable_video else 0
    merge_ops = planned_batch_count * MERGE_OPS_PER_BATCH * branch_multiplier if billable_merge else 0
    if not billable_video:
        video_total_cost = 0.0
    elif video_unit_cost is None:
        video_total_cost = None
    else:
        video_total_cost = video_unit_cost * video_ops
    if not billable_merge:
        merge_total_cost = 0.0
    elif merge_unit_cost is None:
        merge_total_cost = None
    else:
        merge_total_cost = merge_unit_cost * merge_ops

    total_cost = None
    if (
        draft_total_cost is not None
        and suno_total_cost is not None
        and image_total_cost is not None
        and video_total_cost is not None
        and merge_total_cost is not None
    ):
        total_cost = (
            draft_total_cost
            + suno_total_cost
            + image_total_cost
            + video_total_cost
            + merge_total_cost
        )

    return MusicPlanCostBreakdown(
        planned_day_count=planned_day_count,
        pair_count=pair_count,
        planned_batch_count=planned_batch_count,
        songs_per_batch=song_count,
        planned_song_count=planned_song_count,
        draft_unit_cost=draft_unit_cost,
        draft_total_cost=draft_total_cost,
        suno_unit_cost=suno_unit_cost,
        suno_total_cost=suno_total_cost,
        image_unit_cost=image_unit_cost,
        image_jobs_per_batch=image_jobs_per_batch,
        image_total_jobs=image_total_jobs,
        image_total_cost=image_total_cost,
        video_unit_cost=video_unit_cost,
        video_ops=video_ops,
        video_total_cost=video_total_cost,
        merge_unit_cost=merge_unit_cost,
        merge_ops=merge_ops,
        merge_total_cost=merge_total_cost,
        total_cost=total_cost,
    )


def get_batch_generate_total_cost(
    lyric_cost: OperationCostResponse | None,
    music_cost: OperationCostResponse | None,
    image_cost: OperationCostResponse | None,
    primary_profiles: list[ProfileResponse],
    secondary_profiles: list[ProfileResponse],
    song_count: int,
    auto_gen_image: bool,
    auto_gsuno: bool,
    planned_day_count: int | None,
    image_source_mode: str,
    video_cost: OperationCostResponse | None = None,
    merge_cost: OperationCostResponse | None = None,
    auto_video: bool = False,
    auto_merge: bool = False,
    auto_reel: bool = False,
) -> float | None:
    """Batch Generate button total — mirrors getBatchGenerateTotalCost in MusicWorkspacePage.tsx."""
    breakdown = get_music_plan_cost_breakdown(
        lyric_cost,
        music_cost,
        image_cost,
        primary_profiles,
        secondary_profiles,
        song_count,
        auto_gen_image,
        auto_gsuno,
        planned_day_count,
        image_source_mode,
        video_cost,
        merge_cost,
        auto_video,
        auto_merge,
        auto_reel,
    )
    return get_batch_generate_total_cost_from_breakdown(breakdown)


def get_batch_generate_total_cost_from_breakdown(breakdown: MusicPlanCostBreakdown | None) -> float | None:
    if breakdown is None:
        return None
    return breakdown.total_cost
