"""Auth and platform API DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthTokens(BaseModel):
    """Stored session tokens — matches Electron sessionStore camelCase JSON."""

    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"
    expiresAt: int

    @classmethod
    def from_token_response(cls, response: TokenResponse) -> AuthTokens:
        import time

        expires_at = int(time.time() * 1000) + max(0, response.expires_in) * 1000
        return cls(
            accessToken=response.access_token,
            refreshToken=response.refresh_token,
            tokenType=response.token_type,
            expiresAt=expires_at,
        )


class UserMeResponse(BaseModel):
    id: str
    email: str
    email_confirmed: bool
    display_name: str
    credit_balance: float
    plan_name: str | None = None
    role: str | None = None
    onboarding_paid: bool = False
    profile_allowance: int | None = None
    profile_addon_slots: int = 0
    profile_addon_pending: int = 0
    effective_profile_allowance: int | None = None
    effective_quota_channels: int | None = None
    channel_profile_count: int = 0

    model_config = {"extra": "ignore"}


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str | None = None
    image_config: dict[str, object] | None = None
    youtube_config: dict[str, object] | None = None

    model_config = {"extra": "allow"}


class CreateProfileRequest(BaseModel):
    name: str
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    logo_base64: str | None = None
    cover_images: list[str] = Field(default_factory=list)
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str | None = "1920x1080"
    image_config: dict[str, object] | None = None
    youtube_config: dict[str, object] | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    logo_base64: str | None = None
    cover_images: list[str] | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str | None = None
    image_config: dict[str, object] | None = None
    youtube_config: dict[str, object] | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = Field(alias="displayName")

    model_config = {"populate_by_name": True}


class RefreshRequest(BaseModel):
    refresh_token: str


class PublicPlanOffer(BaseModel):
    id: str
    promo_price_cents: int
    max_redemptions: int = 0
    current_redemptions: int = 0
    remaining_redemptions: int = 0
    is_active: bool = True


class PublicPlanTermDiscounts(BaseModel):
    semi_annual_discount_percent: int = 15
    annual_discount_percent: int = 25


class PublicPlan(BaseModel):
    """Public catalog plan from GET /plans/public (API v3)."""

    id: str
    name: str
    price_cents: int
    effective_price_cents: int = 0
    billing_cycle_days: int | None = None
    profile_allowance: int = 0
    monthly_song_limit: int | None = None
    monthly_image_limit: int | None = None
    monthly_draft_limit: int | None = None
    monthly_video_limit: int | None = None
    monthly_merge_limit: int | None = None
    daily_song_limit_per_channel: int = 0
    daily_image_limit_per_channel: int = 0
    monthly_credits: int = 0
    daily_credits: int = 0
    pricing_features: list[str] = Field(default_factory=list)
    pricing_credit_lines: list[str] = Field(default_factory=list)
    credits_per_generate: float = 10
    offer: PublicPlanOffer | None = None

    model_config = {"extra": "ignore"}


class WebMusicSubscriptionPlan(BaseModel):
    """Public paid plan for the desktop Choose Your Plan dialog."""

    id: str
    name: str
    price_cents: int
    billing_cycle: str = "monthly"
    monthly_credits: int = 0
    credits_per_generate: float = 10
    features: list[str] = Field(default_factory=list)
    display_order: int = 0
    is_public: bool = True

    model_config = {"extra": "ignore"}
