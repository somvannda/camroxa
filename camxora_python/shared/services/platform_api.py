"""Platform API endpoints — mirrors platformEndpoints.ts."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from shared.models.auth import (
    CreateProfileRequest,
    LoginRequest,
    ProfileResponse,
    TokenResponse,
    UpdateProfileRequest,
    UserMeResponse,
)
from shared.models.platform import (
    AlbumRewriteResponse,
    BatchCreateRequest,
    BatchCreateResponse,
    BatchDeleteResponse,
    BatchRedownloadPlanResponse,
    BatchStatusResponse,
    SongRetryResponse,
    TitleRewriteResponse,
    ClaimContentPoolResponse,
    ContentPoolListResponse,
    ContentPoolStatsResponse,
    DashboardOverview,
    DashboardStatsResponse,
    DraftGenerationRequest,
    DraftGenerationResponse,
    ImageJobsClearRequest,
    ImageJobsClearResponse,
    ImageJobsEnqueueRequest,
    ImageJobsEnqueueResponse,
    ImageJobsListResponse,
    ImageJobsRunRequest,
    ImageJobsRunResponse,
    ImageJobsRetryRequest,
    ImageJobsRetryResponse,
    ImageJobsSyncManualResponse,
    ImageSamplePackListResponse,
    LyricsPolishRequest,
    LyricsPolishResponse,
    LyricsSunoCheckRequest,
    LyricsSunoCheckResponse,
    MusicPlanPreflightRequest,
    MusicPlanPreflightResponse,
    MusicDownloadSyncItem,
    MusicDownloadSyncResponse,
    MusicHistoryListResponse,
    MusicLanguageListResponse,
    SunoBlocklistRuntimeResponse,
    OperationCostsResponse,
    QuotaStatusResponse,
    PendingMusicDownloadsResponse,
    ProgressFilters,
    ProgressListResponse,
    ProgressLocalSyncItem,
    ProgressLocalSyncResponse,
    PromptNameOption,
    ReservationActionResponse,
    StartYouTubeConnectionResponse,
    UserSettingsResponse,
    ValidateLicenseResponse,
    YouTubeConnectionResponse,
    YouTubeConnectionsResponse,
    YouTubePlaylistsResponse,
)
from shared.services.platform_client import PlatformApiError, PlatformClient


class PlatformApi:
    """Typed wrapper around platform_api REST endpoints."""

    def __init__(self, client: PlatformClient | None = None) -> None:
        self._client = client or PlatformClient()

    @property
    def client(self) -> PlatformClient:
        return self._client

    def login(self, email: str, password: str) -> TokenResponse:
        payload = LoginRequest(email=email, password=password)
        data = self._client.request(
            "/auth/login",
            method="POST",
            body=payload.model_dump(),
        )
        return TokenResponse.model_validate(data)

    def register(self, email: str, password: str, display_name: str) -> dict[str, Any]:
        return self._client.request(
            "/auth/register",
            method="POST",
            body={
                "email": email,
                "password": password,
                "display_name": display_name,
            },
        )

    def refresh(self, refresh_token: str) -> TokenResponse:
        data = self._client.request(
            "/auth/refresh",
            method="POST",
            body={"refresh_token": refresh_token},
        )
        return TokenResponse.model_validate(data)

    def logout(self) -> dict[str, Any]:
        result = self._client.request("/auth/logout", method="POST", auth=True)
        return result or {"message": "ok"}

    def get_me(self) -> UserMeResponse:
        data = self._client.request("/users/me", auth=True)
        return UserMeResponse.model_validate(data)

    def list_profiles(self) -> list[ProfileResponse]:
        data = self._client.request("/profiles", auth=True, timeout=60.0)
        if not isinstance(data, list):
            return []
        profiles: list[ProfileResponse] = []
        for item in data:
            try:
                profiles.append(ProfileResponse.model_validate(item))
            except ValidationError:
                continue
        return profiles

    def create_profile(self, payload: CreateProfileRequest) -> ProfileResponse:
        data = self._client.request(
            "/profiles",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
        )
        return ProfileResponse.model_validate(data)

    def update_profile(self, profile_id: str, payload: UpdateProfileRequest) -> ProfileResponse:
        data = self._client.request(
            f"/profiles/{profile_id}",
            method="PUT",
            auth=True,
            body=payload.model_dump(exclude_none=True),
        )
        return ProfileResponse.model_validate(data)

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        result = self._client.request(f"/profiles/{profile_id}", method="DELETE", auth=True)
        return result or {"message": "Deleted the selected profile."}

    def get_dashboard_stats(self) -> DashboardStatsResponse:
        data = self._client.request("/stats/dashboard", auth=True)
        return DashboardStatsResponse.model_validate(data)

    def validate_license(self) -> ValidateLicenseResponse | None:
        try:
            data = self._client.request("/licenses/validate", auth=True)
            return ValidateLicenseResponse.model_validate(data)
        except PlatformApiError as exc:
            if exc.status == 404:
                return None
            raise

    def get_dashboard_overview(
        self,
        *,
        me: UserMeResponse | None = None,
        profiles: list[ProfileResponse] | None = None,
    ) -> DashboardOverview:
        """Build dashboard overview, reusing cached me/profiles when provided.

        License + stats are fetched in parallel so the page is not blocked by
        four sequential round-trips.
        """
        from concurrent.futures import ThreadPoolExecutor

        resolved_me = me
        resolved_profiles = list(profiles) if profiles is not None else None
        license_info: ValidateLicenseResponse | None = None
        stats = DashboardStatsResponse()
        quota: QuotaStatusResponse | None = None

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures: dict[str, object] = {}
            if resolved_me is None:
                futures["me"] = pool.submit(self.get_me)
            if resolved_profiles is None:
                futures["profiles"] = pool.submit(self.list_profiles)
            futures["license"] = pool.submit(self.validate_license)
            futures["stats"] = pool.submit(self.get_dashboard_stats)
            futures["quota"] = pool.submit(self.get_quota_status)

            if "me" in futures:
                resolved_me = futures["me"].result()  # type: ignore[union-attr]
            if "profiles" in futures:
                try:
                    resolved_profiles = futures["profiles"].result()  # type: ignore[union-attr]
                except PlatformApiError:
                    resolved_profiles = []
            try:
                license_info = futures["license"].result()  # type: ignore[union-attr]
            except PlatformApiError:
                license_info = None
            try:
                stats = futures["stats"].result()  # type: ignore[union-attr]
            except PlatformApiError:
                stats = DashboardStatsResponse()
            try:
                quota = futures["quota"].result()  # type: ignore[union-attr]
            except PlatformApiError:
                quota = None

        assert resolved_me is not None
        return DashboardOverview(
            me=resolved_me,
            profiles=list(resolved_profiles or []),
            license=license_info,
            stats=stats,
            quota=quota,
        )

    def list_progress(self, filters: ProgressFilters | None = None) -> ProgressListResponse:
        resolved = filters or ProgressFilters()
        params: dict[str, Any] = {
            "limit": resolved.limit,
            "active_only": resolved.active_only,
        }
        if resolved.from_date:
            params["from_date"] = resolved.from_date
        if resolved.to_date:
            params["to_date"] = resolved.to_date
        data = self._client.request("/progress", auth=True, params=params, timeout=90.0)
        return ProgressListResponse.model_validate(data)

    def sync_local_progress(self, items: list[ProgressLocalSyncItem]) -> ProgressLocalSyncResponse:
        data = self._client.request(
            "/progress/sync-local",
            method="POST",
            auth=True,
            body={"items": [item.model_dump(exclude_none=True) for item in items]},
        )
        return ProgressLocalSyncResponse.model_validate(data)

    def get_settings(self) -> UserSettingsResponse:
        data = self._client.request("/settings", auth=True, timeout=60.0)
        return UserSettingsResponse.model_validate(data)

    def patch_settings(self, patch: dict[str, object]) -> UserSettingsResponse:
        data = self._client.request("/settings", method="PATCH", auth=True, body=patch)
        return UserSettingsResponse.model_validate(data)

    def list_prompt_description_names(self) -> list[PromptNameOption]:
        data = self._client.request("/prompts/descriptions/workspace", auth=True)
        if not isinstance(data, list):
            return []
        return [
            PromptNameOption.model_validate(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "isOwned": item.get("is_owned", False),
                    "vocal_mode": item.get("vocal_mode"),
                    "default_secondary_language": item.get("default_secondary_language"),
                }
            )
            for item in data
            if isinstance(item, dict)
        ]

    def list_prompt_structure_names(self) -> list[PromptNameOption]:
        data = self._client.request("/prompts/structures/workspace", auth=True)
        if not isinstance(data, list):
            return []
        return [
            PromptNameOption.model_validate(
                {"id": item["id"], "name": item["name"], "isOwned": item.get("is_owned", False)}
            )
            for item in data
            if isinstance(item, dict)
        ]

    def list_prompt_mood_names(self) -> list[PromptNameOption]:
        data = self._client.request("/prompts/moods/workspace", auth=True)
        if not isinstance(data, list):
            return []
        return [
            PromptNameOption.model_validate(
                {"id": item["id"], "name": item["name"], "isOwned": item.get("is_owned", False)}
            )
            for item in data
            if isinstance(item, dict)
        ]

    def list_my_descriptions(self) -> list[dict[str, object]]:
        data = self._client.request("/prompts/me/descriptions", auth=True)
        return data if isinstance(data, list) else []

    def list_my_structures(self) -> list[dict[str, object]]:
        data = self._client.request("/prompts/me/structures", auth=True)
        return data if isinstance(data, list) else []

    def list_my_moods(self) -> list[dict[str, object]]:
        data = self._client.request("/prompts/me/moods", auth=True)
        return data if isinstance(data, list) else []

    def create_my_description(self, *, name: str, content: str) -> dict[str, object]:
        data = self._client.request(
            "/prompts/me/descriptions",
            method="POST",
            auth=True,
            body={"name": name, "content": content},
        )
        return data if isinstance(data, dict) else {}

    def update_my_description(self, prompt_id: str, *, name: str, content: str) -> dict[str, object]:
        data = self._client.request(
            f"/prompts/me/descriptions/{prompt_id}",
            method="PUT",
            auth=True,
            body={"name": name, "content": content},
        )
        return data if isinstance(data, dict) else {}

    def delete_my_description(self, prompt_id: str) -> None:
        self._client.request(
            f"/prompts/me/descriptions/{prompt_id}",
            method="DELETE",
            auth=True,
        )

    def create_my_structure(self, *, name: str, content: str) -> dict[str, object]:
        data = self._client.request(
            "/prompts/me/structures",
            method="POST",
            auth=True,
            body={"name": name, "content": content},
        )
        return data if isinstance(data, dict) else {}

    def update_my_structure(self, prompt_id: str, *, name: str, content: str) -> dict[str, object]:
        data = self._client.request(
            f"/prompts/me/structures/{prompt_id}",
            method="PUT",
            auth=True,
            body={"name": name, "content": content},
        )
        return data if isinstance(data, dict) else {}

    def delete_my_structure(self, prompt_id: str) -> None:
        self._client.request(
            f"/prompts/me/structures/{prompt_id}",
            method="DELETE",
            auth=True,
        )

    def create_my_mood(self, *, name: str, content: str) -> dict[str, object]:
        data = self._client.request(
            "/prompts/me/moods",
            method="POST",
            auth=True,
            body={"name": name, "content": content},
        )
        return data if isinstance(data, dict) else {}

    def update_my_mood(self, prompt_id: str, *, name: str, content: str) -> dict[str, object]:
        data = self._client.request(
            f"/prompts/me/moods/{prompt_id}",
            method="PUT",
            auth=True,
            body={"name": name, "content": content},
        )
        return data if isinstance(data, dict) else {}

    def delete_my_mood(self, prompt_id: str) -> None:
        self._client.request(
            f"/prompts/me/moods/{prompt_id}",
            method="DELETE",
            auth=True,
        )

    def list_music_history(
        self,
        *,
        limit: int = 25,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> MusicHistoryListResponse:
        params: dict[str, object] = {"limit": max(1, min(100, int(limit)))}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        data = self._client.request("/music/history", auth=True, params=params)
        return MusicHistoryListResponse.model_validate(data)

    def list_music_languages(self) -> MusicLanguageListResponse:
        data = self._client.request("/music/languages", auth=True)
        return MusicLanguageListResponse.model_validate(data)

    def get_suno_blocklist(self) -> SunoBlocklistRuntimeResponse:
        data = self._client.request("/generation/suno-blocklist", auth=True)
        return SunoBlocklistRuntimeResponse.model_validate(data)

    def get_operation_costs(self) -> OperationCostsResponse:
        data = self._client.request("/credits/operation-costs", auth=True)
        return OperationCostsResponse.model_validate(data)

    def generate_draft(self, payload: DraftGenerationRequest) -> DraftGenerationResponse:
        data = self._client.request(
            "/generation/draft",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
            timeout=300.0,
        )
        return DraftGenerationResponse.model_validate(data)

    def polish_lyrics(self, payload: LyricsPolishRequest) -> LyricsPolishResponse:
        data = self._client.request(
            "/generation/polish-lyrics",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
            timeout=300.0,
        )
        return LyricsPolishResponse.model_validate(data)

    def check_lyrics_suno(self, payload: LyricsSunoCheckRequest) -> LyricsSunoCheckResponse:
        data = self._client.request(
            "/generation/lyrics-suno-check",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
            timeout=30.0,
        )
        return LyricsSunoCheckResponse.model_validate(data)

    def create_batch(self, payload: BatchCreateRequest) -> BatchCreateResponse:
        data = self._client.request(
            "/batches",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
        )
        return BatchCreateResponse.model_validate(data)

    def preflight_music_plan(self, payload: MusicPlanPreflightRequest) -> MusicPlanPreflightResponse:
        data = self._client.request(
            "/batches/preflight",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
        )
        return MusicPlanPreflightResponse.model_validate(data)

    def get_quota_status(self) -> QuotaStatusResponse:
        data = self._client.request("/credits/quota-status", auth=True)
        return QuotaStatusResponse.model_validate(data)

    def consume_local_video(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._client.request(
            "/generation/video/consume",
            method="POST",
            auth=True,
            body=payload,
        )
        return data if isinstance(data, dict) else dict(data)

    def refund_local_video(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._client.request(
            "/generation/video/refund",
            method="POST",
            auth=True,
            body=payload,
        )
        return data if isinstance(data, dict) else dict(data)

    def report_local_video_telemetry(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._client.request(
            "/generation/video/telemetry",
            method="POST",
            auth=True,
            body=payload,
        )
        return data if isinstance(data, dict) else dict(data)

    def get_batch_status(self, batch_id: str) -> BatchStatusResponse:
        data = self._client.request(f"/batches/{batch_id}", auth=True)
        return BatchStatusResponse.model_validate(data)

    def delete_batch(self, batch_id: str) -> BatchDeleteResponse:
        data = self._client.request(
            f"/batches/{batch_id}",
            method="DELETE",
            auth=True,
        )
        return BatchDeleteResponse.model_validate(data)

    def retry_song_draft(self, batch_id: str, song_id: str) -> SongRetryResponse:
        data = self._client.request(
            f"/batches/{batch_id}/songs/{song_id}/retry-draft",
            method="POST",
            auth=True,
        )
        return SongRetryResponse.model_validate(data)

    def rewrite_batch_album(self, batch_id: str, *, role: str = "ok") -> AlbumRewriteResponse:
        data = self._client.request(
            f"/batches/{batch_id}/rewrite-album",
            method="POST",
            auth=True,
            body={"role": role},
        )
        return AlbumRewriteResponse.model_validate(data)

    def rewrite_song_title(self, batch_id: str, song_id: str) -> TitleRewriteResponse:
        data = self._client.request(
            f"/batches/{batch_id}/songs/{song_id}/rewrite-title",
            method="POST",
            auth=True,
        )
        return TitleRewriteResponse.model_validate(data)

    def retry_song_suno(
        self,
        batch_id: str,
        song_id: str,
        *,
        title: str | None = None,
        album: str | None = None,
        lyrics: str | None = None,
    ) -> SongRetryResponse:
        body: dict[str, str] = {}
        if title is not None:
            body["title"] = title
        if album is not None:
            body["album"] = album
        if lyrics is not None:
            body["lyrics"] = lyrics
        data = self._client.request(
            f"/batches/{batch_id}/songs/{song_id}/retry-suno",
            method="POST",
            auth=True,
            body=body or None,
        )
        return SongRetryResponse.model_validate(data)

    def claim_content_pool_item(
        self,
        kind: str,
        *,
        reservation_token: str | None = None,
        consumer: str = "music-draft",
    ) -> ClaimContentPoolResponse:
        body: dict[str, object] = {"consumer": consumer}
        if reservation_token:
            body["reservation_token"] = reservation_token
        data = self._client.request(
            f"/content-pools/{kind}/claim",
            method="POST",
            auth=True,
            body=body,
        )
        return ClaimContentPoolResponse.model_validate(data)

    def finalize_content_pool_item(self, kind: str, *, item_id: int, reservation_token: str) -> ReservationActionResponse:
        data = self._client.request(
            f"/content-pools/{kind}/finalize",
            method="POST",
            auth=True,
            body={"item_id": item_id, "reservation_token": reservation_token},
        )
        return ReservationActionResponse.model_validate(data)

    def release_content_pool_item(self, kind: str, *, item_id: int, reservation_token: str) -> ReservationActionResponse:
        data = self._client.request(
            f"/content-pools/{kind}/release",
            method="POST",
            auth=True,
            body={"item_id": item_id, "reservation_token": reservation_token},
        )
        return ReservationActionResponse.model_validate(data)

    def sync_music_downloads(self, items: list[MusicDownloadSyncItem]) -> MusicDownloadSyncResponse:
        data = self._client.request(
            "/music/downloads/sync",
            method="POST",
            auth=True,
            body={"items": [item.model_dump(exclude_none=True) for item in items]},
        )
        return MusicDownloadSyncResponse.model_validate(data)

    def list_pending_music_downloads(self, *, limit: int = 12) -> PendingMusicDownloadsResponse:
        data = self._client.request(
            "/music/downloads/pending",
            auth=True,
            params={"limit": limit},
        )
        return PendingMusicDownloadsResponse.model_validate(data)

    def get_batch_redownload_plan(
        self, *, batch_id: str, role: str, run_dir: str
    ) -> BatchRedownloadPlanResponse:
        """Already-successful Suno audio for one batch/channel, targeted at a new folder.

        Used by "change run folder + resume" — ignores the account's `downloaded_*`
        flags, since those tracked a download into a folder we're now moving away from.
        """
        data = self._client.request(
            "/music/downloads/batch-redownload-plan",
            method="POST",
            auth=True,
            body={"batch_id": batch_id, "role": role, "run_dir": run_dir},
        )
        return BatchRedownloadPlanResponse.model_validate(data)

    def sync_manual_image_jobs(self, batch_id: str) -> ImageJobsSyncManualResponse:
        data = self._client.request(
            "/image-jobs/sync-manual",
            method="POST",
            auth=True,
            body={"batch_id": batch_id},
        )
        return ImageJobsSyncManualResponse.model_validate(data)

    def enqueue_image_jobs(self, batch_ids: list[str]) -> ImageJobsEnqueueResponse:
        data = self._client.request(
            "/image-jobs/enqueue",
            method="POST",
            auth=True,
            body=ImageJobsEnqueueRequest(batch_ids=batch_ids).model_dump(),
        )
        return ImageJobsEnqueueResponse.model_validate(data)

    def list_image_jobs(
        self,
        *,
        batch_id: str | None = None,
        status: list[str] | None = None,
        limit: int = 200,
    ) -> ImageJobsListResponse:
        params: dict[str, object] = {"limit": limit}
        if batch_id:
            params["batch_id"] = batch_id
        if status:
            params["status"] = status
        data = self._client.request("/image-jobs", auth=True, params=params)
        return ImageJobsListResponse.model_validate(data)

    def get_image_job_output(self, job_id: str) -> bytes:
        return self._client.request_bytes(f"/image-jobs/{job_id}/output", auth=True)

    def run_image_jobs(self, payload: ImageJobsRunRequest | None = None) -> ImageJobsRunResponse:
        body = (payload or ImageJobsRunRequest()).model_dump(exclude_none=True)
        data = self._client.request(
            "/image-jobs/run",
            method="POST",
            auth=True,
            body=body,
        )
        return ImageJobsRunResponse.model_validate(data)

    def retry_image_jobs(self, payload: ImageJobsRetryRequest) -> ImageJobsRetryResponse:
        data = self._client.request(
            "/image-jobs/retry",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
        )
        return ImageJobsRetryResponse.model_validate(data)

    def clear_image_jobs(self, payload: ImageJobsClearRequest) -> ImageJobsClearResponse:
        data = self._client.request(
            "/image-jobs/clear",
            method="POST",
            auth=True,
            body=payload.model_dump(exclude_none=True),
        )
        return ImageJobsClearResponse.model_validate(data)

    def list_youtube_connections(self) -> list[YouTubeConnectionResponse]:
        data = self._client.request("/youtube/connections", auth=True)
        if isinstance(data, dict):
            response = YouTubeConnectionsResponse.model_validate(data)
            return response.connections
        if isinstance(data, list):
            return [YouTubeConnectionResponse.model_validate(item) for item in data]
        return []

    def start_youtube_connection(self, profile_id: str) -> StartYouTubeConnectionResponse:
        data = self._client.request(
            f"/youtube/profiles/{profile_id}/connect",
            method="POST",
            auth=True,
        )
        return StartYouTubeConnectionResponse.model_validate(data)

    def select_youtube_channel(self, session_id: str, channel_id: str) -> YouTubeConnectionResponse:
        data = self._client.request(
            f"/youtube/connect-sessions/{session_id}/select-channel",
            method="POST",
            auth=True,
            body={"channel_id": channel_id},
        )
        return YouTubeConnectionResponse.model_validate(data)

    def disconnect_youtube_connection(self, profile_id: str) -> dict[str, Any]:
        result = self._client.request(
            f"/youtube/profiles/{profile_id}/connection",
            method="DELETE",
            auth=True,
        )
        return result or {"message": "YouTube channel disconnected."}

    def resync_youtube_connection(self, profile_id: str) -> YouTubeConnectionResponse:
        data = self._client.request(
            f"/youtube/profiles/{profile_id}/resync",
            method="POST",
            auth=True,
        )
        return YouTubeConnectionResponse.model_validate(data)

    def list_youtube_playlists(self, profile_id: str) -> YouTubePlaylistsResponse:
        data = self._client.request(f"/youtube/profiles/{profile_id}/playlists", auth=True)
        return YouTubePlaylistsResponse.model_validate(data)

    def get_content_pool_stats(self) -> ContentPoolStatsResponse:
        data = self._client.request("/content-pools/stats", auth=True)
        return ContentPoolStatsResponse.model_validate(data)

    def list_content_pool_items(
        self,
        kind: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> ContentPoolListResponse:
        data = self._client.request(
            f"/content-pools/{kind}",
            auth=True,
            params={"limit": limit, "offset": offset},
        )
        return ContentPoolListResponse.model_validate(data)

    def list_image_sample_packs(self) -> ImageSamplePackListResponse:
        data = self._client.request("/image-sample-packs", auth=True)
        return ImageSamplePackListResponse.model_validate(data)

    def download_profile_logo(self, profile_id: str) -> bytes:
        return self._client.request_bytes(f"/media/channel-profiles/{profile_id}/logo", auth=True)

    def download_profile_cover(self, profile_id: str, index: int = 0) -> bytes:
        return self._client.request_bytes(
            f"/media/channel-profiles/{profile_id}/covers/{int(index)}",
            auth=True,
        )

    def upsert_profile_video_template(
        self,
        profile_id: str,
        template_id: str,
        *,
        name: str,
        kind: str,
        template_json: dict[str, Any],
        set_as_profile_default: bool = True,
        source: str = "user",
    ) -> dict[str, Any]:
        data = self._client.request(
            f"/profiles/{profile_id}/video-templates/{template_id}",
            method="PUT",
            auth=True,
            body={
                "name": name,
                "kind": kind,
                "template_json": template_json,
                "source": source,
                "set_as_profile_default": set_as_profile_default,
            },
        )
        return data if isinstance(data, dict) else {}

    def upload_client_logs(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._client.request(
            "/client-logs",
            method="POST",
            auth=True,
            body=payload,
        )
        return data if isinstance(data, dict) else {}
