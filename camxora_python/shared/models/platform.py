"""Platform API DTOs for dashboard, license, and progress."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from shared.models.auth import ProfileResponse, UserMeResponse


class DailyUsage(BaseModel):
    date: str
    songs: int = 0
    images: int = 0
    videos: int = 0


class RecentActivity(BaseModel):
    timestamp: datetime
    kind: str
    detail: str
    status: str


class DashboardStatsResponse(BaseModel):
    credits_spent: float = 0
    credits_remaining: float = 0
    credits_total: float = 0
    songs_generated: int = 0
    songs_remaining: int | None = None
    songs_quota: int | None = None
    images_remaining: int | None = None
    images_quota: int | None = None
    drafts_remaining: int | None = None
    drafts_quota: int | None = None
    images_generated: int = 0
    videos_generated: int = 0
    videos_uploaded: int = 0
    usage_by_day: list[DailyUsage] = Field(default_factory=list)
    recent_activity: list[RecentActivity] = Field(default_factory=list)


class ChannelDailyQuota(BaseModel):
    profile_id: str
    profile_name: str
    daily_songs_used: int = 0
    daily_songs_limit: int = 0
    daily_songs_remaining: int = 0
    daily_images_used: int = 0
    daily_images_limit: int = 0
    daily_images_remaining: int = 0


class QuotaStatusResponse(BaseModel):
    songs_remaining: int | None = None
    songs_quota: int | None = None
    images_remaining: int | None = None
    images_quota: int | None = None
    drafts_remaining: int | None = None
    drafts_quota: int | None = None
    videos_remaining: int | None = None
    videos_quota: int | None = None
    merges_remaining: int | None = None
    merges_quota: int | None = None
    daily_videos_remaining: int | None = None
    daily_videos_limit: int | None = None
    daily_merges_remaining: int | None = None
    daily_merges_limit: int | None = None
    wallet_balance: float = 0
    channels: list[ChannelDailyQuota] = Field(default_factory=list)


class ValidateLicenseResponse(BaseModel):
    plan_type: str
    profile_allowance: int
    profile_addon_slots: int = 0
    profile_addon_pending: int = 0
    effective_profile_allowance: int | None = None
    effective_quota_channels: int | None = None
    monthly_song_quota: int | None = None
    songs_remaining: int | None = None
    monthly_image_quota: int | None = None
    images_remaining: int | None = None
    daily_song_limit_per_channel: int | None = None
    daily_image_limit_per_channel: int | None = None
    wallet_balance: float | None = None
    expiration_date: datetime | str | None = None

    @field_validator("expiration_date", mode="before")
    @classmethod
    def _normalize_expiration(cls, value: object) -> datetime | str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return str(value)


class DashboardOverview(BaseModel):
    me: UserMeResponse
    profiles: list[ProfileResponse] = Field(default_factory=list)
    license: ValidateLicenseResponse | None = None
    stats: DashboardStatsResponse
    quota: QuotaStatusResponse | None = None


class ProgressRowMeta(BaseModel):
    batch_id: str
    profile_id: str
    role: str
    run_dir: str | None = None
    source_mode: str | None = None
    background_16x9_path: str | None = None
    background_9x16_path: str | None = None
    thumbnail_16x9_path: str | None = None
    thumbnail_9x16_path: str | None = None
    expected: int = 0
    saved: int = 0
    download_pending: int = 0
    download_ready: int = 0
    bg_ready: int = 0
    bg_total: int = 0
    th_ready: int = 0
    th_total: int = 0
    bg_status: str = "PENDING"
    th_status: str = "PENDING"
    youtube_status: str = ""
    youtube_url: str | None = None
    youtube_success: int = 0
    youtube_pending: int = 0
    youtube_failed: int = 0
    long_ready: bool = False
    reel_ready: bool = False
    music_started_at: datetime | None = None
    music_updated_at: datetime | None = None
    image_started_at: datetime | None = None
    image_updated_at: datetime | None = None
    youtube_created_at: datetime | None = None
    youtube_updated_at: datetime | None = None
    updated_at: datetime | None = None
    draft_failed_song_ids: list[str] = Field(default_factory=list)
    suno_failed_song_ids: list[str] = Field(default_factory=list)


class ProgressRow(BaseModel):
    batch: str
    run_date: str
    channel: str
    album: str | None = None
    status: str
    music: str
    image: str
    converter: str
    merge: str
    youtube: str
    stage: str
    notes: str
    updated: str
    meta: ProgressRowMeta


class ProgressListResponse(BaseModel):
    rows: list[ProgressRow] = Field(default_factory=list)
    summary: str = "Ready"
    updated_at: datetime | None = None


class ProgressFilters(BaseModel):
    limit: int = 25
    active_only: bool = False
    from_date: str | None = None
    to_date: str | None = None


class PendingMusicDownloadTarget(BaseModel):
    download_url: str | None = None
    downloaded: bool = False
    output_dir: str | None = None
    target_path: str | None = None


class PendingMusicDownloadItem(BaseModel):
    task_id: str
    song_id: str | None = None
    batch_id: str | None = None
    title: str | None = None
    track_number: int | None = None
    primary: PendingMusicDownloadTarget = Field(default_factory=PendingMusicDownloadTarget)
    secondary: PendingMusicDownloadTarget = Field(default_factory=PendingMusicDownloadTarget)


class PendingMusicDownloadsResponse(BaseModel):
    items: list[PendingMusicDownloadItem] = Field(default_factory=list)


class ImageJobsSyncManualResponse(BaseModel):
    updated: int = 0


class ImageJobListItem(BaseModel):
    id: str
    batch_id: str | None = None
    song_id: str | None = None
    profile_id: str | None = None
    kind: str
    channel_role: str
    prompt: str | None = None
    provider: str | None = None
    resolution: str = ""
    style_strength: float = 0
    input_image_path: str | None = None
    style_reference_path: str | None = None
    source_job_id: str | None = None
    status: str = "pending"
    attempt_count: int = 0
    output_image_path: str | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ImageJobsListResponse(BaseModel):
    items: list[ImageJobListItem] = Field(default_factory=list)


class ImageJobsRunRequest(BaseModel):
    batch_id: str | None = None
    limit: int = Field(default=8, ge=1, le=50)


class ImageJobsRunResponse(BaseModel):
    scheduled: int = 0


class ImageJobsRetryRequest(BaseModel):
    job_ids: list[str] | None = None
    batch_id: str | None = None


class ImageJobsRetryResponse(BaseModel):
    updated: int = 0


class ImageJobsClearRequest(BaseModel):
    batch_id: str | None = None
    statuses: list[str] | None = None


class ImageJobsClearResponse(BaseModel):
    deleted: int = 0


class ImageJobsEnqueueRequest(BaseModel):
    batch_ids: list[str] = Field(default_factory=list)


class ImageJobsEnqueueResponse(BaseModel):
    created: int = 0


class UserSettingsResponse(BaseModel):
    image_source_mode: str | None = Field(default=None, alias="imageSourceMode")
    suno_output_dir: str | None = Field(default=None, alias="sunoOutputDir")
    downloads_dir: str | None = Field(default=None, alias="downloadsDir")

    model_config = {"populate_by_name": True, "extra": "allow"}


class PromptNameOption(BaseModel):
    id: str
    name: str
    is_owned: bool = Field(default=False, alias="isOwned")
    vocal_mode: str | None = None
    default_secondary_language: str | None = None

    model_config = {"populate_by_name": True}


class MusicHistorySong(BaseModel):
    song_id: str
    batch_index: int = 0
    title: str | None = None
    album: str | None = None
    lyrics: str | None = None
    description_id: str | None = None
    description_name: str | None = None
    structure_id: str | None = None
    structure_name: str | None = None
    output_dir_ok: str | None = None
    output_dir_alt: str | None = None
    status: str = ""
    suno_status: str | None = None
    suno_error_message: str | None = None
    youtube_status: str | None = None
    downloaded_ok: bool = False
    downloaded_alt: bool = False
    image_jobs_completed: int = 0
    image_jobs_total: int = 0
    created_at: str = ""
    updated_at: str = ""


class MusicHistoryBatch(BaseModel):
    batch_id: str
    status: str = ""
    song_count: int = 0
    from_date: str | None = None
    to_date: str | None = None
    planned_days: int = 0
    ok_profile_id: str | None = None
    ok_profile_name: str | None = None
    alt_profile_id: str | None = None
    alt_profile_name: str | None = None
    ok_album: str | None = None
    alt_album: str | None = None
    created_at: str = ""
    updated_at: str = ""
    songs: list[MusicHistorySong] = Field(default_factory=list)


class MusicHistoryListResponse(BaseModel):
    batches: list[MusicHistoryBatch] = Field(default_factory=list)
    summary: str = "No history yet."
    updated_at: str | None = None


class MusicLanguageOption(BaseModel):
    code: str
    label: str


class MusicLanguageListResponse(BaseModel):
    items: list[MusicLanguageOption] = Field(default_factory=list)


class SunoBlocklistRuntimeResponse(BaseModel):
    replacements: dict[str, str] = Field(default_factory=dict)
    block_terms: list[str] = Field(default_factory=list)
    warn_terms: list[str] = Field(default_factory=list)


class OperationCostResponse(BaseModel):
    operation_type: str
    provider: str | None = None
    sub_model: str | None = None
    credits_per_operation: float | None = None
    available: bool = False
    message: str | None = None


class OperationCostsResponse(BaseModel):
    items: list[OperationCostResponse] = Field(default_factory=list)


class DraftGenerationRequest(BaseModel):
    language: str
    secondary_language: str | None = None
    creativity_level: int
    description: str | None = None
    structure: str | None = None
    description_id: str | None = None
    structure_id: str | None = None
    avoid_titles: list[str] = Field(default_factory=list)
    avoid_albums: list[str] = Field(default_factory=list)
    avoid_openings: list[str] = Field(default_factory=list)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None
    title_seed: str | None = None
    album_seed: str | None = None
    channel_profile_id: str | None = None


class DraftGenerationResponse(BaseModel):
    title: str
    album: str
    lyrics: str


class LyricsPolishRequest(BaseModel):
    lyrics: str
    strength: int
    channel_profile_id: str | None = None
    batch_id: str | None = None
    song_id: str | None = None
    title: str | None = None
    album: str | None = None
    description: str | None = None
    structure: str | None = None


class LyricsPolishResponse(BaseModel):
    lyrics: str
    suno_queued: bool = False


class MusicPlanPreflightRequest(BaseModel):
    ok_profile_ids: list[str]
    alt_profile_ids: list[str]
    from_date: str
    to_date: str
    song_count: int = 4
    auto_gen_image: bool = False
    auto_gsuno: bool = False


class MusicPlanPreflightResponse(BaseModel):
    can_generate: bool
    reason: str | None = None
    batch_count: int = 0
    total_songs: int = 0
    total_wallet_cost: int = 0
    wallet_balance: int = 0
    covered_by_subscription: bool = False
    songs_remaining: int | None = None
    images_remaining: int | None = None
    drafts_remaining: int | None = None
    credit_shortfall: int | None = None


class BatchCreateRequest(BaseModel):
    ok_profile_id: str
    alt_profile_id: str
    description_id: str | None = None
    structure_id: str | None = None
    structure_mode: str = "template"
    shuffle_structure: bool = False
    auto_gen_image: bool = False
    auto_gsuno: bool = False
    song_count: int = 4
    language: str = "en"
    secondary_language: str | None = None
    creativity_level: int = 55
    pairing_mode: str = "match_key"
    from_date: str
    to_date: str
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None
    album: str | None = None


class BatchCreateResponse(BaseModel):
    batch_id: str
    status: str = ""
    song_count: int = 0
    from_date: str = ""
    to_date: str = ""
    planned_days: int = 0
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None


class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str = ""
    total_songs: int = 0
    drafts_completed: int = 0
    drafts_failed: int = 0
    suno_submitted: int = 0
    suno_completed: int = 0
    suno_failed: int = 0
    audio_downloaded: int = 0
    images_completed: int = 0
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None


class SongRetryResponse(BaseModel):
    batch_id: str
    song_id: str
    status: str = ""
    title: str | None = None
    album: str | None = None


class ClaimedContentPoolItem(BaseModel):
    id: int
    text: str
    secondary_text: str | None = None
    used_count: int = 0
    reservation_token: str
    reserved_by: str = ""
    reserved_at: str | None = None
    created_at: str | None = None


class ClaimContentPoolResponse(BaseModel):
    kind: str
    item: ClaimedContentPoolItem


class ReservationActionResponse(BaseModel):
    ok: bool = False


class MusicDownloadSyncItem(BaseModel):
    task_id: str
    downloaded_primary: bool | None = None
    downloaded_secondary: bool | None = None
    output_dir_primary: str | None = None
    output_dir_secondary: str | None = None


class MusicDownloadSyncResponse(BaseModel):
    updated: int = 0


class YouTubeConnectionChannelOption(BaseModel):
    id: str
    title: str


class YouTubeConnectionResponse(BaseModel):
    profile_id: str
    profile_name: str
    status: str = "not_connected"
    channel_id: str | None = None
    channel_title: str | None = None
    session_id: str | None = None
    channels: list[YouTubeConnectionChannelOption] = Field(default_factory=list)
    message: str | None = None


class YouTubeConnectionsResponse(BaseModel):
    connections: list[YouTubeConnectionResponse] = Field(default_factory=list)


class StartYouTubeConnectionResponse(BaseModel):
    session_id: str
    auth_url: str
    status: str = "pending_browser"


class YouTubePlaylistOption(BaseModel):
    id: str
    title: str


class YouTubePlaylistsResponse(BaseModel):
    playlists: list[YouTubePlaylistOption] = Field(default_factory=list)


class ContentPoolStat(BaseModel):
    total: int = 0
    unused: int = 0


class ContentPoolStatsResponse(BaseModel):
    titles: ContentPoolStat = Field(default_factory=ContentPoolStat)
    albums: ContentPoolStat = Field(default_factory=ContentPoolStat)
    openings: ContentPoolStat = Field(default_factory=ContentPoolStat)


class ContentPoolRow(BaseModel):
    id: int
    text: str
    secondary_text: str | None = None
    used_count: int = 0
    created_at: str | None = None


class ContentPoolListResponse(BaseModel):
    kind: str
    total: int = 0
    limit: int = 0
    offset: int = 0
    items: list[ContentPoolRow] = Field(default_factory=list)


class ImageSamplePackItem(BaseModel):
    id: str
    category: str
    name: str
    source_type: str = ""
    source_value: str = ""
    download_url: str | None = None
    version_label: str | None = None
    notes: str | None = None

    def install_url(self) -> str:
        return (self.source_value or self.download_url or "").strip()


class ImageSamplePackListResponse(BaseModel):
    items: list[ImageSamplePackItem] = Field(default_factory=list)


def profile_image_mode(profile: dict[str, Any] | ProfileResponse) -> str:
    if isinstance(profile, ProfileResponse):
        config = profile.image_config or {}
    else:
        config = profile.get("image_config") or {}
    mode = str(config.get("mode", "bg_thumb"))
    if mode == "bg_only":
        return "Background only"
    if mode == "thumb_only":
        return "Thumbnail only"
    return "Background + Thumbnail"


def profile_visibility(profile: dict[str, Any] | ProfileResponse) -> str:
    if isinstance(profile, ProfileResponse):
        config = profile.youtube_config or {}
    else:
        config = profile.get("youtube_config") or {}
    value = str(config.get("visibility", "Unlisted")).strip()
    return value or "Unlisted"
