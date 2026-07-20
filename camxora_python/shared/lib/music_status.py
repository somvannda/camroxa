"""Music history pipeline status labels."""

from __future__ import annotations

import re

from shared.lib.progress_presentation import format_pipeline_step_text

_FAILURE_STATUSES = frozenset(
    {
        "failed",
        "error",
        "suno_failed",
        "draft_failed",
        "rejected",
        "sensitive_word_error",
        "sensitive_content",
        "content_policy",
        "policy_violation",
        "create_task_failed",
        "generate_audio_failed",
        "generate_lyrics_failed",
        "callback_exception",
        "failure",
        "cancelled",
        "canceled",
    }
)

_SUCCESS_STATUSES = frozenset(
    {
        "success",
        "complete",
        "completed",
        "done",
        "suno_success",
    }
)

_PENDING_STATUSES = frozenset(
    {
        "",
        "pending",
        "queued",
        "running",
        "processing",
        "in_progress",
        "drafting",
        "draft_ready",
        "text_success",
        "first_success",
    }
)

_STATUS_LABELS: dict[str, str] = {
    "pending": "Pending",
    "drafting": "Drafting",
    "draft_ready": "Draft ready",
    "draft_failed": "Draft failed",
    "suno_failed": "Failed",
    "suno_success": "Success",
    "completed": "Completed",
    "complete": "Complete",
}


def _normalize(value: str | None) -> str:
    return str(value or "").strip().lower()


def _strip_suno_boilerplate(message: str) -> str:
    text = re.sub(r"\s+", " ", str(message or "").strip())
    if not text:
        return ""
    replacements = (
        (
            r"^Suno rejected this song \(content policy\)\.\s*Review the lyrics and style prompt, then try again\.\s*",
            "",
        ),
        (
            r"^Suno flagged sensitive content in the lyrics or style\.\s*Edit the prompt and try again\.\s*",
            "",
        ),
        (
            r"^Suno music generation failed\.\s*Try again with different lyrics or style\.\s*",
            "",
        ),
        (r"^Suno generation failed \(status=[^)]+\)\.\s*", ""),
        (r"^Suno failed \([^)]+\):\s*", ""),
    )
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text.strip(" .")


def _short_reason(message: str | None, *, limit: int = 120) -> str:
    cleaned = _strip_suno_boilerplate(str(message or "").strip())
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def _is_failure_status(status: str | None, suno_status: str | None) -> bool:
    for value in (_normalize(status), _normalize(suno_status)):
        if value in _FAILURE_STATUSES:
            return True
    return False


def classify_song_pipeline_bucket(
    status: str | None,
    suno_status: str | None = None,
) -> str:
    """Coarse History filter bucket: success | failed | pending."""
    if _is_failure_status(status, suno_status):
        return "failed"
    song_status = _normalize(status)
    provider_status = _normalize(suno_status)
    for candidate in (provider_status, song_status):
        if candidate in _SUCCESS_STATUSES:
            return "success"
    return "pending"


def is_song_suno_retry_eligible(
    status: str | None,
    suno_status: str | None = None,
) -> bool:
    """Return True when polish/auto-retry may submit Suno for a history song."""
    song_status = _normalize(status)
    provider_status = _normalize(suno_status)
    if song_status == "draft_failed":
        return False
    if song_status in {"draft_ready", "suno_failed"}:
        return True
    if provider_status == "suno_failed":
        return True
    # Provider task rows use "failed"/"error" while song.status may stay suno_pending.
    if provider_status in _FAILURE_STATUSES:
        return True
    return False


def is_song_suno_batch_retry_target(
    status: str | None,
    suno_status: str | None = None,
) -> bool:
    """History batch menu: retry Suno for failed/stuck songs, not fresh drafts."""
    song_status = _normalize(status)
    provider_status = _normalize(suno_status)
    if not is_song_suno_retry_eligible(status, suno_status):
        return False
    if song_status == "draft_ready" and provider_status in _PENDING_STATUSES:
        return False
    if song_status == "draft_ready" and not provider_status:
        return False
    return True


def format_song_pipeline_status(
    status: str | None,
    suno_status: str | None = None,
    suno_error_message: str | None = None,
) -> str:
    """Return a compact history-table label for a song pipeline step."""
    song_status = _normalize(status)
    provider_status = _normalize(suno_status)

    if _is_failure_status(status, suno_status):
        reason = _short_reason(suno_error_message)
        if not reason and provider_status and provider_status not in _FAILURE_STATUSES:
            reason = provider_status.replace("_", " ")
        if reason:
            return f"Failed (Reason: {reason})"
        return "Failed"

    for candidate in (provider_status, song_status):
        if candidate in _SUCCESS_STATUSES:
            return _STATUS_LABELS.get(candidate, candidate.replace("_", " ").title() or "Success")

    for candidate in (provider_status, song_status):
        if candidate in _PENDING_STATUSES:
            return _STATUS_LABELS.get(candidate, candidate.replace("_", " ").title() or "Pending")

    fallback = suno_status or status or "pending"
    labeled = _STATUS_LABELS.get(_normalize(fallback))
    if labeled:
        return labeled
    return format_pipeline_step_text(str(fallback))


def song_pipeline_status_tooltip(
    status: str | None,
    suno_status: str | None = None,
    suno_error_message: str | None = None,
) -> str | None:
    """Full failure reason for history tooltips."""
    if not _is_failure_status(status, suno_status):
        return None
    full = str(suno_error_message or "").strip()
    if full:
        return full
    provider_status = _normalize(suno_status)
    if provider_status and provider_status not in _FAILURE_STATUSES:
        return provider_status.replace("_", " ")
    return None
