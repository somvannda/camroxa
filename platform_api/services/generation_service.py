"""Generation service implementing GenerationServicePort.

Orchestrates song draft generation (LLM), Suno music generation,
and image generation with credit deduction, validation, and error handling.

Requirements: 10.1, 10.3, 10.4, 10.5, 10.6, 10.7, 11.1, 11.5, 11.7,
              12.1, 12.2, 12.5, 12.6, 7.1, 7.2, 7.3, 7.6, 8.1, 8.2, 8.3
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx

from platform_api.ai.models import TextRouting
from platform_api.ai.parsing.response_parser import extract_chat_content
from platform_api.ai.purposes.channel_text import parse_title_album_lyrics
from platform_api.ai.purposes.draft_routing import DraftRouting
from platform_api.ai.types import is_suno_lyric_routing
from platform_api.models.billing_context import DraftBillingContext
from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    NoAvailableKeysError,
    ValidationError,
)
from platform_api.models.domain import SunoTask
from platform_api.models.enums import TaskStatus
from platform_api.ports.generation_port import (
    DraftRequest,
    ImageRequest,
    SongDraft,
    SunoRequest,
)
from platform_api.ports.key_pool_service_port import KeyPoolServicePort
from platform_api.services import image_progress_log as image_log
from platform_api.services.image_provider_retry import (
    compute_retry_delay_seconds,
    provider_max_attempts,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DRAFT_ATTEMPTS = 8
MAX_LYRIC_ATTEMPTS = 3
MAX_LYRIC_SHAPE_ATTEMPTS = 2
MAX_TITLE_ATTEMPTS = 2
MAX_ALBUM_ATTEMPTS = 2
MAX_TITLE_ALBUM_ATTEMPTS = 6
IMAGE_MIN_RESOLUTION = 512
IMAGE_MAX_RESOLUTION = 2048
IMAGE_MAX_PROMPT_LENGTH = 5000
IMAGE_MAX_BASE64_BYTES = 10 * 1024 * 1024  # 10 MB
CHANNEL_COVER_ALLOWED_RESOLUTION = (1920, 1080)

ImageProviderChain = list[tuple[str, str | None]]


@dataclass(frozen=True)
class ImageGenerationOutcome:
    """Result of a routed image generation call."""

    image_bytes: bytes
    provider: str
    sub_model: str | None


# ---------------------------------------------------------------------------
# Repository / Client Protocols
# ---------------------------------------------------------------------------


class CreditServiceProtocol(Protocol):
    """Minimal protocol for credit deduction and refund operations."""

    async def deduct(
        self,
        user_id: str,
        amount: int,
        reason: str,
        ref_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        ...

    async def refund(
        self,
        user_id: str,
        amount: int,
        reason: str,
        ref_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...

    async def patch_transaction_metadata(
        self,
        user_id: str,
        ref_id: str,
        patch: dict[str, Any],
    ) -> bool:
        ...


class CreditPricingRepository(Protocol):
    """Looks up per-service credit pricing."""

    async def get_price(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str | None = None,
    ) -> int | None:
        ...


class TaskRepository(Protocol):
    """Minimal protocol for Suno task persistence."""

    async def find_by_hash(self, user_id: UUID, request_hash: str) -> SunoTask | None:
        ...

    async def create(self, task: SunoTask) -> SunoTask:
        ...


class LlmClientProtocol(Protocol):
    """Minimal protocol for the LLM client."""

    async def generate_song_draft(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> dict[str, Any]:
        ...


class SunoClientProtocol(Protocol):
    """Minimal protocol for the Suno client."""

    async def submit_task(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool,
        callback_url: str | None,
    ) -> dict[str, Any]:
        ...


class FalClientProtocol(Protocol):
    """Minimal protocol for the Fal AI image client."""

    async def generate_image(
        self,
        *,
        prompt: str,
        model_id: str,
        width: int,
        height: int,
        num_images: int,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ...


class SlaiClientProtocol(Protocol):
    """Minimal protocol for the SLAI image client."""

    async def generate_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        style_strength: float,
        reference_image_base64: str | None,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# Pure Helper Functions
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """Normalize text for avoid-list comparison.

    Lowercases, strips whitespace, removes accents, and collapses spaces.
    """
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text


_SECTION_HEADER_RE = re.compile(r"^\[(.+)\]$", re.IGNORECASE)

STRUCTURE_MODE_TEMPLATE = "template"
STRUCTURE_MODE_AI_FREE = "ai_free"
STRUCTURE_MODE_SUNO = "suno"
FREE_STRUCTURE_MODES = frozenset({STRUCTURE_MODE_AI_FREE, STRUCTURE_MODE_SUNO})
AI_STRUCTURE_SENTINEL = "__ai_structure__"
SUNO_STRUCTURE_SENTINEL = "__suno_structure__"
AI_STRUCTURE_MIN_CONTENT_LINES = 16
AI_STRUCTURE_MIN_SECTION_HEADERS = 2


def is_free_structure_mode(structure_mode: str | None) -> bool:
    """True when lyrics keep provider section headers (AI Structure or Suno Structure)."""
    return str(structure_mode or "").strip() in FREE_STRUCTURE_MODES
_SECTION_KEY_SYNONYMS: dict[str, str] = {
    "hook": "chorus",
    "refrain": "chorus",
    "chorus hook": "chorus",
}
_SECTION_LINE_WEIGHTS: dict[str, float] = {
    "intro": 1.0,
    "outro": 1.0,
    "break": 1.0,
    "interlude": 1.0,
    "bridge": 1.5,
    "build-up": 1.5,
    "buildup": 1.5,
    "pre-chorus": 1.5,
    "verse": 2.0,
    "chorus": 2.5,
    "drop": 3.0,
    "final drop": 3.5,
}
_DEFAULT_SECTION_LINE_WEIGHT = 2.0
_META_TAIL_LINE_RE = re.compile(
    r"(^---+$|^\*\*.*\*\*$|.*\b(do not repeat|end mark|remaining through|"
    r"audio void|boat block|ok cut|cut\.|aus fade|silence shorter|"
    r"sign\. cut|error--|only low noise|au revoir)\b)",
    re.IGNORECASE,
)


def strip_trailing_lyric_meta_tail(text: str) -> str:
    """Drop model commentary / production notes after the lyric body."""
    clean_lines: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue
        if _META_TAIL_LINE_RE.search(stripped):
            break
        clean_lines.append(line)

    while clean_lines and not clean_lines[-1].strip():
        clean_lines.pop()
    while clean_lines and len(clean_lines[-1].strip()) <= 2:
        tail = clean_lines[-1].strip()
        if tail.isalpha() and len(tail) == 1:
            clean_lines.pop()
            continue
        break
    return "\n".join(clean_lines).strip()


_CORRUPT_LYRIC_LINE_RE = re.compile(
    r'(\{\s*$|^\s*\}\s*$|"lyrics"\s*:|please present|acting failure|token back|'
    r"accord override|unintelligense|\b8token\b|normal edit yes|short reply mode|"
    r"boat block|do not repeat dropped|end mark|remaining through|audio void|"
    r"only low noise|ok cut|aus fade|silence shorter|au revoir|"
    r"springapplication|jsonobject|githubusercontent|sanitize value forbidden|"
    r"graphql|jwt\b|deserialize|cjson|formattingenabled)",
    re.IGNORECASE,
)
_SCRIPT_CHAR_RE = re.compile(
    r"[\u0400-\u04ff\u0600-\u06ff\u0900-\u097f\u0e00-\u0e7f"
    r"\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]"
)
_REWRITE_MAX_INPUT_CHARS = 2200
_REWRITE_MAX_OUTPUT_CHARS = 4500
_REWRITE_MAX_LINE_CHARS = 160
_REWRITE_MAX_LINE_WORDS = 28


def _parse_bracket_header(line: str) -> str | None:
    match = _SECTION_HEADER_RE.match(line.strip())
    return match.group(1).strip() if match else None


def normalize_section_label(header_line: str) -> str:
    """Normalize a structure or lyric header to a comparable section label.

    Examples:
        [Verse] -> verse
        [Intro: dark pads] -> intro
        [Build-Up: risers] -> build-up
    """
    inner = _parse_bracket_header(header_line)
    if inner is None:
        inner = header_line.strip().strip("[]")
    if ":" in inner:
        inner = inner.split(":", 1)[0]
    return _normalize_text(inner.strip())


def _is_section_header_line(line: str) -> bool:
    return bool(_SECTION_HEADER_RE.match(str(line or "").strip()))


def _is_corrupt_lyric_line(line: str) -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return True
    if stripped.startswith("{") or stripped.startswith('"lyrics"'):
        return True
    if _CORRUPT_LYRIC_LINE_RE.search(stripped):
        return True
    if _SCRIPT_CHAR_RE.search(stripped) and len(_SCRIPT_CHAR_RE.findall(stripped)) >= 3:
        return True
    words = re.findall(r"[A-Za-z0-9']+", stripped)
    if len(stripped) > _REWRITE_MAX_LINE_CHARS or len(words) > _REWRITE_MAX_LINE_WORDS:
        # Run-on word-salad lines (common rewrite failure mode).
        return True
    return False


def prepare_lyrics_for_rewrite(lyrics: str) -> str:
    """Keep only coherent leading lyric body before corruption / word-salad tails."""
    text = strip_trailing_lyric_meta_tail(str(lyrics or "").strip())
    if not text:
        return ""

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if kept and kept[-1].strip():
                kept.append("")
            continue
        if _is_section_header_line(stripped):
            kept.append(stripped)
            continue
        if _is_corrupt_lyric_line(stripped):
            break
        kept.append(stripped)

    while kept and not kept[-1].strip():
        kept.pop()
    while kept and _is_section_header_line(kept[-1]):
        kept.pop()

    cleaned = "\n".join(kept).strip()
    if len(cleaned) > _REWRITE_MAX_INPUT_CHARS:
        cut = cleaned[:_REWRITE_MAX_INPUT_CHARS]
        last_header = cut.rfind("\n[")
        if last_header > 400:
            cut = cut[:last_header].rstrip()
        cleaned = cut.strip()
    return cleaned


def describe_lyric_rewrite_quality_failure(lyrics: str) -> str | None:
    """Reject rewrite outputs that are empty, oversized, or corrupted."""
    text = str(lyrics or "").strip()
    if not text:
        return "Lyrics rewrite returned empty text."
    if len(text) > _REWRITE_MAX_OUTPUT_CHARS:
        return "Lyrics rewrite is too long to submit to Suno."
    if re.search(r'"lyrics"\s*:', text, re.IGNORECASE):
        return "Lyrics contain embedded JSON artifacts."
    content_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not _is_section_header_line(line)
    ]
    if not content_lines:
        return "Lyrics rewrite has no singable lines."
    bad = sum(1 for line in content_lines if _is_corrupt_lyric_line(line))
    if bad / max(len(content_lines), 1) >= 0.2:
        return "Lyrics rewrite contains word-salad or corrupted lines."
    script_hits = len(_SCRIPT_CHAR_RE.findall(text))
    if script_hits >= 20:
        return "Lyrics rewrite contains unexpected mixed-script noise."
    return None


def unwrap_embedded_lyrics_payload(text: str) -> str:
    """Recover lyric text when the model returned JSON or spliced JSON into the body."""
    from platform_api.ai.parsing.response_parser import parse_json_object

    raw = str(text or "").strip()
    if not raw:
        return raw

    parsed = parse_json_object(raw)
    if isinstance(parsed, dict) and parsed.get("lyrics"):
        return str(parsed["lyrics"]).strip()

    brace_index = raw.find("{")
    if brace_index >= 0:
        fragment = raw[brace_index:]
        parsed = parse_json_object(fragment)
        if isinstance(parsed, dict) and parsed.get("lyrics"):
            return str(parsed["lyrics"]).strip()

    return raw


def strip_trailing_lyric_json_artifacts(text: str) -> str:
    """Drop model meta/JSON tails that sometimes appear after real lyric lines."""
    clean_lines: list[str] = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped == "{" or stripped.startswith('{"lyrics"') or stripped.startswith('"lyrics"'):
            break
        if stripped in {"}", '"}', '"}'}:
            break
        if _is_corrupt_lyric_line(line):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()


def describe_lyric_quality_failure(lyrics: str) -> str | None:
    """Reject obvious model corruption that should trigger a lyric retry."""
    text = str(lyrics or "").strip()
    if not text:
        return "Lyrics are empty."

    if re.search(r'"lyrics"\s*:', text, re.IGNORECASE):
        return "Lyrics contain embedded JSON artifacts."

    content_lines = [
        line
        for line in text.splitlines()
        if line.strip() and not _SECTION_HEADER_RE.match(line.strip())
    ]
    if not content_lines:
        return "Lyrics contain no content lines."

    corrupt_lines = [line for line in content_lines if _is_corrupt_lyric_line(line)]
    if corrupt_lines:
        return "Lyrics contain corrupted or meta model output."

    placeholder_lines = [line for line in content_lines if line.strip() == "…"]
    if placeholder_lines and len(placeholder_lines) / len(content_lines) >= 0.2:
        return "Lyrics contain excessive placeholder padding."

    unique_lines = {line.strip().lower() for line in content_lines}
    if len(content_lines) >= 4 and len(unique_lines) / len(content_lines) < 0.5:
        return "Lyrics repeat the same lines too often."

    min_unique = max(4, min(12, len(content_lines) // 2))
    if len(unique_lines) < min_unique:
        return "Lyrics need more unique lines."

    return None


def extract_freeform_lyric_lines(lyrics: str) -> list[str]:
    """Collect plain lyric lines from a free-form model response."""
    text = unwrap_embedded_lyrics_payload(str(lyrics or "").strip())
    text = strip_trailing_lyric_json_artifacts(text)
    text = strip_lyrics_preamble(text)
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _SECTION_HEADER_RE.match(stripped):
            continue
        if _is_corrupt_lyric_line(line):
            continue
        lines.append(stripped)
    return lines


def split_freeform_lyrics_to_structure(
    lyrics: str,
    structure_headers: list[str],
    *,
    forced_opening: str | None = None,
) -> str:
    """Map free-form lyric lines onto the user-selected structure template."""
    if not structure_headers:
        return str(lyrics or "").strip()

    content_lines = extract_freeform_lyric_lines(lyrics)
    opening_lines = [
        line.strip()
        for line in str(forced_opening or "").splitlines()
        if line.strip() and not _is_corrupt_lyric_line(line)
    ]

    body_lines = list(content_lines)
    if opening_lines and len(body_lines) >= len(opening_lines):
        if [line.lower() for line in body_lines[: len(opening_lines)]] == [
            line.lower() for line in opening_lines
        ]:
            body_lines = body_lines[len(opening_lines) :]

    expected_short = [lyric_header_line(header) for header in structure_headers]
    rebuilt: list[str] = []

    if not body_lines and not opening_lines:
        return ""

    weights = [section_line_weight(header) for header in structure_headers]
    section_buckets = distribute_lines_by_section_weight(body_lines, weights)

    for index, short_header in enumerate(expected_short):
        rebuilt.append(short_header)
        section_lines = list(section_buckets[index]) if index < len(section_buckets) else []
        if index == 0 and opening_lines:
            section_lines = opening_lines + section_lines
        rebuilt.extend(section_lines)

    return "\n".join(rebuilt).strip()


def assign_draft_lyrics_to_structure(
    lyrics: str,
    structure_headers: list[str],
    *,
    forced_opening: str | None = None,
) -> str:
    """Normalize a free-form lyric draft and assign it to the structure template."""
    normalized = normalize_draft_lyrics(lyrics, structure_headers)
    return split_freeform_lyrics_to_structure(
        normalized,
        structure_headers,
        forced_opening=forced_opening,
    )


def describe_freeform_lyric_source_failure(
    lyrics: str, structure_headers: list[str]
) -> str | None:
    """Validate raw free-form lyric text before template assignment."""
    lines = extract_freeform_lyric_lines(lyrics)
    min_lines = minimum_lyric_content_lines(len(structure_headers))
    if len(lines) < min_lines:
        return (
            f"Not enough lyric lines: need at least {min_lines} plain lines, "
            f"found {len(lines)}. Write more distinct lyric lines."
        )
    return describe_lyric_quality_failure("\n".join(lines))


def describe_draft_lyrics_validation_failure(
    lyrics: str, structure_headers: list[str]
) -> str | None:
    quality_failure = describe_lyric_quality_failure(lyrics)
    if quality_failure is not None:
        return quality_failure
    return describe_structure_validation_failure(lyrics, structure_headers)


def section_label_key(header_line: str) -> str:
    """Map lyric/structure headers to a shared bucket, ignoring Verse 1 vs Verse."""
    label = normalize_section_label(header_line)
    label = re.sub(r"\s+\d+$", "", label).strip()
    return _SECTION_KEY_SYNONYMS.get(label, label)


def section_line_weight(header_line: str) -> float:
    """Relative lyric line budget for a structure section when splitting free-form text."""
    key = section_label_key(header_line)
    if key in _SECTION_LINE_WEIGHTS:
        return _SECTION_LINE_WEIGHTS[key]
    if "final" in key and "drop" in key:
        return _SECTION_LINE_WEIGHTS["final drop"]
    if "drop" in key:
        return _SECTION_LINE_WEIGHTS["drop"]
    return _DEFAULT_SECTION_LINE_WEIGHT


def distribute_lines_by_section_weight(
    lines: list[str],
    weights: list[float],
) -> list[list[str]]:
    """Split lyric lines across sections using largest-remainder weighting."""
    section_count = len(weights)
    if section_count == 0:
        return []
    if not lines:
        return [[] for _ in range(section_count)]

    total_weight = sum(weights)
    if total_weight <= 0:
        even = len(lines) // section_count
        remainder = len(lines) % section_count
        buckets: list[list[str]] = []
        index = 0
        for section_index in range(section_count):
            share = even + (1 if section_index < remainder else 0)
            buckets.append(lines[index : index + share])
            index += share
        return buckets

    total_lines = len(lines)
    raw_shares = [total_lines * weight / total_weight for weight in weights]
    counts = [int(share) for share in raw_shares]
    assigned = sum(counts)
    if total_lines >= section_count:
        for section_index in range(section_count):
            if counts[section_index] == 0:
                donor = max(range(section_count), key=lambda idx: counts[idx])
                if counts[donor] > 1:
                    counts[donor] -= 1
                    counts[section_index] = 1
                    assigned += 1
    for section_index in sorted(
        range(section_count),
        key=lambda idx: (raw_shares[idx] - counts[idx], weights[idx]),
        reverse=True,
    ):
        if assigned >= total_lines:
            break
        counts[section_index] += 1
        assigned += 1

    buckets = []
    index = 0
    for section_index, count in enumerate(counts):
        if section_index == section_count - 1:
            buckets.append(lines[index:])
            break
        buckets.append(lines[index : index + count])
        index += count
    return buckets


def _parse_lyric_sections_ordered(
    lyrics: str,
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split lyrics into preamble and section blocks in source order."""
    text = strip_lyrics_preamble(str(lyrics or "").strip())
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_key: str | None = None
    current_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_key, current_lines
        if current_key is not None:
            sections.append((current_key, current_lines))
        current_key = None
        current_lines = []

    for line in lines:
        if _SECTION_HEADER_RE.match(line):
            flush_section()
            current_key = section_label_key(line)
            continue
        if current_key is None:
            preamble.append(line)
        else:
            current_lines.append(line)
    flush_section()
    return preamble, sections


def _section_content_queues(
    sections: list[tuple[str, list[str]]],
) -> dict[str, list[list[str]]]:
    queues: dict[str, list[list[str]]] = {}
    for key, lines in sections:
        queues.setdefault(key, []).append(list(lines))
    return queues


def _take_section_lines(
    queues: dict[str, list[list[str]]],
    key: str,
    *,
    slots_remaining_for_key: int,
) -> list[str]:
    """Take the next content block for a structure slot, splitting when needed."""
    bucket = queues.get(key)
    if not bucket:
        return []

    if len(bucket) > 1:
        return bucket.pop(0)

    chunk = bucket[0]
    if slots_remaining_for_key <= 1 or len(chunk) <= 1:
        return bucket.pop(0)

    share = max(1, (len(chunk) + slots_remaining_for_key - 1) // slots_remaining_for_key)
    taken = chunk[:share]
    bucket[0] = chunk[share:]
    if not bucket[0]:
        bucket.pop(0)
    return taken


def _pad_section_lines(
    lines: list[str],
    min_count: int,
    *,
    fallback_pool: list[str] | None = None,
) -> list[str]:
    pool = [line for line in lines if line.strip() and line.strip() != "…"]
    if not pool and fallback_pool:
        pool = [
            line
            for line in fallback_pool
            if line.strip() and line.strip() != "…" and not _is_corrupt_lyric_line(line)
        ]
    if len(pool) >= min_count:
        return list(pool)
    if not pool:
        return ["…"] * min_count
    padded = list(pool)
    index = 0
    while len(padded) < min_count:
        padded.append(pool[index % len(pool)])
        index += 1
    return padded


def reshape_lyrics_to_structure(lyrics: str, structure_headers: list[str]) -> str:
    """Deterministically rebuild lyrics to match the user-selected structure template."""
    if not structure_headers:
        return str(lyrics or "").strip()

    preamble, ordered_sections = _parse_lyric_sections_ordered(str(lyrics or ""))
    queues = _section_content_queues(ordered_sections)
    fallback_pool = [
        line
        for _key, lines in ordered_sections
        for line in lines
        if not _is_corrupt_lyric_line(line)
    ]
    if preamble:
        fallback_pool = [
            line for line in preamble if not _is_corrupt_lyric_line(line)
        ] + fallback_pool
    expected_short = [lyric_header_line(header) for header in structure_headers]
    expected_keys = [section_label_key(header) for header in structure_headers]
    min_total = minimum_lyric_content_lines(len(structure_headers))
    min_per_section = max(2, (min_total + len(structure_headers) - 1) // len(structure_headers))

    key_totals: dict[str, int] = {}
    for key in expected_keys:
        key_totals[key] = key_totals.get(key, 0) + 1
    key_seen: dict[str, int] = {}
    expected_key_set = set(expected_keys)

    rebuilt: list[str] = []
    for index, (short_header, key) in enumerate(zip(expected_short, expected_keys, strict=True)):
        key_seen[key] = key_seen.get(key, 0) + 1
        slots_remaining_for_key = key_totals[key] - key_seen[key] + 1
        rebuilt.append(short_header)
        content = _take_section_lines(
            queues,
            key,
            slots_remaining_for_key=slots_remaining_for_key,
        )
        if index == 0 and preamble:
            content = [line for line in preamble if not _is_corrupt_lyric_line(line)] + content
        content = _pad_section_lines(content, min_per_section, fallback_pool=fallback_pool)
        rebuilt.extend(content)

    orphan_lines = [
        line
        for bucket_key, chunks in queues.items()
        if bucket_key not in expected_key_set
        for chunk in chunks
        for line in chunk
        if not _is_corrupt_lyric_line(line)
    ]
    for bucket_key, chunks in queues.items():
        if bucket_key in expected_key_set:
            for chunk in chunks:
                orphan_lines.extend(
                    line for line in chunk if not _is_corrupt_lyric_line(line)
                )
    if orphan_lines:
        rebuilt.extend(orphan_lines)

    return "\n".join(rebuilt).strip()


def normalize_and_reshape_draft_lyrics(
    lyrics: str,
    structure_headers: list[str],
    *,
    forced_opening: str | None = None,
) -> str:
    """Normalize lyric text, then assign it to the structure template."""
    return assign_draft_lyrics_to_structure(
        lyrics,
        structure_headers,
        forced_opening=forced_opening,
    )


def lyric_header_line(header_line: str) -> str:
    """Return the short lyric header the LLM should emit for a structure line."""
    inner = _parse_bracket_header(header_line)
    if inner is None:
        inner = header_line.strip().strip("[]")
    if ":" in inner:
        label = inner.split(":", 1)[0].strip()
        return f"[{label}]"
    stripped = header_line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped
    return f"[{inner.strip()}]"


def extract_structure_header_lines(structure: str) -> list[str]:
    """Extract bracket section lines from a structure template."""
    if not structure or not structure.strip():
        return []
    return [
        line.strip()
        for line in structure.strip().splitlines()
        if line.strip() and _SECTION_HEADER_RE.match(line.strip())
    ]


def minimum_lyric_content_lines(section_count: int) -> int:
    """Minimum non-header lyric lines required for a structure."""
    if section_count <= 0:
        return 32
    # Production templates can have many sections; keep the bar practical.
    return max(16, section_count * 2)


def strip_lyrics_preamble(lyrics: str) -> str:
    """Drop any lines before the first bracket section header.

    Models often prepend a short note (e.g. "Here are the lyrics:") even when
    instructed not to. Trimming preamble is safe when the remaining structure
    is validated separately.
    """
    lines = lyrics.strip().splitlines()
    for index, line in enumerate(lines):
        if _SECTION_HEADER_RE.match(line.strip()):
            return "\n".join(lines[index:]).strip()
    return lyrics.strip()


def normalize_draft_lyrics(lyrics: str, structure_headers: list[str]) -> str:
    """Apply deterministic cleanup before structure validation."""
    text = unwrap_embedded_lyrics_payload(str(lyrics or "").strip())
    text = strip_trailing_lyric_json_artifacts(text)
    if structure_headers:
        text = strip_lyrics_preamble(text)
    return text


def validate_lyrics_structure(lyrics: str, structure_headers: list[str]) -> bool:
    """Validate that lyrics follow the required song structure.

    Rules (Requirement 10.3):
    - No content before the first header (if headers provided).
    - Section labels appear in the same order as the structure template.
      Production templates may use long headers like ``[Intro: synth pads]`` while
      lyrics use the short form ``[Intro]``.
    - Minimum content lines = max(16, len(headers) * 2) if headers,
      or 32 if no headers are provided.

    Args:
        lyrics: The full lyrics text.
        structure_headers: Bracket section lines from the structure template.

    Returns:
        True if lyrics meet all structure constraints.
    """
    return describe_structure_validation_failure(lyrics, structure_headers) is None


def describe_structure_validation_failure(
    lyrics: str, structure_headers: list[str]
) -> str | None:
    """Return a human-readable rejection reason, or None when lyrics are valid."""
    lines = [line.strip() for line in lyrics.strip().splitlines() if line.strip()]
    if not lines:
        return "Lyrics are empty."

    if structure_headers:
        expected_short = [lyric_header_line(header) for header in structure_headers]
        expected_labels = [normalize_section_label(header) for header in structure_headers]

        if not _SECTION_HEADER_RE.match(lines[0]):
            return (
                f"Lyrics must start with {expected_short[0]} on the first line; "
                "remove any text before the first section header."
            )

        found_headers = [line for line in lines if _SECTION_HEADER_RE.match(line)]
        found_labels = [normalize_section_label(header) for header in found_headers]

        if len(found_labels) != len(expected_labels):
            return (
                f"Expected exactly {len(expected_labels)} section headers "
                f"({', '.join(expected_short)}), but found {len(found_headers)}: "
                f"{', '.join(found_headers[:12])}."
            )

        if found_labels != expected_labels:
            mismatches: list[str] = []
            for index, (expected, found_header, found_label) in enumerate(
                zip(expected_short, found_headers, found_labels, strict=True)
            ):
                if expected_labels[index] != found_label:
                    mismatches.append(
                        f"section {index + 1} expected {expected}, got {found_header}"
                    )
            if mismatches:
                return "Section header mismatch: " + "; ".join(mismatches[:4]) + "."
            return (
                f"Section headers must appear in this exact order: {', '.join(expected_short)}."
            )

        content_lines = [line for line in lines if not _SECTION_HEADER_RE.match(line)]
        min_lines = minimum_lyric_content_lines(len(structure_headers))
        if len(content_lines) < min_lines:
            return (
                f"Not enough lyric lines: need at least {min_lines} non-header lines, "
                f"found {len(content_lines)}. Add more lines under each section."
            )
        return None

    content_lines = [line for line in lines if not _SECTION_HEADER_RE.match(line)]
    min_lines = minimum_lyric_content_lines(0)
    if len(content_lines) < min_lines:
        return (
            f"Not enough lyric lines: need at least {min_lines} lines, "
            f"found {len(content_lines)}."
        )
    return None


def extract_lyric_section_headers(lyrics: str) -> list[str]:
    """Return bracket section header lines found in lyric text."""
    return [
        line.strip()
        for line in str(lyrics or "").strip().splitlines()
        if line.strip() and _SECTION_HEADER_RE.match(line.strip())
    ]


def count_ai_structure_content_lines(lyrics: str) -> int:
    """Count non-header lyric lines for AI Structure mode validation."""
    lines = [line.strip() for line in str(lyrics or "").strip().splitlines() if line.strip()]
    return sum(1 for line in lines if not _SECTION_HEADER_RE.match(line))


def normalize_ai_structure_lyrics(lyrics: str) -> str:
    """Normalize provider output for AI Structure mode.

    Strips preamble/JSON wrappers. When a model returns plain lines with no
    section headers, wrap them in a single ``[Verse]`` block as a last resort.
    """
    text = unwrap_embedded_lyrics_payload(str(lyrics or "").strip())
    text = strip_trailing_lyric_json_artifacts(text)
    text = strip_lyrics_preamble(text)
    text = strip_trailing_lyric_meta_tail(text)
    if extract_lyric_section_headers(text):
        return text.strip()

    content_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not _is_corrupt_lyric_line(line)
    ]
    if len(content_lines) >= AI_STRUCTURE_MIN_CONTENT_LINES:
        return "[Verse]\n" + "\n".join(content_lines)
    return text.strip()


def analyze_ai_structure_lyric_response(lyrics: str) -> dict[str, Any]:
    """Summarize raw provider output for probe scripts and acceptance tuning."""
    raw = str(lyrics or "").strip()
    normalized = normalize_ai_structure_lyrics(raw)
    headers = extract_lyric_section_headers(normalized)
    distinct_labels = sorted({normalize_section_label(header) for header in headers})
    raw_lines = [line.strip() for line in raw.splitlines() if line.strip()]
    first_header_index = next(
        (index for index, line in enumerate(raw_lines) if _SECTION_HEADER_RE.match(line)),
        None,
    )
    return {
        "has_headers": bool(headers),
        "header_count": len(headers),
        "distinct_section_labels": distinct_labels,
        "headers_sample": headers[:12],
        "content_line_count": count_ai_structure_content_lines(normalized),
        "total_lines": len(raw_lines),
        "starts_with_header": bool(raw_lines and _SECTION_HEADER_RE.match(raw_lines[0])),
        "has_preamble": first_header_index not in (None, 0),
        "wrapped_single_verse": normalized.startswith("[Verse]\n") and not extract_lyric_section_headers(raw),
        "normalized_preview": normalized[:500],
    }


def describe_ai_structure_validation_failure(lyrics: str) -> str | None:
    """Validate lyrics produced in AI Structure mode."""
    normalized = normalize_ai_structure_lyrics(lyrics)
    quality_failure = describe_lyric_quality_failure(normalized)
    if quality_failure is not None:
        return quality_failure

    lines = [line.strip() for line in normalized.strip().splitlines() if line.strip()]
    if not lines:
        return "Lyrics are empty."

    headers = extract_lyric_section_headers(normalized)
    if not headers:
        return (
            "Lyrics must include section headers like [Verse] and [Chorus], "
            "or enough plain lines for auto-wrapping."
        )

    if not _SECTION_HEADER_RE.match(lines[0]):
        return (
            "Lyrics must start with a section header on the first line; "
            "remove any text before the first section header."
        )

    distinct_labels = {normalize_section_label(header) for header in headers}
    if len(distinct_labels) < AI_STRUCTURE_MIN_SECTION_HEADERS and headers[0] != "[Verse]":
        return (
            f"Need at least {AI_STRUCTURE_MIN_SECTION_HEADERS} distinct section types "
            f"({', '.join(sorted(distinct_labels)) or 'none'} found)."
        )

    content_lines = count_ai_structure_content_lines(normalized)
    if content_lines < AI_STRUCTURE_MIN_CONTENT_LINES:
        return (
            f"Not enough lyric lines: need at least {AI_STRUCTURE_MIN_CONTENT_LINES} "
            f"non-header lines, found {content_lines}."
        )
    return None


def validate_ai_structure_lyrics(lyrics: str) -> bool:
    """Return True when AI Structure mode lyrics meet acceptance rules."""
    return describe_ai_structure_validation_failure(lyrics) is None


def build_structure_constraints_block(structure_headers: list[str]) -> str:
    """Legacy structure-header instructions (kept for tests and reshape fallback)."""
    lyric_headers = [lyric_header_line(header) for header in structure_headers]
    min_lines = minimum_lyric_content_lines(len(structure_headers))
    header_list = ", ".join(lyric_headers)
    return (
        f"Required lyric headers in this exact order (one header per line): {header_list}.\n"
        f"Write at least {min_lines} non-header lyric lines total (about 2-4 lines per section).\n"
        "Rules:\n"
        f"- The first lyrics line must be {lyric_headers[0]} with no text before it.\n"
        "- Use only the short header labels above; do not copy ': production notes' from the structure guide.\n"
        "- Do not invent variants like [Verse 1], [Verse 2], [Hook], or extra sections.\n"
        "- Put original lyric lines beneath each header; headers must be on their own lines.\n"
    )


def build_freeform_lyrics_system_prompt(*, language: str, min_lines: int) -> str:
    """System prompt for lyric draft generation (plain text, no section headers)."""
    return build_lyric_draft_system_prompt(language=language, min_lines=min_lines)


def build_lyric_draft_system_prompt(
    *,
    language: str,
    min_lines: int,
    profile: Any | None = None,
    secondary_language: str | None = None,
    structure_headers: list[str] | None = None,
) -> str:
    """System prompt for step 1: creative whole-song draft as plain lines."""
    from platform_api.ai.purposes.vocal_profile import (
        VocalProfile,
        build_bilingual_language_instruction,
        build_monolingual_language_instruction,
        parse_vocal_profile,
    )

    parsed = profile if isinstance(profile, VocalProfile) else parse_vocal_profile(profile)
    base = (
        "You are a professional songwriter. Write a complete song as plain lyric lines only.\n"
        "Output plain text only — one lyric line per line.\n"
        "Rules:\n"
        "- Do NOT use JSON, markdown fences, commentary, or production notes.\n"
        "- Do NOT include section labels like [Verse], [Chorus], or [Intro].\n"
        "- Write distinct lines that tell a full song story from start to finish.\n"
        "- Do not repeat the same couplet across the song.\n"
        f"- Write at least {min_lines} lyric lines.\n"
    )
    if (
        parsed is not None
        and parsed.is_bilingual
        and secondary_language
        and structure_headers
    ):
        return base + build_bilingual_language_instruction(
            primary=language,
            secondary=secondary_language,
            profile=parsed,
            structure_headers=structure_headers,
        )
    return base + f"- {build_monolingual_language_instruction(language)}\n"


def build_ai_structure_lyrics_system_prompt(
    *,
    language: str,
    min_lines: int = AI_STRUCTURE_MIN_CONTENT_LINES,
    profile: Any | None = None,
    secondary_language: str | None = None,
) -> str:
    """System prompt for AI Structure mode: model chooses section layout."""
    from platform_api.ai.purposes.vocal_profile import (
        VocalProfile,
        build_bilingual_language_instruction,
        build_monolingual_language_instruction,
        parse_vocal_profile,
    )

    from platform_api.services.ai_structure_diversity import (
        build_ai_structure_diversity_system_rules,
    )

    parsed = profile if isinstance(profile, VocalProfile) else parse_vocal_profile(profile)
    base = (
        "You are a professional songwriter. Write a complete song with section headers "
        "you choose (for example [Verse], [Chorus], [Bridge], [Drop], [Outro]).\n"
        "Output plain text only — one section header or lyric line per line.\n"
        "Rules:\n"
        "- Do NOT use JSON, markdown fences, commentary, or production notes.\n"
        "- Put each section header on its own line using square brackets.\n"
        "- Use at least two different section types when the song length allows.\n"
        "- Write original lyric lines beneath each header.\n"
        "- Do not repeat the same couplet across the song.\n"
        f"- Write at least {min_lines} non-header lyric lines in total.\n"
        f"{build_ai_structure_diversity_system_rules()}"
    )
    if parsed is not None and parsed.is_bilingual and secondary_language:
        return base + build_bilingual_language_instruction(
            primary=language,
            secondary=secondary_language,
            profile=parsed,
            structure_headers=[],
        )
    return base + f"- {build_monolingual_language_instruction(language)}\n"


def build_mood_writing_context(
    mood: str,
    *,
    title: str | None = None,
) -> str:
    """Build album/title/lyric writing context from mood (never production description)."""
    parts: list[str] = []
    mood_text = str(mood or "").strip()
    if mood_text:
        parts.append(f"Mood:\n{mood_text}")
    title_text = str(title or "").strip()
    if title_text:
        parts.append(f'Song title: "{title_text}"')
    if not parts:
        return (
            "Write with a clear emotional mood. Prefer specific human feelings. "
            "Avoid neon, chrome, cyberpunk, and night-drive clichés."
        )
    parts.append(
        "Follow the mood closely. Avoid neon, chrome, cyberpunk, and night-drive clichés."
    )
    return "\n\n".join(parts)


def build_lyric_rewrite_system_prompt(
    *,
    strength: int,
    suno_failure_hint: str | None = None,
) -> str:
    """System prompt for lyric rewrite — same rules as draft lyric (mood-led, not description)."""
    strength_clamped = max(0, min(100, int(strength)))
    rewrite_intensity = (
        "Use clearly different wording, imagery, and phrasing from the original."
        if strength_clamped >= 70
        else "Change wording substantially while keeping the same story beats."
    )
    system_prompt = (
        "Rewrite song lyrics for music generation. Keep the same overall story arc, "
        "but produce fresh lyrics that read like a new draft—not a light edit. "
        f"{rewrite_intensity} "
        "Follow the mood and title closely when provided. "
        "Do not treat production style, genre tags, or mix notes as lyric subject matter. "
        "Write SHORT singable lines (usually under 12 words). Aim for about 16–40 lyric lines total. "
        "Never output word salad, keyword lists, code, URLs, JSON, multilingual gibberish, "
        "or meta commentary. "
        "Remove artist names, producer tags, brand names, and other references that could "
        "trigger music-platform content filters. "
        "Never use the word 'lowlight' or other tokens that resemble producer tags. "
        "Keep section labels like [Verse], [Chorus], [Bridge] and preserve line breaks. "
        "Return ONLY the rewritten lyrics text."
    )
    failure_hint = str(suno_failure_hint or "").strip()
    if failure_hint:
        system_prompt += (
            " Suno previously rejected similar lyrics. Avoid repeating the blocked wording. "
            f"Provider rejection detail: {failure_hint}"
        )
    return system_prompt


def build_lyric_rewrite_user_prompt(
    *,
    lyrics: str,
    mood: str = "",
    title: str | None = None,
    structure: str = "",
    description: str = "",  # deprecated; ignored — description is Suno-only
) -> str:
    """User prompt for lyric rewrite: mood + title + structure (no description)."""
    del description
    parts = [build_mood_writing_context(mood, title=title)]
    layout = str(structure or "").strip()
    if layout:
        parts.append(
            "Song structure (preserve these section headers when present in the original):\n"
            f"{layout}"
        )
    parts.append("Original lyrics to rewrite:")
    parts.append(str(lyrics or "").strip())
    return "\n\n".join(parts)


def lyric_rewrite_temperature(strength: int) -> float:
    """Cap rewrite temperature like draft lyric (avoid gibberish from high creativity)."""
    strength_clamped = max(0, min(100, int(strength)))
    return min(0.9, max(0.35, 0.45 + (strength_clamped / 100.0) * 0.4))


def build_ai_structure_lyrics_user_prompt(
    *,
    mood: str = "",
    title: str | None = None,
    description: str = "",  # deprecated; ignored — description is Suno-only
    avoid_openings: list[str] | None = None,
    forced_opening: str | None = None,
    preferred_structure_layout: str | None = None,
    avoid_structures: list[str] | None = None,
    description_genres: list[str] | None = None,
) -> str:
    """User prompt for AI Structure mode — title + mood + layout seed; no description."""
    from platform_api.services.ai_structure_diversity import (
        build_ai_structure_seed_user_block,
    )

    del description  # production description belongs on Suno style only
    parts = [
        build_mood_writing_context(mood, title=title),
        "Choose a viral-friendly section layout for this song and write full lyrics.",
        "Invent section headers that fit the preferred layout shape when provided.",
    ]
    seed_block = build_ai_structure_seed_user_block(
        preferred_layout=preferred_structure_layout,
        avoid_structures=avoid_structures,
        genres=description_genres,
    )
    if seed_block:
        parts.append(seed_block)
    if avoid_openings:
        avoid_str = ", ".join(avoid_openings[:200])
        parts.append(f"Avoid these opening lines: {avoid_str}")
    if forced_opening:
        parts.append(
            "Required opening lines (place under your first section header):\n"
            f"{forced_opening.strip()}"
        )
    return "\n\n".join(parts)


def build_lyric_shape_system_prompt(
    *,
    language: str,
    min_lines: int,
    profile: Any | None = None,
    secondary_language: str | None = None,
    structure_headers: list[str] | None = None,
) -> str:
    """System prompt for step 2: assign draft lines to the structure template."""
    from platform_api.ai.purposes.vocal_profile import (
        VocalProfile,
        build_bilingual_language_instruction,
        build_monolingual_language_instruction,
        parse_vocal_profile,
    )

    parsed = profile if isinstance(profile, VocalProfile) else parse_vocal_profile(profile)
    base = (
        "You are a lyric structure editor. Assign draft lyric lines to the required "
        "section headers in order.\n"
        "Output plain text only — section headers on their own lines, lyric lines below each header.\n"
        "Rules:\n"
        "- Use ONLY lines from the draft provided in the user message.\n"
        "- Do not invent new lyric lines. You may fix minor grammar or line breaks only.\n"
        "- Use exactly the header labels specified; do not add extra sections.\n"
        "- Do not copy ': production notes' from the structure guide into headers.\n"
        f"- Include at least {min_lines} non-header lyric lines in total.\n"
    )
    if (
        parsed is not None
        and parsed.is_bilingual
        and secondary_language
        and structure_headers
    ):
        return base + build_bilingual_language_instruction(
            primary=language,
            secondary=secondary_language,
            profile=parsed,
            structure_headers=structure_headers,
        )
    return base + f"- {build_monolingual_language_instruction(language)}\n"


def build_lyric_shape_user_prompt(
    *,
    draft_lyrics: str,
    structure_guide: str,
    structure_headers: list[str],
    forced_opening: str | None = None,
    profile: Any | None = None,
    primary_language: str | None = None,
    secondary_language: str | None = None,
) -> str:
    """User prompt for step 2: draft text plus structure constraints."""
    from platform_api.ai.purposes.vocal_profile import (
        format_section_language_plan_text,
        parse_vocal_profile,
    )

    parts = [
        "Song structure guide (mood and energy arc — do not output these labels verbatim):\n"
        f"{structure_guide.strip()}",
        build_structure_constraints_block(structure_headers),
        "Draft lyrics to structure (use only these lines):\n"
        f"{str(draft_lyrics or '').strip()}",
    ]
    parsed = parse_vocal_profile(profile)
    if (
        parsed is not None
        and parsed.is_bilingual
        and primary_language
        and secondary_language
    ):
        parts.insert(
            2,
            "Section language plan:\n"
            + format_section_language_plan_text(
                structure_headers,
                profile=parsed,
                primary=primary_language,
                secondary=secondary_language,
            ),
        )
    opening = str(forced_opening or "").strip()
    if opening:
        parts.append(
            "Required opening lines — place these at the start of the first section:\n"
            f"{opening}"
        )
    return "\n\n".join(parts)


def parse_plain_lyric_text(raw: str) -> str:
    """Normalize a plain-text LLM lyric response (draft or shaped)."""
    text = str(raw or "").strip()
    if not text:
        return ""
    text = unwrap_embedded_lyrics_payload(text)
    text = strip_trailing_lyric_json_artifacts(text)
    return strip_lyrics_preamble(text).strip()


def build_freeform_lyrics_opening_block(forced_opening: str | None) -> str:
    """Instructions for starting a free-form song from a pool opening."""
    opening = str(forced_opening or "").strip()
    if not opening:
        return ""
    return (
        "Required opening lines — begin the song with these (you may lightly adapt, "
        "but keep the meaning and imagery):\n"
        f"{opening}\n"
        "Then continue with brand-new lyric lines. Do not repeat the opening verbatim later."
    )


def build_lyric_retry_feedback(
    failure_reason: str,
    structure_headers: list[str],
) -> str:
    """Append corrective instructions after a rejected lyric draft attempt."""
    min_lines = minimum_lyric_content_lines(len(structure_headers))
    return (
        "\n\nCORRECTION REQUIRED — your previous lyrics were rejected:\n"
        f"{failure_reason}\n"
        "Regenerate the draft from scratch and follow these rules exactly:\n"
        f"- Write at least {min_lines} distinct plain lyric lines.\n"
        "- Plain text only. No section labels like [Verse] or [Intro].\n"
        "- Do NOT repeat the same lines across the song.\n"
        "- No markdown fences, commentary, or JSON."
    )


def build_lyric_shape_retry_feedback(
    failure_reason: str,
    structure_headers: list[str],
) -> str:
    """Append corrective instructions after a rejected lyric shaping attempt."""
    lyric_headers = [lyric_header_line(header) for header in structure_headers]
    min_lines = minimum_lyric_content_lines(len(structure_headers))
    return (
        "\n\nCORRECTION REQUIRED — your previous structured lyrics were rejected:\n"
        f"{failure_reason}\n"
        "Re-structure the same draft and follow these rules exactly:\n"
        f"- Start with {lyric_headers[0]} on line 1.\n"
        f"- Use exactly these headers in order: {', '.join(lyric_headers)}.\n"
        f"- Include at least {min_lines} non-header lyric lines in total.\n"
        "- Use only lines from the draft. Plain text output, no JSON or commentary."
    )


def build_structure_retry_feedback(
    failure_reason: str, structure_headers: list[str]
) -> str:
    """Append corrective instructions after a rejected draft attempt."""
    lyric_headers = [lyric_header_line(header) for header in structure_headers]
    min_lines = minimum_lyric_content_lines(len(structure_headers))
    return (
        "\n\nCORRECTION REQUIRED — your previous response was rejected:\n"
        f"{failure_reason}\n"
        "Regenerate from scratch and follow these rules exactly:\n"
        f"- Start lyrics with {lyric_headers[0]} on line 1.\n"
        f"- Use exactly these headers in order: {', '.join(lyric_headers)}.\n"
        f"- Include at least {min_lines} non-header lyric lines in total.\n"
        "- Return ONLY valid JSON with the required keys. No markdown fences or commentary."
    )


def draft_attempt_temperature(base_temperature: float, attempt: int) -> float:
    """Lower temperature slightly on later attempts for more reliable structure."""
    if attempt <= 1:
        return base_temperature
    return min(base_temperature, max(0.35, base_temperature * 0.7))


def _format_avoid_block(label: str, values: list[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return ""
    return f"Avoid these {label}: {', '.join(cleaned[:200])}"


def build_title_slot_prompts(
    *,
    user_context: str,
    title_seed: str | None = None,
    avoid_titles: list[str] | None = None,
    language: str = "en",
    secondary_language: str | None = None,
    vocal_profile: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build system/user prompts for the title LLM slot."""
    from platform_api.ai.purposes.vocal_profile import (
        build_metadata_language_instruction,
        parse_vocal_profile,
    )

    profile = parse_vocal_profile(vocal_profile)
    language_line = build_metadata_language_instruction(
        language=language,
        secondary_language=secondary_language,
        profile=profile,
        slot="title",
    )
    system = (
        'Return valid JSON with exactly one key: "title". '
        "The title must be a short original song title. No explanation. "
        "Use only letters, numbers, spaces, apostrophes, and hyphens. "
        "No quotes, brackets, URLs, or JSON punctuation. "
        f"{language_line}"
    )
    avoid_block = _format_avoid_block("titles", avoid_titles or [])
    if title_seed and title_seed.strip():
        system = (
            'Return valid JSON with exactly one key: "title". '
            "Rephrase the seed into a new short song title. "
            "Keep the same theme and mood, but change the wording. "
            "Do not copy the seed verbatim. No explanation. "
            "Use only letters, numbers, spaces, apostrophes, and hyphens. "
            "No quotes, brackets, URLs, or JSON punctuation. "
            f"{language_line}"
        )
        user_parts = [
            "Rephrase this content-pool title seed into a new song title.",
            f'Seed title: "{title_seed.strip()}"',
            "If the seed is unreadable, invent a short thematic title instead.",
        ]
        if avoid_block:
            user_parts.append(avoid_block)
        user_parts.append(f"Song context:\n{user_context}")
        return system, "\n\n".join(user_parts)

    user_parts = [user_context]
    if avoid_block:
        user_parts.append(avoid_block)
    return system, "\n\n".join(user_parts)


def build_album_slot_prompts(
    *,
    user_context: str,
    album_seed: str | None = None,
    avoid_albums: list[str] | None = None,
    language: str = "en",
    secondary_language: str | None = None,
    vocal_profile: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build system/user prompts for the album LLM slot."""
    from platform_api.ai.purposes.vocal_profile import (
        build_metadata_language_instruction,
        parse_vocal_profile,
    )

    profile = parse_vocal_profile(vocal_profile)
    language_line = build_metadata_language_instruction(
        language=language,
        secondary_language=secondary_language,
        profile=profile,
        slot="album name",
    )
    system = (
        'Return valid JSON with exactly one key: "album". '
        "The album must be a short original album name (2-5 words). No explanation. "
        "Use only letters, numbers, spaces, apostrophes, and hyphens. "
        "No quotes, brackets, URLs, or JSON punctuation. "
        f"{language_line}"
    )
    avoid_block = _format_avoid_block("album names", avoid_albums or [])
    if album_seed and album_seed.strip():
        system = (
            'Return valid JSON with exactly one key: "album". '
            "Rephrase the seed into a new short album name (2-5 words). "
            "Keep the same theme and mood, but change the wording. "
            "Do not copy the seed verbatim. No explanation. "
            "Use only letters, numbers, spaces, apostrophes, and hyphens. "
            "No quotes, brackets, URLs, or JSON punctuation. "
            f"{language_line}"
        )
        user_parts = [
            "Rephrase this content-pool album seed into a new album name.",
            f'Seed album: "{album_seed.strip()}"',
            "If the seed is unreadable or not a real phrase, invent a short thematic album name instead.",
        ]
        if avoid_block:
            user_parts.append(avoid_block)
        user_parts.append(f"Song context:\n{user_context}")
        return system, "\n\n".join(user_parts)

    user_parts = [user_context]
    if avoid_block:
        user_parts.append(avoid_block)
    return system, "\n\n".join(user_parts)


def build_lyrics_opening_block(forced_opening: str | None) -> str:
    """Backward-compatible alias for opening-block builders."""
    return build_freeform_lyrics_opening_block(forced_opening)


def build_suno_lyrics_prompt(
    *,
    description: str = "",
    structure: str,
    language: str,
    secondary_language: str | None = None,
    vocal_profile: dict[str, Any] | None = None,
    structure_headers: list[str] | None = None,
    forced_opening: str | None = None,
    retry_hint: str = "",
    structure_mode: str = STRUCTURE_MODE_TEMPLATE,
    mood: str = "",
    title: str | None = None,
) -> str:
    """Compress lyric-draft context into Suno Lyrics API's 200-character prompt.

    Uses title/mood/opening/structure — not production description (that is Suno style).
    """
    from platform_api.ai.purposes.vocal_profile import (
        language_label,
        parse_vocal_profile,
        resolve_batch_languages,
    )

    del description  # production description is for Suno music style only

    def _compact(text: str, limit: int) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip())[:limit]

    profile = parse_vocal_profile(vocal_profile)
    primary, secondary = resolve_batch_languages(
        batch_language=language,
        secondary_language=secondary_language,
        profile=profile,
    )
    _ = secondary
    lang = _compact(language_label(primary), 16)

    section_labels: list[str] = []
    if not is_free_structure_mode(structure_mode):
        headers = structure_headers or extract_structure_header_lines(structure)
        for header in headers:
            section_labels.append(_compact(lyric_header_line(header).strip("[]"), 18))
            if len(section_labels) >= 4:
                break
    sections = ", ".join(section_labels)

    parts: list[str] = []
    title_bit = _compact(title, 28) if title else ""
    if title_bit:
        parts.append(title_bit)
    mood_bit = _compact(mood, 40) if mood else ""
    if mood_bit:
        parts.append(mood_bit)
    opening = _compact(forced_opening, 35) if forced_opening else ""
    if opening:
        parts.append(opening)
    if structure_mode == STRUCTURE_MODE_SUNO:
        # Native Suno layout — never soft-seed preferred headers.
        parts.append("use your own section headers")
    elif structure_mode == STRUCTURE_MODE_AI_FREE:
        # Compact soft seed if caller packed preferred headers into `structure`.
        seed_labels: list[str] = []
        for header in extract_structure_header_lines(structure)[:4]:
            seed_labels.append(_compact(lyric_header_line(header).strip("[]"), 14))
        if seed_labels:
            parts.append("prefer " + "-".join(seed_labels))
        else:
            parts.append("use your own section headers")
    elif sections:
        parts.append(sections)
    if lang:
        parts.append(lang)
    if retry_hint:
        parts.append(_compact(retry_hint, 40))

    prompt = ". ".join(part for part in parts if part).strip(" .")
    if len(prompt) > 200:
        prompt = prompt[:200].rstrip(" .")
    return prompt


def compute_suno_request_hash(
    model: str, title: str, lyrics: str, style: str, instrumental: bool
) -> str:
    """Compute SHA-256 hash of a Suno request for deduplication (Requirement 11.5).

    Normalizes fields by stripping whitespace before hashing.
    """
    normalized = {
        "model": model.strip(),
        "title": title.strip(),
        "lyrics": lyrics.strip(),
        "style": style.strip(),
        "instrumental": bool(instrumental),
    }
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _check_avoid_list(value: str, avoid_list: list[str]) -> bool:
    """Return True if `value` matches any entry in the avoid list (normalized)."""
    normalized_value = _normalize_text(value)
    return any(_normalize_text(entry) == normalized_value for entry in avoid_list)


def _is_plausible_metadata_name(
    value: str,
    *,
    max_words: int = 6,
    max_chars: int = 56,
    field: str = "album",
) -> bool:
    """Reject runaway or corrupted pool/LLM metadata names."""
    from platform_api.ai.purposes.metadata_text import is_valid_metadata_name

    return is_valid_metadata_name(value, field=field, max_length=max_chars)


def _parse_resolution(resolution: str) -> tuple[int, int] | None:
    """Parse a resolution string like '1920x1080' into (width, height).

    Returns None if the format is invalid.
    """
    match = re.match(r"^(\d+)x(\d+)$", resolution.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


# ---------------------------------------------------------------------------
# Generation Service
# ---------------------------------------------------------------------------


class _ImageUrlResponse(Exception):
    """Internal signal that the provider returned a URL to download instead of inline bytes."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(url)


class GenerationService:
    """Orchestrates AI generation requests with credit management.

    Implements GenerationServicePort: submit_draft, submit_suno, submit_image.

    Constructor Parameters:
        credit_service: Service for deducting/refunding credits.
        pricing_repo: Repository for looking up per-model pricing.
        task_repo: Repository for Suno task persistence and dedup lookup.
        llm_client: Client for LLM song draft generation.
        suno_client: Client for Suno music generation.
        fal_client: Client for Fal AI image generation.
        slai_client: Client for SLAI image generation.
        key_pool_service: Optional key pool service for multi-key management.
            When provided and the pool has entries for a provider, requests
            are routed through KeyPoolClientWrapper with automatic key selection
            and failover. When None or pool has zero entries for a provider,
            falls back to the existing single-key behavior (Req 8.1, 8.2, 8.3).
    """

    def __init__(
        self,
        credit_service: CreditServiceProtocol,
        pricing_repo: CreditPricingRepository,
        task_repo: TaskRepository,
        llm_client: LlmClientProtocol,
        suno_client: SunoClientProtocol,
        fal_client: FalClientProtocol,
        slai_client: SlaiClientProtocol,
        key_pool_service: KeyPoolServicePort | None = None,
        ai_routing_service: Any | None = None,
    ) -> None:
        self._credit_service = credit_service
        self._pricing_repo = pricing_repo
        self._task_repo = task_repo
        self._llm_client = llm_client
        self._suno_client = suno_client
        self._fal_client = fal_client
        self._slai_client = slai_client
        self._key_pool_service = key_pool_service
        self._ai_routing_service = ai_routing_service

        # Create client wrappers when key pool service is available (Req 8.1, 8.2)
        if key_pool_service is not None:
            from platform_api.clients.key_pool_client_wrapper import KeyPoolClientWrapper

            self._suno_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="suno")
            self._fal_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="fal")
            self._slai_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="slai")
            self._llm_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="openai")
            self._deepseek_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="deepseek")
        else:
            self._suno_pool_wrapper = None
            self._fal_pool_wrapper = None
            self._slai_pool_wrapper = None
            self._llm_pool_wrapper = None
            self._deepseek_pool_wrapper = None

        self._text_gateway = None
        self._image_gateway = None

    def _get_image_gateway(self) -> Any:
        if self._image_gateway is None:
            from platform_api.ai.providers.image.gateway import ImageProviderGateway
            from platform_api.dependencies import get_cala_client

            self._image_gateway = ImageProviderGateway(
                fal_client=self._fal_client,
                slai_client=self._slai_client,
                fal_pool=self._fal_pool_wrapper,
                slai_pool=self._slai_pool_wrapper,
                openai_pool=self._llm_pool_wrapper,
                key_pool_service=self._key_pool_service,
                cala_client=get_cala_client(),
            )
        return self._image_gateway

    def _get_text_gateway(self) -> Any:
        if self._text_gateway is None:
            from platform_api.ai.providers.text.gateway import TextProviderGateway
            from platform_api.config import get_settings

            self._text_gateway = TextProviderGateway(
                llm_client=self._llm_client,
                openai_pool=self._llm_pool_wrapper,
                deepseek_pool=self._deepseek_pool_wrapper,
                slai_pool=self._slai_pool_wrapper,
                slai_base_url=get_settings().slai_api_base_url,
                default_llm_timeout_seconds=float(get_settings().llm_timeout_seconds),
            )
        return self._text_gateway

    async def _text_provider_chain(
        self,
        operation: str,
        *,
        provider: str,
        model: str,
    ) -> list[tuple[str, str]]:
        if self._ai_routing_service is not None:
            chain = await self._ai_routing_service.resolve_text_chain(operation)
            return [(item.provider, item.sub_model or "") for item in chain]
        return [(provider, model or "")]

    async def _image_provider_chain(
        self,
        operation: str,
        *,
        provider: str,
        model: str | None,
    ) -> ImageProviderChain:
        if self._ai_routing_service is not None:
            chain = await self._ai_routing_service.resolve_image_chain(operation)
            return [(item.provider, item.sub_model) for item in chain]
        return [(provider, model)]

    # ------------------------------------------------------------------
    # Key Pool Integration Helpers (Requirements 8.1, 8.2, 8.3)
    # ------------------------------------------------------------------

    async def _require_pool_wrapper(self, wrapper: Any, provider: str) -> Any:
        if wrapper is None:
            raise NoAvailableKeysError(provider, {})
        return wrapper

    async def polish_lyrics_text(
        self,
        user_id: str,
        lyrics: str,
        strength: int,
        provider: str,
        model_id: str,
        *,
        provider_chain: list[tuple[str, str]] | None = None,
        description: str | None = None,  # deprecated; ignored — Suno style only
        structure: str | None = None,
        title: str | None = None,
        mood: str | None = None,
        suno_failure_hint: str | None = None,
    ) -> str:
        """Rewrite lyrics aligned with draft lyric flow (mood + title + structure)."""
        del user_id  # reserved for future audit logging
        del description  # production description belongs on Suno style only
        text = prepare_lyrics_for_rewrite(str(lyrics or ""))
        if not text:
            raise ValidationError(
                "These lyrics are too corrupted to rewrite. Regenerate a fresh draft instead.",
                details={"field": "lyrics", "reason": "corrupt_or_empty_after_trim"},
            )
        content_lines = [
            line
            for line in text.splitlines()
            if line.strip() and not _is_section_header_line(line)
        ]
        if len(content_lines) < 2:
            raise ValidationError(
                "Not enough clean lyric lines left to rewrite. Regenerate a fresh draft instead.",
                details={"field": "lyrics", "reason": "insufficient_clean_lines"},
            )

        strength_clamped = max(0, min(100, int(strength)))
        temperature = lyric_rewrite_temperature(strength_clamped)
        system_prompt = build_lyric_rewrite_system_prompt(
            strength=strength_clamped,
            suno_failure_hint=suno_failure_hint,
        )
        user_prompt = build_lyric_rewrite_user_prompt(
            lyrics=text,
            mood=str(mood or ""),
            title=title,
            structure=str(structure or ""),
        )

        polished = await self.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            provider=provider,
            model=model_id,
            temperature=temperature,
            max_tokens=2048,
            prefer_json=False,
            provider_chain=provider_chain,
        )
        cleaned = prepare_lyrics_for_rewrite(str(polished or ""))
        if not cleaned:
            raise ExternalServiceError(
                "Lyrics rewrite returned empty or corrupted text.",
                is_retryable=True,
                details={"provider": provider},
            )
        from platform_api.dependencies import get_suno_blocklist_service
        from platform_api.services.suno_lyrics_sanitize import (
            extract_blocked_terms_from_suno_error,
            sanitize_lyrics_for_suno,
        )

        blocked = extract_blocked_terms_from_suno_error(suno_failure_hint)
        runtime_config = await get_suno_blocklist_service().get_runtime_config()
        cleaned = sanitize_lyrics_for_suno(
            cleaned,
            blocked_terms=blocked,
            runtime_config=runtime_config,
        )
        from platform_api.services.suno_lyrics_sanitize import (
            find_suno_risk_terms_in_text,
            sanitize_lyrics_for_suno_with_changes,
        )

        block_hits = [
            hit
            for hit in find_suno_risk_terms_in_text(
                cleaned,
                learned_terms=blocked,
                runtime_config=runtime_config,
            )
            if hit.severity == "block"
        ]
        if block_hits:
            cleaned, _ = sanitize_lyrics_for_suno_with_changes(
                cleaned,
                blocked_terms=blocked,
                runtime_config=runtime_config,
            )
            cleaned = prepare_lyrics_for_rewrite(cleaned)

        quality_failure = describe_lyric_rewrite_quality_failure(cleaned)
        if quality_failure:
            raise ExternalServiceError(
                quality_failure,
                is_retryable=True,
                details={"provider": provider, "reason": "rewrite_quality_gate"},
            )
        return cleaned

    # ------------------------------------------------------------------
    # submit_draft (Requirements 10.1, 10.3-10.7, 7.3, 7.6)
    # ------------------------------------------------------------------

    async def submit_draft(
        self,
        user_id: str,
        request: DraftRequest,
        *,
        provider: str,
        model: str,
        draft_routing: DraftRouting | None = None,
        skip_pricing: bool = False,
        billing_context: DraftBillingContext | None = None,
    ) -> SongDraft:
        """Generate a song draft (title, album, lyrics) via LLM.

        Uses one provider-agnostic split pipeline: separate title, album, and lyrics
        calls with shared structure validation, retry feedback, and routing.
        """
        ref_id = (
            billing_context.ref_id
            if billing_context and billing_context.ref_id
            else str(uuid4())
        )

        routing = draft_routing or DraftRouting(
            lyric=TextRouting(provider=provider, sub_model=model or None),
            title=TextRouting(provider=provider, sub_model=model or None),
            album=TextRouting(provider=provider, sub_model=model or None),
        )

        price = 0
        usage_metadata: dict[str, Any] | None = None
        if not skip_pricing:
            from platform_api.services.draft_billing import calculate_split_draft_billing
            from platform_api.services.usage_transaction_labels import build_draft_usage_metadata

            include_title = not request.forced_title
            include_album = not request.forced_album
            price, line_items = await calculate_split_draft_billing(
                self._pricing_repo,
                routing,
                include_title=include_title,
                include_album=include_album,
            )
            usage_metadata = build_draft_usage_metadata(
                line_items=[item.to_metadata() for item in line_items],
                forced_title=bool(request.forced_title),
                forced_album=bool(request.forced_album),
                extra=billing_context.to_metadata() if billing_context else None,
                )

            # Atomic credit deduction (Req 7.3)
            success = await self._credit_service.deduct(
                user_id, price, "llm_draft", ref_id, metadata=usage_metadata
            )
            if not success:
                raise InsufficientCreditsError(
                    "Insufficient credits for song draft generation.",
                    details={"required": price},
                )

        if not str(request.description or "").strip():
            raise ValidationError(
                "Description is required for draft generation.",
                details={"field": "description"},
            )

        structure_mode = str(getattr(request, "structure_mode", STRUCTURE_MODE_TEMPLATE) or STRUCTURE_MODE_TEMPLATE)
        if is_free_structure_mode(structure_mode):
            structure_headers: list[str] = []
        else:
            if not str(request.structure or "").strip():
                raise ValidationError(
                    "Structure is required for draft generation.",
                    details={"field": "structure"},
                )
            structure_headers = extract_structure_header_lines(request.structure)
            if not structure_headers:
                raise ValidationError(
                    "Structure must include at least one bracket section header like [Verse].",
                    details={"field": "structure"},
                )

        return await self._submit_split_draft(
            user_id=user_id,
            request=request,
            structure_headers=structure_headers,
            structure_mode=structure_mode,
            routing=routing,
            skip_pricing=skip_pricing,
            price=price,
            ref_id=ref_id,
            usage_metadata=usage_metadata,
        )

    async def _submit_split_draft(
        self,
        *,
        user_id: str,
        request: DraftRequest,
        structure_headers: list[str],
        structure_mode: str = STRUCTURE_MODE_TEMPLATE,
        routing: DraftRouting,
        skip_pricing: bool,
        price: int,
        ref_id: str,
        usage_metadata: dict[str, Any] | None = None,
    ) -> SongDraft:
        """Generate title, album, and lyrics via their dedicated routing slots."""
        from platform_api.ai.parsing.response_parser import parse_string_field
        from platform_api.ai.purposes.metadata_text import (
            is_valid_metadata_name,
            sanitize_metadata_name,
        )

        ai_free = is_free_structure_mode(structure_mode)
        use_ai_structure_seeds = structure_mode == STRUCTURE_MODE_AI_FREE
        # Cap temperature — legacy desktop used ~creativity/85; 1.5x caused gibberish.
        temperature = min(1.0, max(0.25, request.creativity_level / 100.0 * 1.15))
        mood_text = str(getattr(request, "mood", "") or "").strip()
        metadata_context = build_mood_writing_context(mood_text)
        description_genres = [
            str(item).strip()
            for item in (getattr(request, "description_genres", None) or [])
            if str(item).strip()
        ]
        preferred_structure_layout = str(
            getattr(request, "preferred_structure_layout", None) or ""
        ).strip() or None
        avoid_structures = [
            str(item).strip()
            for item in (getattr(request, "avoid_structures", None) or [])
            if str(item).strip()
        ]
        if use_ai_structure_seeds and preferred_structure_layout is None:
            from platform_api.services.ai_structure_diversity import choose_ai_structure_seed

            seed_index = max(0, int(getattr(request, "song_number", None) or 1) - 1)
            preferred_structure_layout = choose_ai_structure_seed(
                genres=description_genres,
                batch_index=seed_index,
                avoid_fingerprints=avoid_structures,
            ).layout_block
        elif not use_ai_structure_seeds:
            preferred_structure_layout = None
        if ai_free:
            # Title is injected after album/title generation.
            lyrics_user_context = ""
            min_lyric_lines = AI_STRUCTURE_MIN_CONTENT_LINES
        else:
            lyrics_user_context = ""
            min_lyric_lines = minimum_lyric_content_lines(len(structure_headers))
        opening_block = build_freeform_lyrics_opening_block(request.forced_opening)

        title_system, title_user = build_title_slot_prompts(
            user_context=metadata_context,
            title_seed=request.title_seed,
            avoid_titles=request.avoid_titles,
            language=request.language,
            secondary_language=request.secondary_language,
            vocal_profile=request.vocal_profile,
        )
        album_system, album_user = build_album_slot_prompts(
            user_context=metadata_context,
            album_seed=request.album_seed,
            avoid_albums=request.avoid_albums,
            language=request.language,
            secondary_language=request.secondary_language,
            vocal_profile=request.vocal_profile,
        )
        lyrics_system = (
            build_ai_structure_lyrics_system_prompt(
                language=request.language,
                min_lines=min_lyric_lines,
                profile=request.vocal_profile,
                secondary_language=request.secondary_language,
            )
            if ai_free
            else build_lyric_draft_system_prompt(
                language=request.language,
                min_lines=min_lyric_lines,
                profile=request.vocal_profile,
                secondary_language=request.secondary_language,
                structure_headers=structure_headers,
            )
        )
        lyrics_shape_system = build_lyric_shape_system_prompt(
            language=request.language,
            min_lines=min_lyric_lines,
            profile=request.vocal_profile,
            secondary_language=request.secondary_language,
            structure_headers=structure_headers,
        )
        if opening_block and not ai_free:
            lyrics_system += (
                "The user message includes required opening lines. "
                "Begin the song with them, then continue with new lines.\n"
            )

        last_failure_reason = "Unknown failure"
        title_album_attempts = 0
        lyric_retry_feedback = ""
        title_calls = 0
        album_calls = 0
        lyric_calls = 0
        title_chain = await self._text_provider_chain(
            "title",
            provider=routing.title.provider,
            model=routing.title.sub_model or "",
        )
        album_chain = await self._text_provider_chain(
            "album",
            provider=routing.album.provider,
            model=routing.album.sub_model or "",
        )
        lyric_chain = await self._text_provider_chain(
            "lyric",
            provider=routing.lyric.provider,
            model=routing.lyric.sub_model or "",
        )

        refunded = False

        from platform_api.services.draft_progress_log import log_song_draft_started

        if request.batch_id:
            log_song_draft_started(
                batch_id=request.batch_id,
                song_number=request.song_number,
                song_id=request.song_id,
            )

        async def refund_failed_draft(
            *,
            attempts_used: int | None = None,
            status: str = "failed",
            reason: str = "draft_generation_failed",
        ) -> None:
            nonlocal refunded
            if refunded or skip_pricing or price <= 0:
                return
            failure_metadata = {
                **(usage_metadata or {}),
                "attempts_used": attempts_used or MAX_LYRIC_ATTEMPTS,
                "llm_calls_title": title_calls,
                "llm_calls_album": album_calls,
                "llm_calls_lyric": lyric_calls,
                "status": status,
            }
            await self._credit_service.refund(
                user_id,
                price,
                reason,
                ref_id,
                metadata=failure_metadata,
            )
            refunded = True

        try:
            # 1) Album (pool seed + mood) → 2) Title (pool seed + mood) → 3) Lyrics
            album: str | None = request.forced_album
            album_attempt_used = 1
            if album:
                album = sanitize_metadata_name(album, field="album")
                if not is_valid_metadata_name(album, field="album"):
                    await refund_failed_draft(attempts_used=1, reason="invalid_forced_album")
                    raise ExternalServiceError(
                        f"Forced album '{request.forced_album}' failed validation.",
                        is_retryable=False,
                        details={"field": "album"},
                    )
            if not album:
                for album_attempt in range(1, MAX_ALBUM_ATTEMPTS + 1):
                    attempt_temperature = draft_attempt_temperature(temperature, album_attempt)
                    try:
                        album_raw = await self._get_text_gateway().generate_text(
                            provider=routing.album.provider,
                            model=routing.album.sub_model or "",
                            system_prompt=album_system,
                            user_prompt=album_user,
                            temperature=attempt_temperature,
                            max_tokens=256,
                            prefer_json=True,
                            provider_chain=album_chain,
                        )
                        album_calls += 1
                        album = sanitize_metadata_name(
                            parse_string_field(album_raw, "album"),
                            field="album",
                        )
                    except ExternalServiceError as exc:
                        last_failure_reason = f"Album LLM error on attempt {album_attempt}: {exc}"
                        logger.warning(last_failure_reason, exc_info=True)
                        album = None
                        if album_attempt >= MAX_ALBUM_ATTEMPTS:
                            await refund_failed_draft(attempts_used=album_attempt)
                            raise
                    if not album:
                        last_failure_reason = f"Incomplete album on attempt {album_attempt}"
                        continue
                    if not _is_plausible_metadata_name(album, field="album"):
                        last_failure_reason = (
                            f"Album '{album}' failed plausibility check on attempt {album_attempt}"
                        )
                        album = None
                        continue
                    if _check_avoid_list(album, request.avoid_albums):
                        title_album_attempts += 1
                        last_failure_reason = f"Album '{album}' found in avoid list"
                        album = None
                        if title_album_attempts >= MAX_TITLE_ALBUM_ATTEMPTS:
                            break
                        continue
                    album_attempt_used = album_attempt
                    break
            if not album:
                await refund_failed_draft(attempts_used=album_calls or MAX_ALBUM_ATTEMPTS)
                raise ExternalServiceError(
                    f"Song draft generation failed while generating album. "
                    f"Last failure: {last_failure_reason}",
                    is_retryable=False,
                    details={"last_failure_reason": last_failure_reason},
                )

            from platform_api.services.draft_progress_log import (
                log_album_generated,
                log_album_reused,
            )

            if request.batch_id:
                if request.forced_album:
                    log_album_reused(
                        batch_id=request.batch_id,
                        song_number=request.song_number,
                        album=album,
                    )
                else:
                    log_album_generated(
                        batch_id=request.batch_id,
                        song_number=request.song_number,
                        album=album,
                        attempt=album_attempt_used,
                    )

            title: str | None = request.forced_title
            title_attempt_used = 1
            if title:
                title = sanitize_metadata_name(title, field="title")
                if not is_valid_metadata_name(title, field="title"):
                    await refund_failed_draft(attempts_used=1, reason="invalid_forced_title")
                    raise ExternalServiceError(
                        f"Forced title '{request.forced_title}' failed validation.",
                        is_retryable=False,
                        details={"field": "title"},
                    )
            if not title:
                for title_attempt in range(1, MAX_TITLE_ATTEMPTS + 1):
                    attempt_temperature = draft_attempt_temperature(temperature, title_attempt)
                    try:
                        title_raw = await self._get_text_gateway().generate_text(
                            provider=routing.title.provider,
                            model=routing.title.sub_model or "",
                            system_prompt=title_system,
                            user_prompt=title_user,
                            temperature=attempt_temperature,
                            max_tokens=256,
                            prefer_json=True,
                            provider_chain=title_chain,
                        )
                        title_calls += 1
                        title = sanitize_metadata_name(
                            parse_string_field(title_raw, "title"),
                            field="title",
                        )
                    except ExternalServiceError as exc:
                        last_failure_reason = f"Title LLM error on attempt {title_attempt}: {exc}"
                        logger.warning(last_failure_reason, exc_info=True)
                        title = None
                        if title_attempt >= MAX_TITLE_ATTEMPTS:
                            await refund_failed_draft(attempts_used=title_attempt)
                            raise
                    if not title:
                        last_failure_reason = f"Incomplete title on attempt {title_attempt}"
                        continue
                    if not is_valid_metadata_name(title, field="title"):
                        last_failure_reason = (
                            f"Title '{title}' failed validation on attempt {title_attempt}"
                        )
                        title = None
                        continue
                    if _check_avoid_list(title, request.avoid_titles):
                        title_album_attempts += 1
                        last_failure_reason = f"Title '{title}' found in avoid list"
                        title = None
                        if title_album_attempts >= MAX_TITLE_ALBUM_ATTEMPTS:
                            break
                        continue
                    title_attempt_used = title_attempt
                    break
            if not title:
                await refund_failed_draft(attempts_used=title_calls or MAX_TITLE_ATTEMPTS)
                raise ExternalServiceError(
                    f"Song draft generation failed while generating title. "
                    f"Last failure: {last_failure_reason}",
                    is_retryable=False,
                    details={"last_failure_reason": last_failure_reason},
                )

            from platform_api.services.draft_progress_log import log_title_generated

            if request.batch_id:
                log_title_generated(
                    batch_id=request.batch_id,
                    song_number=request.song_number,
                    title=title,
                    attempt=title_attempt_used,
                )

            if ai_free:
                lyrics_user_context = build_ai_structure_lyrics_user_prompt(
                    mood=mood_text,
                    title=title,
                    avoid_openings=request.avoid_openings,
                    forced_opening=request.forced_opening,
                    preferred_structure_layout=preferred_structure_layout,
                    avoid_structures=avoid_structures,
                    description_genres=description_genres,
                )
            else:
                lyrics_user_context = self._build_freeform_lyrics_user_prompt(
                    request, title=title
                )

            lyrics = ""
            lyric_attempt = 0
            use_suno_lyrics = is_suno_lyric_routing(
                provider=routing.lyric.provider,
                operation="lyric",
            )
            suno_retry_hint = ""
            for lyric_attempt in range(1, MAX_LYRIC_ATTEMPTS + 1):
                attempt_temperature = draft_attempt_temperature(temperature, lyric_attempt)
                lyrics_user_prompt = lyrics_user_context
                if opening_block and not ai_free:
                    # AI Structure prompt already includes forced_opening.
                    lyrics_user_prompt += "\n\n" + opening_block
                elif opening_block and ai_free and "Required opening" not in lyrics_user_prompt:
                    lyrics_user_prompt += "\n\n" + opening_block
                lyrics_user_prompt += lyric_retry_feedback
                draft_lyrics = ""
                try:
                    if use_suno_lyrics:
                        suno_structure = (
                            preferred_structure_layout
                            if use_ai_structure_seeds and preferred_structure_layout
                            else request.structure
                        )
                        suno_prompt = build_suno_lyrics_prompt(
                            structure=suno_structure or "",
                            language=request.language,
                            secondary_language=request.secondary_language,
                            vocal_profile=request.vocal_profile,
                            structure_headers=structure_headers,
                            forced_opening=request.forced_opening,
                            retry_hint=suno_retry_hint,
                            structure_mode=structure_mode,
                            mood=mood_text,
                            title=title,
                        )
                        draft_lyrics = await self._call_suno_lyrics(prompt=suno_prompt)
                        lyric_calls += 1
                    else:
                        draft_raw = await self._get_text_gateway().generate_text(
                            provider=routing.lyric.provider,
                            model=routing.lyric.sub_model or "",
                            system_prompt=lyrics_system,
                            user_prompt=lyrics_user_prompt,
                            temperature=attempt_temperature,
                            max_tokens=2048,
                            prefer_json=False,
                            provider_chain=lyric_chain,
                        )
                        lyric_calls += 1
                        draft_lyrics = parse_plain_lyric_text(draft_raw)
                except ExternalServiceError as exc:
                    last_failure_reason = f"Lyric LLM error on attempt {lyric_attempt}: {exc}"
                    logger.warning(
                        "Split draft lyric LLM error on attempt %d/%d: %s",
                        lyric_attempt,
                        MAX_LYRIC_ATTEMPTS,
                        exc,
                        exc_info=True,
                    )
                    if lyric_attempt >= MAX_LYRIC_ATTEMPTS:
                        await refund_failed_draft(attempts_used=lyric_attempt)
                        raise
                    continue

                if not draft_lyrics:
                    last_failure_reason = f"Incomplete lyrics on attempt {lyric_attempt}"
                    continue

                if ai_free:
                    lyrics = normalize_ai_structure_lyrics(draft_lyrics)
                    structure_failure = describe_ai_structure_validation_failure(lyrics)
                    if structure_failure is not None:
                        last_failure_reason = (
                            f"Lyrics validation failed on attempt {lyric_attempt}: "
                            f"{structure_failure}"
                        )
                        lyric_retry_feedback = (
                            f"\n\nPrevious attempt failed: {structure_failure}. "
                            "Use section headers and write more distinct lyric lines."
                        )
                        if use_suno_lyrics:
                            suno_retry_hint = "More sections and distinct lines."
                        logger.warning(
                            "AI Structure lyric validation failed attempt %d/%d: %s",
                            lyric_attempt,
                            MAX_LYRIC_ATTEMPTS,
                            structure_failure,
                        )
                        continue
                    break

                source_failure = describe_freeform_lyric_source_failure(
                    draft_lyrics, structure_headers
                )
                if source_failure is not None:
                    last_failure_reason = (
                        f"Lyrics source validation failed on attempt {lyric_attempt}: "
                        f"{source_failure}"
                    )
                    lyric_retry_feedback = build_lyric_retry_feedback(
                        source_failure, structure_headers
                    )
                    if use_suno_lyrics:
                        suno_retry_hint = "More distinct lines, no repetition."
                    logger.warning(
                        "Split draft lyric draft rejected attempt %d/%d: %s",
                        lyric_attempt,
                        MAX_LYRIC_ATTEMPTS,
                        source_failure,
                    )
                    continue

                if use_suno_lyrics:
                    lyrics = assign_draft_lyrics_to_structure(
                        draft_lyrics,
                        structure_headers,
                        forced_opening=request.forced_opening,
                    )
                else:
                    lyrics = ""
                    shape_retry_feedback = ""
                    shape_temperature = min(0.4, max(0.2, attempt_temperature * 0.35))
                    for shape_attempt in range(1, MAX_LYRIC_SHAPE_ATTEMPTS + 1):
                        shape_user_prompt = build_lyric_shape_user_prompt(
                            draft_lyrics=draft_lyrics,
                            structure_guide=request.structure,
                            structure_headers=structure_headers,
                            forced_opening=request.forced_opening,
                            profile=request.vocal_profile,
                            primary_language=request.language,
                            secondary_language=request.secondary_language,
                        )
                        shape_user_prompt += shape_retry_feedback
                        try:
                            shaped_raw = await self._get_text_gateway().generate_text(
                                provider=routing.lyric.provider,
                                model=routing.lyric.sub_model or "",
                                system_prompt=lyrics_shape_system,
                                user_prompt=shape_user_prompt,
                                temperature=shape_temperature,
                                max_tokens=2048,
                                prefer_json=False,
                                provider_chain=lyric_chain,
                            )
                            lyric_calls += 1
                        except ExternalServiceError as exc:
                            last_failure_reason = (
                                f"Lyric shape LLM error on attempt {lyric_attempt}: {exc}"
                            )
                            logger.warning(last_failure_reason, exc_info=True)
                            break
                        lyrics = normalize_draft_lyrics(
                            parse_plain_lyric_text(shaped_raw),
                            structure_headers,
                        )
                        structure_failure = describe_draft_lyrics_validation_failure(
                            lyrics, structure_headers
                        )
                        if structure_failure is None:
                            break
                        shape_retry_feedback = build_lyric_shape_retry_feedback(
                            structure_failure, structure_headers
                        )
                        logger.warning(
                            "Split draft lyric shape rejected attempt %d/%d shape %d/%d: %s",
                            lyric_attempt,
                            MAX_LYRIC_ATTEMPTS,
                            shape_attempt,
                            MAX_LYRIC_SHAPE_ATTEMPTS,
                            structure_failure,
                        )
                    if describe_draft_lyrics_validation_failure(lyrics, structure_headers):
                        lyrics = assign_draft_lyrics_to_structure(
                            draft_lyrics,
                            structure_headers,
                            forced_opening=request.forced_opening,
                        )

                structure_failure = describe_draft_lyrics_validation_failure(
                    lyrics, structure_headers
                )
                if structure_failure is not None:
                    last_failure_reason = (
                        f"Lyrics validation failed on attempt {lyric_attempt}: "
                        f"{structure_failure}"
                    )
                    lyric_retry_feedback = build_lyric_retry_feedback(
                        structure_failure, structure_headers
                    )
                    if use_suno_lyrics:
                        suno_retry_hint = "More distinct lines, no repetition."
                    logger.warning(
                        "Split draft structure validation failed attempt %d/%d: %s",
                        lyric_attempt,
                        MAX_LYRIC_ATTEMPTS,
                        structure_failure,
                    )
                    continue
                break

            if ai_free:
                final_failure = describe_ai_structure_validation_failure(lyrics)
            else:
                final_failure = describe_draft_lyrics_validation_failure(lyrics, structure_headers)
            if not lyrics or final_failure:
                await refund_failed_draft(
                    attempts_used=lyric_attempt or MAX_LYRIC_ATTEMPTS,
                )
                raise ExternalServiceError(
                    f"Song draft generation failed after all attempts. "
                    f"Last failure: {last_failure_reason}",
                    is_retryable=False,
                    details={"last_failure_reason": last_failure_reason},
                )

            from platform_api.services.draft_progress_log import (
                log_lyrics_generated,
                log_song_draft_complete,
            )

            if request.batch_id:
                log_lyrics_generated(
                    batch_id=request.batch_id,
                    song_number=request.song_number,
                    lyric_calls=lyric_calls,
                    attempts=lyric_attempt,
                )
                log_song_draft_complete(
                    batch_id=request.batch_id,
                    song_number=request.song_number,
                    title=title,
                    album=album,
                    song_id=request.song_id,
                )

            logger.info(
                "Split draft generated successfully for user %s "
                "(title_calls=%d, album_calls=%d, lyric_calls=%d)",
                user_id,
                title_calls,
                album_calls,
                lyric_calls,
            )
            if not skip_pricing and ref_id:
                completion_patch = {
                    "attempts_used": lyric_attempt,
                    "llm_calls_title": title_calls,
                    "llm_calls_album": album_calls,
                    "llm_calls_lyric": lyric_calls,
                    "status": "completed",
                }
                if usage_metadata:
                    usage_metadata = {**usage_metadata, **completion_patch}
                await self._credit_service.patch_transaction_metadata(
                    user_id,
                    ref_id,
                    completion_patch,
                )
            return SongDraft(title=title, album=album, lyrics=lyrics)

        except (InsufficientCreditsError, ValidationError, ExternalServiceError):
            raise
        except Exception as exc:
            await refund_failed_draft(status="error", reason="draft_generation_error")
            raise ExternalServiceError(
                f"Unexpected error during split draft generation: {exc}",
                is_retryable=False,
                details={"error": str(exc)},
            ) from exc

    # ------------------------------------------------------------------
    # submit_suno (Requirements 11.1, 11.5, 11.7, 7.1, 7.6)
    # ------------------------------------------------------------------

    async def submit_suno(
        self,
        user_id: str,
        request: SunoRequest,
        *,
        skip_pricing: bool = False,
        source: str = "studio",
    ) -> str:
        """Submit a music generation request to Suno.

        Workflow:
        1. Compute SHA-256 request hash for dedup (Req 11.5).
        2. Check for existing task with same hash for the user.
        3. If not duplicate: deduct credits, forward to Suno, create record.
        4. On delivery failure: refund credits (Req 7.6).

        Returns:
            The Suno-assigned task ID (from existing record or new submission).
        """
        user_uuid = UUID(user_id)
        ref_id = str(uuid4())
        from platform_api.dependencies import get_suno_blocklist_service
        from platform_api.ai.purposes.metadata_text import (
            is_valid_metadata_name,
            sanitize_metadata_name,
        )
        from platform_api.services.suno_lyrics_sanitize import sanitize_text_for_suno

        runtime_config = await get_suno_blocklist_service().get_runtime_config()
        safe_title = sanitize_metadata_name(request.title, field="title", max_length=255)
        if not safe_title or not is_valid_metadata_name(
            safe_title, field="title", max_length=255
        ):
            raise ValidationError(
                "Suno requires a valid song title.",
                details={"field": "title", "title": str(request.title or "")[:160]},
            )

        safe_title = sanitize_text_for_suno(safe_title, runtime_config=runtime_config)
        if not is_valid_metadata_name(safe_title, field="title", max_length=255):
            raise ValidationError(
                "Suno requires a valid song title after blocklist sanitize.",
                details={"field": "title"},
            )
        safe_lyrics = sanitize_text_for_suno(request.lyrics, runtime_config=runtime_config)
        safe_style = sanitize_text_for_suno(request.style, runtime_config=runtime_config)

        # Compute request hash for dedup (Req 11.5)
        request_hash = compute_suno_request_hash(
            model=request.model,
            title=safe_title,
            lyrics=safe_lyrics,
            style=safe_style,
            instrumental=request.instrumental,
        )

        # Check for existing task with same hash (studio only — web Create is a new request each time)
        existing_task = await self._task_repo.find_by_hash(user_uuid, request_hash)
        if existing_task is not None and str(source or "studio").strip().lower() != "web_music":
            logger.info(
                "Duplicate Suno request detected for user %s (hash=%s). "
                "Returning existing task %s",
                user_id,
                request_hash[:12],
                existing_task.id,
            )
            return str(existing_task.id)

        price = 0
        usage_metadata: dict[str, Any] | None = None
        if not skip_pricing:
            from platform_api.services.pricing_keys import normalize_suno_pricing_sub_model

            price = await self._pricing_repo.get_price(
                "suno",
                "music",
                normalize_suno_pricing_sub_model(request.model) or None,
            )

            from platform_api.services.usage_transaction_labels import build_generation_usage_metadata

            usage_metadata = build_generation_usage_metadata(
                operation="suno",
                provider="suno",
                model=request.model,
                purpose=f"Music generation (Suno {request.model})",
                extra={
                    "title": request.title,
                    "instrumental": request.instrumental,
                },
                )

            # Atomic credit deduction (Req 7.1)
            success = await self._credit_service.deduct(
                user_id, price, "suno_generation", ref_id, metadata=usage_metadata
            )
            if not success:
                raise InsufficientCreditsError(
                    "Insufficient credits for Suno music generation.",
                    details={"required": price},
                )

        # Forward to Suno API (Req 11.1)
        try:
            suno_response = await self._call_suno(
                model=request.model,
                title=safe_title,
                lyrics=safe_lyrics,
                style=safe_style,
                instrumental=request.instrumental,
                callback_url=None,  # Client uses configured callback URL
            )
        except ExternalServiceError as exc:
            # Delivery failure — refund credits (Req 7.6)
            if not skip_pricing and price > 0:
                await self._credit_service.refund(
                    user_id,
                    price,
                    "suno_generation_failed",
                    ref_id,
                    metadata=usage_metadata,
                )
            raise exc

        # Extract external task ID from Suno response
        from platform_api.clients.suno_client import extract_suno_generate_task_id

        try:
            external_task_id = extract_suno_generate_task_id(suno_response)
        except ExternalServiceError as exc:
            if not skip_pricing and price > 0:
                await self._credit_service.refund(
                    user_id,
                    price,
                    "suno_invalid_response",
                    ref_id,
                    metadata=usage_metadata,
                )
            raise exc

        # Create Suno_Task record
        task = SunoTask(
            id=uuid4(),
            user_id=user_uuid,
            request_hash=request_hash,
            model=request.model,
            title=safe_title,
            lyrics=safe_lyrics,
            style=safe_style,
            instrumental=request.instrumental,
            external_task_id=external_task_id,
            status=TaskStatus.PENDING,
            source=str(source or "studio"),
        )
        await self._task_repo.create(task)

        logger.info(
            "Suno task created for user %s: task_id=%s, external=%s",
            user_id,
            task.id,
            external_task_id,
        )
        return str(task.id)

    # ------------------------------------------------------------------
    # submit_image (Requirements 12.1, 12.2, 12.5, 12.6, 7.2, 7.6)
    # ------------------------------------------------------------------

    async def submit_image(
        self,
        user_id: str,
        request: ImageRequest,
        *,
        skip_pricing: bool = False,
    ) -> bytes:
        """Submit an image generation request to the configured provider.

        Workflow:
        1. Validate request parameters (resolution, style_strength, prompt, base64).
        2. Deduct credits atomically.
        3. Forward to provider (Fal AI or SLAI).
        4. Return generated PNG bytes.
        5. On failure: refund credits.

        Returns:
            The generated image as PNG bytes.
        """
        ref_id = str(uuid4())

        # --- Validation (Req 12.1, 12.6) ---
        self._validate_image_request(request)

        # Parse resolution
        dims = _parse_resolution(request.resolution)
        if dims is None:
            raise ValidationError(
                f"Invalid resolution format: '{request.resolution}'. Expected WIDTHxHEIGHT.",
                details={"resolution": request.resolution},
            )
        width, height = dims

        # Validate resolution bounds
        is_channel_cover_resolution = (width, height) == CHANNEL_COVER_ALLOWED_RESOLUTION

        if not (IMAGE_MIN_RESOLUTION <= width <= IMAGE_MAX_RESOLUTION):
            raise ValidationError(
                f"Image width must be between {IMAGE_MIN_RESOLUTION} and {IMAGE_MAX_RESOLUTION}.",
                details={"width": width},
            )
        if not is_channel_cover_resolution and not (
            IMAGE_MIN_RESOLUTION <= height <= IMAGE_MAX_RESOLUTION
        ):
            raise ValidationError(
                (
                    f"Image height must be between {IMAGE_MIN_RESOLUTION} and "
                    f"{IMAGE_MAX_RESOLUTION}, or use the supported channel cover "
                    f"size {CHANNEL_COVER_ALLOWED_RESOLUTION[0]}x{CHANNEL_COVER_ALLOWED_RESOLUTION[1]}."
                ),
                details={"height": height, "allowed_cover_resolution": "1920x1080"},
            )

        price = 0
        usage_metadata: dict[str, Any] | None = None
        if not skip_pricing:
            # Get pricing for image operation
            price = await self._pricing_repo.get_price(request.provider, "image")
            if price is None:
                raise ValidationError(
                    "Image generation pricing is not configured.",
                    details={"provider": request.provider, "operation": "image"},
                )

            from platform_api.services.usage_transaction_labels import build_generation_usage_metadata

            usage_metadata = build_generation_usage_metadata(
                operation="image",
                provider=request.provider,
                model=getattr(request, "model", None),
                purpose=f"Image generation ({request.provider})",
                extra={
                    "resolution": request.resolution,
                    "image_kind": getattr(request, "image_kind", None),
                },
                )

            # Atomic credit deduction (Req 7.2)
            success = await self._credit_service.deduct(
                user_id, price, "image_generation", ref_id, metadata=usage_metadata
            )
            if not success:
                raise InsufficientCreditsError(
                    "Insufficient credits for image generation.",
                    details={"required": price},
                )

        # Forward to provider
        try:
            if request.provider == "fal":
                image_bytes = await self._generate_fal_image(request, width, height)
            elif request.provider == "slai":
                image_bytes = await self._generate_slai_image(request, width, height)
            elif request.provider == "openai":
                image_bytes = await self._generate_openai_image(request, width, height)
            elif request.provider == "cala":
                image_bytes = await self._generate_cala_image(request, width, height)
            else:
                if not skip_pricing and price > 0:
                    await self._credit_service.refund(
                        user_id,
                        price,
                        "image_invalid_provider",
                        ref_id,
                        metadata=usage_metadata,
                    )
                raise ValidationError(
                    f"Unsupported image provider: '{request.provider}'.",
                    details={"provider": request.provider},
                )
        except ExternalServiceError as exc:
            # Delivery failure — refund (Req 7.6)
            if not skip_pricing and price > 0:
                await self._credit_service.refund(
                    user_id,
                    price,
                    "image_generation_failed",
                    ref_id,
                    metadata=usage_metadata,
                )
            raise exc

        except (InsufficientCreditsError, ValidationError):
            raise
        except Exception as exc:
            # Unexpected error — refund (Req 7.6)
            if not skip_pricing and price > 0:
                await self._credit_service.refund(
                    user_id,
                    price,
                    "image_generation_error",
                    ref_id,
                    metadata=usage_metadata,
                )
            raise ExternalServiceError(
                f"Unexpected error during image generation: {exc}",
                is_retryable=False,
                details={"error": str(exc)},
            ) from exc

        logger.info(
            "Image generated for user %s via %s (%dx%d). Size: %d bytes",
            user_id,
            request.provider,
            width,
            height,
            len(image_bytes),
        )
        return image_bytes

    async def submit_image_outcome(
        self,
        user_id: str,
        request: ImageRequest,
        *,
        operation: str | None = None,
        provider_chain: ImageProviderChain | None = None,
        skip_pricing: bool = False,
        job_id: str | None = None,
        slai_retry_attempts: int | None = None,
    ) -> ImageGenerationOutcome:
        """Generate an image, optionally trying a provider fallback chain.

        When ``provider_chain`` is omitted and ``operation`` is set, the chain is
        resolved from AI routing (primary assignment + image fallback list).
        """
        from platform_api.services.slai_image_config_service import (
            get_cached_slai_image_provider_config,
        )

        ref_id = str(uuid4())
        _ = ref_id  # reserved for future per-outcome billing in this method

        self._validate_image_request(request)

        dims = _parse_resolution(request.resolution)
        if dims is None:
            raise ValidationError(
                f"Invalid resolution format: '{request.resolution}'. Expected WIDTHxHEIGHT.",
                details={"resolution": request.resolution},
            )
        width, height = dims

        is_channel_cover_resolution = (width, height) == CHANNEL_COVER_ALLOWED_RESOLUTION
        if not (IMAGE_MIN_RESOLUTION <= width <= IMAGE_MAX_RESOLUTION):
            raise ValidationError(
                f"Image width must be between {IMAGE_MIN_RESOLUTION} and {IMAGE_MAX_RESOLUTION}.",
                details={"width": width},
            )
        if not is_channel_cover_resolution and not (
            IMAGE_MIN_RESOLUTION <= height <= IMAGE_MAX_RESOLUTION
        ):
            raise ValidationError(
                (
                    f"Image height must be between {IMAGE_MIN_RESOLUTION} and "
                    f"{IMAGE_MAX_RESOLUTION}, or use the supported channel cover "
                    f"size {CHANNEL_COVER_ALLOWED_RESOLUTION[0]}x{CHANNEL_COVER_ALLOWED_RESOLUTION[1]}."
                ),
                details={"height": height, "allowed_cover_resolution": "1920x1080"},
            )

        chain = provider_chain
        if chain is None:
            if operation:
                chain = await self._image_provider_chain(
                    operation,
                    provider=request.provider,
                    model=request.model_id,
                )
            else:
                chain = [(request.provider, request.model_id)]

        last_error: ExternalServiceError | None = None
        slai_config = get_cached_slai_image_provider_config()
        for index, (provider, sub_model) in enumerate(chain):
            routed_request = ImageRequest(
                prompt=request.prompt,
                provider=provider,
                model_id=sub_model,
                resolution=request.resolution,
                style_strength=request.style_strength,
                base_image=request.base_image,
            )
            max_attempts = provider_max_attempts(
                provider,
                slai_retries=(
                    slai_retry_attempts
                    if slai_retry_attempts is not None
                    else slai_config.provider_retries
                ),
                fallback_retries=slai_config.fallback_provider_retries,
            )
            provider_error: ExternalServiceError | None = None
            for attempt_index in range(max_attempts):
                image_log.log_provider_attempt(
                    job_id=job_id,
                    provider=provider,
                    sub_model=sub_model,
                    attempt=attempt_index + 1,
                    max_attempts=max_attempts,
                )
                try:
                    image_bytes = await self._generate_image_for_provider(
                        routed_request,
                        width,
                        height,
                    )
                    logger.info(
                        "Image generated for user %s via %s (%dx%d). Size: %d bytes",
                        user_id,
                        provider,
                        width,
                        height,
                        len(image_bytes),
                    )
                    return ImageGenerationOutcome(
                        image_bytes=image_bytes,
                        provider=provider,
                        sub_model=sub_model,
                    )
                except ExternalServiceError as exc:
                    provider_error = exc
                    if not exc.is_retryable or attempt_index >= max_attempts - 1:
                        break
                    delay_seconds = compute_retry_delay_seconds(
                        exc,
                        attempt_index=attempt_index,
                        base_delay_seconds=slai_config.retry_base_delay_seconds,
                        max_delay_seconds=slai_config.retry_max_delay_seconds,
                    )
                    image_log.log_provider_retry(
                        job_id=job_id,
                        provider=provider,
                        sub_model=sub_model,
                        attempt=attempt_index + 1,
                        max_attempts=max_attempts,
                        delay_seconds=delay_seconds,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay_seconds)

            if provider_error is None:
                continue

            last_error = provider_error
            next_provider = chain[index + 1][0] if index + 1 < len(chain) else None
            image_log.log_provider_fallback(
                job_id=job_id,
                provider=provider,
                sub_model=sub_model,
                error=str(provider_error),
                next_provider=next_provider,
            )
            if index >= len(chain) - 1:
                raise provider_error
            logger.warning(
                "Image provider %s/%s failed after %d attempt(s) (%s); trying next fallback provider.",
                provider,
                sub_model,
                max_attempts,
                provider_error,
            )

        if last_error is not None:
            raise last_error
        raise ExternalServiceError(
            "All image providers in the fallback chain failed.",
            is_retryable=False,
            details={"providers": [p for p, _ in chain]},
        )

    async def _generate_image_for_provider(
        self,
        request: ImageRequest,
        width: int,
        height: int,
    ) -> bytes:
        if request.provider == "fal":
            return await self._generate_fal_image(request, width, height)
        if request.provider == "slai":
            return await self._generate_slai_image(request, width, height)
        if request.provider == "openai":
            return await self._generate_openai_image(request, width, height)
        if request.provider == "cala":
            return await self._generate_cala_image(request, width, height)
        raise ValidationError(
            f"Unsupported image provider: '{request.provider}'.",
            details={"provider": request.provider},
        )

    # ------------------------------------------------------------------
    # Private Helpers — Draft
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_headers(structure: str) -> list[str]:
        """Extract section headers like [Verse], [Chorus] from structure text."""
        return extract_structure_header_lines(structure)

    @staticmethod
    def _build_draft_user_prompt(
        request: DraftRequest, structure_headers: list[str]
    ) -> str:
        """Build the user prompt for draft generation with avoid lists."""
        from platform_api.ai.purposes.vocal_profile import sanitize_production_description

        parts = [f"Description:\n{sanitize_production_description(request.description)}"]
        structure_mode = str(getattr(request, "structure_mode", STRUCTURE_MODE_TEMPLATE) or STRUCTURE_MODE_TEMPLATE)
        if not is_free_structure_mode(structure_mode) and str(request.structure or "").strip():
            parts.append(
                "Song structure guide (sonic/production intent only):\n"
                f"{request.structure.strip()}"
            )
        if request.avoid_titles:
            avoid_str = ", ".join(request.avoid_titles[:200])
            parts.append(f"Avoid these titles: {avoid_str}")
        if request.avoid_albums:
            avoid_str = ", ".join(request.avoid_albums[:200])
            parts.append(f"Avoid these album names: {avoid_str}")
        if request.avoid_openings:
            avoid_str = ", ".join(request.avoid_openings[:200])
            parts.append(f"Avoid these opening lines: {avoid_str}")
        if request.forced_title:
            parts.append(f"The title MUST be: {request.forced_title}")
        if request.forced_album:
            parts.append(f"The album name MUST be: {request.forced_album}")
        if request.forced_opening:
            parts.append(
                "The lyrics must include the required opening lines from the user message."
            )
        return "\n\n".join(parts)

    @staticmethod
    def _build_freeform_lyrics_user_prompt(
        request: DraftRequest,
        *,
        title: str | None = None,
    ) -> str:
        """Lyric-slot user prompt: mood + structure + polished title (no description)."""
        parts = [
            build_mood_writing_context(str(getattr(request, "mood", "") or ""), title=title),
        ]
        if str(request.structure or "").strip():
            parts.append(
                "Song structure (write lyrics that fit this form; use exact headers later):\n"
                f"{request.structure.strip()}"
            )
        if request.avoid_openings:
            avoid_str = ", ".join(request.avoid_openings[:200])
            parts.append(f"Avoid these opening lines: {avoid_str}")
        return "\n\n".join(parts)

    @staticmethod
    def _ensure_forced_opening(lyrics: str, forced_opening: str) -> str:
        """Inject opening lines only when the model omitted them."""
        opening = str(forced_opening or "").strip()
        if not opening:
            return lyrics
        normalized_lyrics = str(lyrics or "").strip()
        if opening in normalized_lyrics:
            return lyrics
        return GenerationService._inject_forced_opening(lyrics, opening)

    @staticmethod
    def _parse_llm_response(response: dict[str, Any]) -> dict[str, str] | None:
        """Parse LLM chat completion response into title/album/lyrics."""
        content = extract_chat_content(response)
        if not content:
            return None
        return parse_title_album_lyrics(content)

    @staticmethod
    def _parse_llm_json_content(content: str) -> dict[str, Any] | None:
        """Best-effort JSON object extraction from raw LLM text."""
        from platform_api.ai.parsing.response_parser import parse_json_object

        return parse_json_object(content)

    @staticmethod
    def _inject_forced_opening(lyrics: str, forced_opening: str) -> str:
        """Inject the forced opening as the first content lines after the first header.

        If the lyrics start with a header, insert the forced opening after it.
        Otherwise, prepend it to the beginning of the lyrics.
        """
        lines = lyrics.splitlines()
        if not lines:
            return forced_opening

        # If first line is a header, insert after it
        if re.match(r"^\[.+\]$", lines[0].strip()):
            return lines[0] + "\n" + forced_opening + "\n" + "\n".join(lines[1:])

        # Otherwise prepend
        return forced_opening + "\n" + lyrics

    # ------------------------------------------------------------------
    # Private Helpers — Image
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_image_request(request: ImageRequest) -> None:
        """Validate image request parameters (Req 12.1, 12.6).

        Checks:
        - style_strength in [0, 1]
        - prompt length 1-IMAGE_MAX_PROMPT_LENGTH chars
        - base_image (if provided) ≤ 10 MB
        """
        if not (0.0 <= request.style_strength <= 1.0):
            raise ValidationError(
                "style_strength must be between 0.0 and 1.0.",
                details={"style_strength": request.style_strength},
            )

        if not request.prompt or len(request.prompt) < 1:
            raise ValidationError(
                f"Image prompt is required (1-{IMAGE_MAX_PROMPT_LENGTH} characters).",
                details={"prompt_length": 0},
            )

        if len(request.prompt) > IMAGE_MAX_PROMPT_LENGTH:
            raise ValidationError(
                f"Image prompt exceeds maximum length of {IMAGE_MAX_PROMPT_LENGTH} characters.",
                details={"prompt_length": len(request.prompt)},
            )

        if request.base_image is not None:
            if len(request.base_image) > IMAGE_MAX_BASE64_BYTES:
                raise ValidationError(
                    f"Base image exceeds maximum size of 10 MB.",
                    details={"base_image_bytes": len(request.base_image)},
                )

    async def _generate_fal_image(
        self, request: ImageRequest, width: int, height: int
    ) -> bytes:
        """Generate an image via Fal AI and return PNG bytes."""
        extra_params: dict[str, Any] = {}
        if request.base_image is not None:
            extra_params["image"] = base64.b64encode(request.base_image).decode()
            extra_params["strength"] = request.style_strength

        response = await self._get_image_gateway().generate_fal(
            prompt=request.prompt,
            model_id=request.model_id,
            width=width,
            height=height,
            extra_params=extra_params or None,
        )
        return self._extract_image_bytes(response, provider="fal")

    async def _generate_slai_image(
        self, request: ImageRequest, width: int, height: int
    ) -> bytes:
        """Generate an image via SLAI and return PNG bytes."""
        from platform_api.services.slai_image_rate_limiter import get_slai_image_rate_limiter

        reference_b64: str | None = None
        if request.base_image is not None:
            reference_b64 = base64.b64encode(request.base_image).decode()

        async with get_slai_image_rate_limiter().slot():
            response = await self._get_image_gateway().generate_slai(
            prompt=request.prompt,
                model_id=request.model_id,
            width=width,
            height=height,
            style_strength=request.style_strength,
            reference_image_base64=reference_b64,
        )
        return await self.extract_image_bytes_async(response, provider="slai")

    async def _generate_openai_image(
        self, request: ImageRequest, width: int, height: int
    ) -> bytes:
        """Generate an image via OpenAI (gpt-image models) and return PNG bytes."""
        response = await self._get_image_gateway().generate_openai(
            prompt=request.prompt,
            model_id=request.model_id,
            width=width,
            height=height,
        )
        return self._extract_image_bytes(response, provider="openai")

    async def _generate_cala_image(
        self, request: ImageRequest, width: int, height: int
    ) -> bytes:
        """Generate an image via CALA client and return PNG bytes."""
        reference_b64: str | None = None
        if request.base_image is not None:
            reference_b64 = base64.b64encode(request.base_image).decode()

        response = await self._get_image_gateway().generate_cala(
            prompt=request.prompt,
            width=width,
            height=height,
            reference_image_base64=reference_b64,
        )
        return await self.extract_image_bytes_async(response, provider="cala")

    # ------------------------------------------------------------------
    # Private Helpers — Key Pool Routing (Requirements 8.1, 8.2, 8.3)
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        provider: str,
        provider_chain: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        return await self._get_text_gateway().generate_json_draft(
            provider=provider,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
            provider_chain=provider_chain,
        )

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        provider: str,
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 800,
        response_format: dict[str, str] | None = None,
        prefer_json: bool = False,
        provider_chain: list[tuple[str, str]] | None = None,
    ) -> str:
        return await self._get_text_gateway().generate_text(
            provider=provider,
                    model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
            prefer_json=prefer_json,
            provider_chain=provider_chain,
        )

    async def generate_chat_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str = "deepseek-v4-flash",
        temperature: float = 0.8,
        max_tokens: int = 600,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """Generic LLM chat call routed by model name.

        Routes to the appropriate provider based on the model:
        - deepseek-* models → DeepSeek pool
        - gpt-* models → OpenAI pool
        - Other → fallback chain (DeepSeek → OpenAI → direct)
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if model.startswith("gpt-"):
            wrapper = await self._require_pool_wrapper(self._llm_pool_wrapper, "openai")
            response = await wrapper.execute(
                lambda api_key: self._llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=api_key,
                    base_url="https://api.openai.com",
                    response_format=response_format,
                )
            )
        elif model.startswith("deepseek-"):
            wrapper = await self._require_pool_wrapper(self._deepseek_pool_wrapper, "deepseek")
            response = await wrapper.execute(
                lambda api_key: self._llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=api_key,
                    response_format=response_format,
                )
            )
        else:
            raise ValidationError(
                "Unsupported text model. Configure a deepseek-* or gpt-* model in AI Routing.",
                details={"model": model},
            )

        try:
            return (response["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError(
                "LLM returned an unexpected response shape.",
                is_retryable=False,
                details={"provider": "llm"},
            ) from exc

    async def _call_suno(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool,
        callback_url: str | None,
    ) -> dict[str, Any]:
        wrapper = await self._require_pool_wrapper(self._suno_pool_wrapper, "suno")
        return await wrapper.execute(
            lambda api_key: self._suno_client.submit_task(
                model=model,
                title=title,
                lyrics=lyrics,
                style=style,
                instrumental=instrumental,
                callback_url=callback_url,
                api_key=api_key,
            )
        )

    async def poll_suno_generate_status(self, external_task_id: str):
        """Poll Suno generate record-info for one external task id."""
        from platform_api.clients.suno_client import parse_suno_generate_poll

        wrapper = await self._require_pool_wrapper(self._suno_pool_wrapper, "suno")
        response = await wrapper.execute(
            lambda api_key: self._suno_client.check_status(external_task_id, api_key=api_key)
        )
        return parse_suno_generate_poll(response)

    async def generate_suno_lyrics(self, prompt: str) -> tuple[str, str]:
        """Generate lyrics (and optional title) via Suno for web Simple mode."""
        wrapper = await self._require_pool_wrapper(self._suno_pool_wrapper, "suno")

        async def _run_with_key(api_key: str) -> tuple[str, str]:
            return await self._suno_client.generate_lyrics_blocking(
                prompt=prompt,
                api_key=api_key,
            )

        return await wrapper.execute(_run_with_key)

    async def _call_suno_lyrics(self, *, prompt: str) -> str:
        """Generate lyrics via Suno API (submit + poll on the same pool key)."""
        wrapper = await self._require_pool_wrapper(self._suno_pool_wrapper, "suno")

        async def _run_with_key(api_key: str) -> str:
            text, _title = await self._suno_client.generate_lyrics_blocking(
                prompt=prompt,
                api_key=api_key,
            )
            return text

        return await wrapper.execute(_run_with_key)

    async def _call_fal(
        self,
        *,
        prompt: str,
        model_id: str,
        width: int,
        height: int,
        num_images: int,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        wrapper = await self._require_pool_wrapper(self._fal_pool_wrapper, "fal")
        return await wrapper.execute(
            lambda api_key: self._fal_client.generate_image(
                prompt=prompt,
                model_id=model_id,
                width=width,
                height=height,
                num_images=num_images,
                extra_params=extra_params,
                api_key=api_key,
            )
        )

    async def _call_slai(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        style_strength: float,
        reference_image_base64: str | None,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        wrapper = await self._require_pool_wrapper(self._slai_pool_wrapper, "slai")
        return await wrapper.execute(
            lambda api_key: self._slai_client.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                style_strength=style_strength,
                reference_image_base64=reference_image_base64,
                extra_params=extra_params,
                api_key=api_key,
            )
        )

    @staticmethod
    def _extract_image_bytes(response: dict[str, Any], *, provider: str) -> bytes:
        """Extract PNG image bytes from a provider response.

        Providers may return image data as base64 in various fields.
        Tries common response structures. For URL-based responses (like SLAI),
        raises with a special marker so callers can download asynchronously.
        """
        # Shape 0 (SLAI): {"data": [{"url": "https://...", "cache_id": "..."}]}
        data_list = response.get("data")
        if isinstance(data_list, list) and data_list:
            first_entry = data_list[0]
            if isinstance(first_entry, dict):
                # Check for b64_json first
                b64 = first_entry.get("b64_json", "")
                if b64:
                    return base64.b64decode(b64)
                # Check for downloadable URL
                url = first_entry.get("url", "")
                if url and url.startswith("http"):
                    # Return URL as marker — caller must download
                    raise _ImageUrlResponse(url)

        # Shape 1: {"images": [{"url": "data:image/png;base64,..."}]}
        images = response.get("images", [])
        if images and isinstance(images, list):
            first_image = images[0]
            if isinstance(first_image, dict):
                # base64 data URL
                url = first_image.get("url", "")
                if url.startswith("data:"):
                    _, _, b64_data = url.partition(",")
                    if b64_data:
                        return base64.b64decode(b64_data)
                # Direct base64 field
                b64 = first_image.get("base64") or first_image.get("data")
                if b64:
                    return base64.b64decode(b64)
            elif isinstance(first_image, str):
                return base64.b64decode(first_image)

        # Shape 2: {"image": "base64..."}
        image_data = response.get("image") or response.get("data")
        if image_data and isinstance(image_data, str):
            if image_data.startswith("data:"):
                _, _, b64_data = image_data.partition(",")
                return base64.b64decode(b64_data)
            return base64.b64decode(image_data)

        # Shape 3: {"output": "base64..."}
        output = response.get("output")
        if output and isinstance(output, str):
            return base64.b64decode(output)

        raise ExternalServiceError(
            f"Unable to extract image bytes from {provider} response.",
            is_retryable=False,
            details={"provider": provider, "response_keys": list(response.keys())},
        )

    async def extract_image_bytes_async(
        self, response: dict[str, Any], *, provider: str
    ) -> bytes:
        """Extract image bytes, downloading from URL if needed."""
        try:
            return self._extract_image_bytes(response, provider=provider)
        except _ImageUrlResponse as url_resp:
            # Download the image from the URL with retries
            import asyncio

            max_retries = 3
            last_exc: Exception | None = None

            for attempt in range(1, max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
                        # Include auth header — some providers require it for download
                        dl_response = await client.get(
                            url_resp.url,
                            headers={"User-Agent": "CAMXORA/1.0"},
                            follow_redirects=True,
                        )
                        dl_response.raise_for_status()
                        content = dl_response.content

                        # Validate we got actual image bytes
                        if content and (
                            content[:4] == b'\x89PNG'
                            or content[:2] == b'\xff\xd8'
                            or content[:4] == b'RIFF'
                            or content[:4] == b'GIF8'
                        ):
                            return content

                        # May be a JSON response with embedded URL or base64
                        if content and content[:1] == b'{':
                            import json
                            try:
                                data = json.loads(content)
                                # Try to extract image from nested response
                                nested = self._extract_image_bytes(data, provider=provider)
                                return nested
                            except Exception:
                                pass

                        # If content looks valid (>1KB), return it anyway
                        if len(content) > 1024:
                            return content

                        raise ExternalServiceError(
                            f"Downloaded content is not a valid image ({len(content)} bytes)",
                            is_retryable=True,
                        )
                except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        await asyncio.sleep(2.0 * attempt)
                        continue
                    raise ExternalServiceError(
                        f"Failed to download image from {provider} after {max_retries} attempts: {exc}",
                        is_retryable=True,
                    ) from exc
