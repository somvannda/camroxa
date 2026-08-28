"""DTOs for the web-music Create APIs used by the desktop Create page."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WebMusicQuotaResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit: int = 0
    used: int = 0
    remaining: int = 0
    is_pro: bool = False
    requires_upgrade: bool = False
    can_download: bool = False
    has_subscription: bool = False
    queue_limit: int = 2
    queue_used: int = 0
    credits_remaining: int | None = None
    credits_per_song: int | None = None


class WebMusicGenerateRequest(BaseModel):
    mode: str = "advanced"
    lyrics: str = ""
    style: str = ""
    title: str = ""
    prompt: str = ""
    instrumental: bool = False
    model: str = "V5_5"
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = None
    weirdness_constraint: float | None = None
    audio_weight: float | None = None
    workspace_id: str | None = None


class WebMusicGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    status: str
    title: str = ""
    style: str = ""
    quota: WebMusicQuotaResponse = Field(default_factory=WebMusicQuotaResponse)


class WebMusicClipResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    variant: str
    label: str = ""
    audio_url: str = ""
    download_url: str = ""
    ready: bool = False
    package_status: str = "none"
    image_url: str | None = None
    duration_seconds: float | None = None
    title: str = ""


class WebMusicGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str = ""
    lyrics: str = ""
    style: str = ""
    model: str = "V5"
    instrumental: bool = False
    status: str
    error_message: str | None = None
    created_at: str | None = None
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = None
    weirdness_constraint: float | None = None
    audio_weight: float | None = None
    clips: list[WebMusicClipResponse] = Field(default_factory=list)


class WebMusicGenerationListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[WebMusicGenerationResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 40
    offset: int = 0


class WebMusicDraftRequest(BaseModel):
    prompt: str


class WebMusicDraftResponse(BaseModel):
    lyrics: str = ""
    title: str = ""
