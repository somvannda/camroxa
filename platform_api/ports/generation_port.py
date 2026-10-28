"""Generation service protocol interface.

Defines the contract for AI generation operations including Suno music
generation, image generation, and LLM-based song draft generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SunoRequest:
    """Parameters for a Suno music generation request."""

    model: str  # 'V6', 'V6_MINI', 'V6_WILD', 'V5_5', or 'V5'
    title: str
    lyrics: str
    style: str
    instrumental: bool = False
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = None
    weirdness_constraint: float | None = None
    audio_weight: float | None = None
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    persona_id: str | None = None
    persona_model: str | None = None


@dataclass(frozen=True, slots=True)
class ImageRequest:
    """Parameters for an image generation request."""

    prompt: str
    provider: str  # 'fal' or 'slai'
    model_id: str | None = None
    resolution: str = "1920x1080"
    style_strength: float = 0.6
    base_image: bytes | None = None  # optional base64-decoded source image


@dataclass(frozen=True, slots=True)
class DraftRequest:
    """Parameters for an LLM song draft generation request."""

    language: str
    creativity_level: int  # 0-100
    description: str
    structure: str
    mood: str = ""
    secondary_language: str | None = None
    vocal_profile: dict[str, Any] | None = None
    avoid_titles: list[str] = field(default_factory=list)
    avoid_albums: list[str] = field(default_factory=list)
    avoid_openings: list[str] = field(default_factory=list)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None
    title_seed: str | None = None
    album_seed: str | None = None
    batch_id: str | None = None
    song_number: int | None = None
    song_id: str | None = None
    structure_mode: str = "template"
    # AI Structure diversity (genres + soft layout seed; not production description text)
    description_genres: list[str] = field(default_factory=list)
    preferred_structure_layout: str | None = None
    avoid_structures: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SongDraft:
    """Generated song draft returned by the LLM provider."""

    title: str
    album: str
    lyrics: str


class GenerationServicePort(Protocol):
    """Port for AI generation orchestration.

    Implementations handle forwarding requests to external AI services
    (Suno, Fal AI, SLAI, DeepSeek) with credit deduction and error handling.
    """

    async def submit_suno(
        self,
        user_id: str,
        request: SunoRequest,
        *,
        skip_pricing: bool = False,
    ) -> str:
        """Submit a music generation request to Suno.

        Returns the Suno-assigned task ID on successful submission.
        Performs duplicate detection via request hash before submitting.
        Raises InsufficientCreditsError if the user's balance is too low.
        Raises ExternalServiceError if Suno is unreachable or returns an error.
        """
        ...

    async def submit_image(
        self,
        user_id: str,
        request: ImageRequest,
        *,
        skip_pricing: bool = False,
    ) -> bytes:
        """Submit an image generation request to the configured provider.

        Returns the generated image as PNG bytes.
        Raises InsufficientCreditsError if the user's balance is too low.
        Raises ExternalServiceError if the provider fails.
        """
        ...

    async def submit_draft(
        self,
        user_id: str,
        request: DraftRequest,
        *,
        provider: str,
        model: str,
        skip_pricing: bool = False,
    ) -> SongDraft:
        """Generate a song draft (title, album, lyrics) via LLM.

        Validates lyrics structure and title/album uniqueness against avoid lists.
        Retries up to configured maximum attempts on validation failures.
        Raises InsufficientCreditsError if the user's balance is too low.
        Raises ExternalServiceError if the LLM provider fails after all retries.
        """
        ...
