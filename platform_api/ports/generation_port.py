"""Generation service protocol interface.

Defines the contract for AI generation operations including Suno music
generation, image generation, and LLM-based song draft generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SunoRequest:
    """Parameters for a Suno music generation request."""

    model: str  # 'V5' or 'V5_5'
    title: str
    lyrics: str
    style: str
    instrumental: bool = False


@dataclass(frozen=True, slots=True)
class ImageRequest:
    """Parameters for an image generation request."""

    prompt: str
    provider: str  # 'fal' or 'slai'
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
    avoid_titles: list[str] = field(default_factory=list)
    avoid_albums: list[str] = field(default_factory=list)
    avoid_openings: list[str] = field(default_factory=list)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None


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

    async def submit_suno(self, user_id: str, request: SunoRequest) -> str:
        """Submit a music generation request to Suno.

        Returns the Suno-assigned task ID on successful submission.
        Performs duplicate detection via request hash before submitting.
        Raises InsufficientCreditsError if the user's balance is too low.
        Raises ExternalServiceError if Suno is unreachable or returns an error.
        """
        ...

    async def submit_image(self, user_id: str, request: ImageRequest) -> bytes:
        """Submit an image generation request to the configured provider.

        Returns the generated image as PNG bytes.
        Raises InsufficientCreditsError if the user's balance is too low.
        Raises ExternalServiceError if the provider fails.
        """
        ...

    async def submit_draft(self, user_id: str, request: DraftRequest) -> SongDraft:
        """Generate a song draft (title, album, lyrics) via LLM.

        Validates lyrics structure and title/album uniqueness against avoid lists.
        Retries up to configured maximum attempts on validation failures.
        Raises InsufficientCreditsError if the user's balance is too low.
        Raises ExternalServiceError if the LLM provider fails after all retries.
        """
        ...
