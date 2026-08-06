"""Desktop-side DTOs for video workspace and export state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VideoTemplateSummary(BaseModel):
    id: str
    name: str
    kind: str | None = None
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class PreviewAspectRatio(BaseModel):
    width: int = 16
    height: int = 9


class VideoPlaybackState(BaseModel):
    is_playing: bool = Field(default=False, alias="isPlaying")
    is_ready: bool = Field(default=False, alias="isReady")
    is_loading: bool = Field(default=False, alias="isLoading")
    current_time_sec: float = Field(default=0.0, alias="currentTimeSec")
    duration_sec: float = Field(default=0.0, alias="durationSec")

    model_config = {"populate_by_name": True}


class Mp3ListItem(BaseModel):
    name: str
    path: str


class VideoExportState(BaseModel):
    running: bool = False
    branch: str | None = None
    workers: int = 1
    fps: int = 24
    auto_merge: bool = Field(default=False, alias="autoMerge")
    shuffle_merge: bool = Field(default=False, alias="shuffleMerge")
    merge_running: bool = Field(default=False, alias="mergeRunning")
    merge_progress_percent: int | None = Field(default=None, alias="mergeProgressPercent")
    current_status: str = Field(default="", alias="currentStatus")
    output_dir: str | None = Field(default=None, alias="outputDir")
    current_output_path: str | None = Field(default=None, alias="currentOutputPath")
    total_jobs: int = Field(default=0, alias="totalJobs")
    completed_jobs: int = Field(default=0, alias="completedJobs")
    progress_percent: int | None = Field(default=None, alias="progressPercent")
    video_codec: str | None = Field(default=None, alias="videoCodec")
    estimated_remaining_sec: int | None = Field(default=None, alias="estimatedRemainingSec")
    started_at_ms: int | None = Field(default=None, alias="startedAtMs")
    last_output_path: str | None = Field(default=None, alias="lastOutputPath")
    last_merged_output_path: str | None = Field(default=None, alias="lastMergedOutputPath")

    model_config = {"populate_by_name": True}


class VideoWorkspaceUiState(BaseModel):
    preview_title: str = Field(default="Preview", alias="previewTitle")
    live_preview_open: bool = Field(default=False, alias="livePreviewOpen")
    source: str = "python-local"
    notes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class VideoWorkspaceState(BaseModel):
    template: dict[str, object] = Field(default_factory=dict)
    template_id: str | None = Field(default=None, alias="templateId")
    template_name: str = Field(default="No template loaded", alias="templateName")
    templates: list[VideoTemplateSummary] = Field(default_factory=list)
    output_resolution: str = Field(default="1920x1080", alias="outputResolution")
    preview_aspect_ratio: PreviewAspectRatio = Field(
        default_factory=PreviewAspectRatio,
        alias="previewAspectRatio",
    )
    background_path: str = Field(default="", alias="backgroundPath")
    logo_path: str = Field(default="", alias="logoPath")
    selected_mp3_path: str = Field(default="", alias="selectedMp3Path")
    mp3_directory: str = Field(default="", alias="mp3Directory")
    mp3_list: list[Mp3ListItem] = Field(default_factory=list, alias="mp3List")
    playback: VideoPlaybackState = Field(default_factory=VideoPlaybackState)
    export: VideoExportState = Field(default_factory=VideoExportState)
    ui: VideoWorkspaceUiState = Field(default_factory=VideoWorkspaceUiState)

    model_config = {"populate_by_name": True}
