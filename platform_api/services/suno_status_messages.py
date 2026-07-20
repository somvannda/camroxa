"""User-friendly messages for Suno API task statuses and error codes."""

from __future__ import annotations

# Documented Suno generate/lyrics failure statuses (record-info + callbacks).
SUNO_FAILURE_STATUSES: frozenset[str] = frozenset(
    {
        "REJECTED",
        "FAILED",
        "ERROR",
        "FAILURE",
        "CANCELLED",
        "CANCELED",
        "SENSITIVE_WORD_ERROR",
        "CREATE_TASK_FAILED",
        "GENERATE_AUDIO_FAILED",
        "CALLBACK_EXCEPTION",
        "GENERATE_LYRICS_FAILED",
        "SENSITIVE_CONTENT",
        "CONTENT_POLICY",
        "POLICY_VIOLATION",
    }
)

SUNO_PENDING_STATUSES: frozenset[str] = frozenset(
    {
        "",
        "PENDING",
        "QUEUED",
        "RUNNING",
        "PROCESSING",
        "IN_PROGRESS",
        "TEXT_SUCCESS",
        "FIRST_SUCCESS",
    }
)

SUNO_SUCCESS_STATUSES: frozenset[str] = frozenset(
    {
        "SUCCESS",
        "COMPLETE",
        "COMPLETED",
        "DONE",
    }
)

# Suno API response codes (submit + poll envelope).
SUNO_API_CODE_MESSAGES: dict[int, str] = {
    429: "Insufficient Suno API credits. Add credits to the Key Pool or try again later.",
    430: "Suno API rate limit reached. Wait a moment and try again.",
    455: "Suno is temporarily unavailable for maintenance. Try again shortly.",
}

_STATUS_USER_MESSAGES: dict[str, str] = {
    "REJECTED": (
        "Suno rejected this song (content policy). "
        "Review the lyrics and style prompt, then try again."
    ),
    "SENSITIVE_WORD_ERROR": (
        "Suno flagged sensitive content in the lyrics or style. "
        "Edit the prompt and try again."
    ),
    "SENSITIVE_CONTENT": (
        "Suno flagged sensitive content in the lyrics or style. "
        "Edit the prompt and try again."
    ),
    "CONTENT_POLICY": (
        "Suno rejected this song due to content policy. "
        "Review the lyrics and style prompt, then try again."
    ),
    "POLICY_VIOLATION": (
        "Suno rejected this song due to content policy. "
        "Review the lyrics and style prompt, then try again."
    ),
    "CREATE_TASK_FAILED": "Suno could not start music generation. Try again or contact support.",
    "GENERATE_AUDIO_FAILED": "Suno failed while generating audio. Try again with different lyrics or style.",
    "GENERATE_LYRICS_FAILED": "Suno failed while generating lyrics. Try again with a shorter prompt.",
    "CALLBACK_EXCEPTION": "Suno reported an internal callback error. Try submitting again.",
    "FAILED": "Suno music generation failed. Try again with different lyrics or style.",
    "ERROR": "Suno music generation failed. Try again with different lyrics or style.",
    "FAILURE": "Suno music generation failed. Try again with different lyrics or style.",
    "CANCELLED": "Suno cancelled this generation.",
    "CANCELED": "Suno cancelled this generation.",
}


def normalize_suno_status(status: object) -> str:
    return str(status or "").strip().upper()


def is_suno_failure_status(status: object) -> bool:
    normalized = normalize_suno_status(status)
    return normalized in SUNO_FAILURE_STATUSES


def is_suno_pending_status(status: object) -> bool:
    return normalize_suno_status(status) in SUNO_PENDING_STATUSES


def is_suno_success_status(status: object) -> bool:
    return normalize_suno_status(status) in SUNO_SUCCESS_STATUSES


def suno_api_code_message(code: int, *, fallback: str = "") -> str:
    mapped = SUNO_API_CODE_MESSAGES.get(int(code or 0))
    if mapped:
        return mapped
    cleaned = str(fallback or "").strip()
    if cleaned:
        return cleaned
    return f"Suno API request failed (code {code})."


def suno_task_failure_message(
    *,
    status: object = "",
    error_message: object = "",
    api_code: int | None = None,
    api_msg: object = "",
) -> str:
    """Build a user-facing failure message from Suno poll/callback fields."""
    if api_code is not None and int(api_code) != 200:
        return suno_api_code_message(int(api_code), fallback=str(api_msg or ""))

    provider_error = str(error_message or "").strip()
    normalized_status = normalize_suno_status(status)

    if normalized_status in _STATUS_USER_MESSAGES:
        base = _STATUS_USER_MESSAGES[normalized_status]
        if provider_error and provider_error.lower() not in base.lower():
            return f"{base} ({provider_error})"
        return base

    if provider_error:
        if normalized_status:
            return f"Suno failed ({normalized_status}): {provider_error}"
        return provider_error

    if normalized_status:
        return f"Suno generation failed (status={normalized_status})."

    return "Suno music generation failed. Try again with different lyrics or style."


def suno_submit_error_message(
    *,
    code: int,
    msg: object = "",
    context: str = "generate",
) -> str:
    """Map Suno submit API errors (generate/lyrics) to user-facing text."""
    cleaned = str(msg or "").strip()
    mapped = SUNO_API_CODE_MESSAGES.get(int(code or 0))
    if mapped:
        return mapped
    if cleaned:
        return cleaned
    label = "generate" if context == "generate" else "lyrics"
    return f"Suno {label} failed (code {code})."


def classify_suno_failure_type(
    *,
    status: object = "",
    error_message: object = "",
) -> str:
    """Classify Suno failures for metrics and retry guidance."""
    normalized = normalize_suno_status(status)
    if normalized in {
        "REJECTED",
        "SENSITIVE_WORD_ERROR",
        "SENSITIVE_CONTENT",
        "CONTENT_POLICY",
        "POLICY_VIOLATION",
    }:
        return "SENSITIVE_WORD_ERROR"

    text = str(error_message or "").strip().lower()
    if "producer tag" in text:
        return "producer_tag"
    if any(
        token in text
        for token in (
            "sensitive",
            "content policy",
            "policy violation",
            "rejected",
            "moderat",
        )
    ):
        return "SENSITIVE_WORD_ERROR"
    return "other"
