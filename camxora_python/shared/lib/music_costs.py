"""Music credit cost calculations — port of MusicWorkspacePage cost helpers."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.auth import ProfileResponse
from shared.models.platform import OperationCostResponse


@dataclass(frozen=True, slots=True)
class MusicPlanCostBreakdown:
    planned_day_count: int
    pair_count: int
    planned_batch_count: int
    songs_per_batch: int
    planned_song_count: int
    draft_unit_cost: int | None
    draft_total_cost: int | None
    suno_unit_cost: int | None
    suno_total_cost: int | None
    image_unit_cost: int | None
    image_jobs_per_song: int
    image_total_cost: int | None
    total_cost: int | None


def map_operation_costs(items: list[OperationCostResponse] | None) -> dict[str, OperationCostResponse]:
    return {item.operation_type: item for item in (items or [])}


def get_operation_unit_cost(item: OperationCostResponse | None) -> int | None:
    if item is None or not item.available or item.credits_per_operation is None:
        return None
    return item.credits_per_operation


def format_operation_cost_label(item: OperationCostResponse | None, fallback: str) -> str:
    if item is None or not item.available or item.credits_per_operation is None:
        return f"{fallback}: unavailable"
    return f"{fallback}: {item.credits_per_operation} credits"


def format_button_credit_label(label: str, credits: int | None, unavailable_label: str = "Unavailable") -> str:
    if credits is None:
        return f"{label} ({unavailable_label})"
    return f"{label} ({credits} Credits)"


def get_profile_image_job_count(profile: ProfileResponse | None) -> int:
    if profile is None:
        return 2
    image_config = profile.image_config or {}
    raw_mode = str(image_config.get("mode", "bg_thumb")).strip().lower()
    if raw_mode in {"bg_only", "thumb_only"}:
        return 1
    return 2


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
    image_jobs_per_song = (
        sum(get_profile_image_job_count(profile) for profile in [*primary_profiles, *secondary_profiles])
        if auto_gen_image and image_source_mode != "manual"
        else 0
    )

    draft_total_cost = None if draft_unit_cost is None else draft_unit_cost * planned_song_count
    suno_total_cost = 0 if not auto_gsuno else None if suno_unit_cost is None else suno_unit_cost * planned_song_count
    if not auto_gen_image or image_source_mode == "manual":
        image_total_cost = 0
    elif image_unit_cost is None:
        image_total_cost = None
    else:
        image_total_cost = image_unit_cost * image_jobs_per_song * planned_song_count

    total_cost = None
    if draft_total_cost is not None and suno_total_cost is not None and image_total_cost is not None:
        total_cost = draft_total_cost + suno_total_cost + image_total_cost

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
        image_jobs_per_song=image_jobs_per_song,
        image_total_cost=image_total_cost,
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
) -> int | None:
    """Batch Generate button total — mirrors getBatchGenerateTotalCost in MusicWorkspacePage.tsx."""
    if (
        song_count <= 0
        or not primary_profiles
        or len(primary_profiles) != len(secondary_profiles)
        or planned_day_count is None
        or planned_day_count <= 0
    ):
        return None

    draft_unit_cost = get_operation_unit_cost(lyric_cost)
    if draft_unit_cost is None:
        return None

    pair_count = len(primary_profiles)
    planned_song_count = pair_count * planned_day_count * song_count
    total_cost = draft_unit_cost * planned_song_count

    if auto_gsuno:
        suno_unit_cost = get_operation_unit_cost(music_cost)
        if suno_unit_cost is None:
            return None
        total_cost += suno_unit_cost * planned_song_count

    if not auto_gen_image or image_source_mode == "manual":
        return total_cost

    image_unit_cost = get_operation_unit_cost(image_cost)
    if image_unit_cost is None:
        return None

    image_jobs_per_song = sum(
        get_profile_image_job_count(profile) for profile in [*primary_profiles, *secondary_profiles]
    )
    return total_cost + image_unit_cost * image_jobs_per_song * planned_song_count


def get_batch_generate_total_cost_from_breakdown(breakdown: MusicPlanCostBreakdown | None) -> int | None:
    if breakdown is None:
        return None
    return breakdown.total_cost
