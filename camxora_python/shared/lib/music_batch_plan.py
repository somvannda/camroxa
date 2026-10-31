"""Plan a multi-day generate: skip existing day/pair slots, retry leftovers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from shared.models.platform import BatchCreateRequest, BatchCreateResponse, MusicHistoryBatch
from shared.services.platform_client import PlatformApiError


def _ymd(value: object) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return ""


def batch_slot_key(run_date: str, ok_profile_id: str, alt_profile_id: str) -> tuple[str, str, str]:
    """Stable key for one planned generate cell: day + primary + secondary."""
    return (_ymd(run_date), str(ok_profile_id or "").strip(), str(alt_profile_id or "").strip())


def request_slot_key(request: BatchCreateRequest) -> tuple[str, str, str]:
    return batch_slot_key(request.from_date, request.ok_profile_id, request.alt_profile_id)


def history_slot_key(batch: MusicHistoryBatch) -> tuple[str, str, str] | None:
    run_date = _ymd(batch.from_date) or _ymd(batch.to_date)
    ok_id = str(batch.ok_profile_id or "").strip()
    alt_id = str(batch.alt_profile_id or "").strip()
    if not run_date or not ok_id or not alt_id:
        return None
    return (run_date, ok_id, alt_id)


def existing_batch_slots(batches: list[MusicHistoryBatch] | None) -> set[tuple[str, str, str]]:
    slots: set[tuple[str, str, str]] = set()
    for batch in batches or []:
        key = history_slot_key(batch)
        if key is not None:
            slots.add(key)
    return slots


def missing_create_requests(
    requests: list[BatchCreateRequest],
    existing_batches: list[MusicHistoryBatch] | None,
) -> list[BatchCreateRequest]:
    """Return planned creates whose day/pair is not already saved."""
    taken = existing_batch_slots(existing_batches)
    missing: list[BatchCreateRequest] = []
    for request in requests:
        key = request_slot_key(request)
        if not key[0] or not key[1] or not key[2]:
            missing.append(request)
            continue
        if key not in taken:
            missing.append(request)
    return missing


def is_retryable_create_error(exc: BaseException) -> bool:
    """Retry timeouts, network drops, and transient 429/5xx. Do not retry auth/validation."""
    if isinstance(exc, PlatformApiError):
        if exc.status in {401, 403, 404, 409, 422}:
            return False
        message = str(exc).lower()
        if "insufficient" in message or "quota" in message:
            return False
        return exc.status in {0, 408, 429, 500, 502, 503, 504}
    return True


# Longest wait we will block the create worker for. A closed window normally
# clears inside a minute; a longer Retry-After is reported to the user instead
# of leaving Generate looking frozen.
MAX_RETRY_WAIT_SEC = 30.0

# Used when a 429 arrives without a usable Retry-After header.
DEFAULT_RATE_LIMIT_WAIT_SEC = 15.0


def retry_after_seconds(exc: BaseException) -> float | None:
    """Server-requested cooldown for a 429, in seconds (None when unknown)."""
    raw = getattr(exc, "retry_after", None)
    if raw is None:
        return None
    try:
        wait = float(raw)
    except (TypeError, ValueError):
        return None
    return wait if wait > 0 else None


@dataclass
class CreateBatchesResult:
    planned: int = 0
    created: list[BatchCreateResponse] = field(default_factory=list)
    skipped: int = 0
    failed: list[tuple[BatchCreateRequest, str]] = field(default_factory=list)
    # Failed slots whose last error was a 429 (rate limit), plus the cooldown the
    # server asked for, so the UI can show one actionable line instead of a wall.
    rate_limited: int = 0
    retry_after: float | None = None
    # Requests skipped because their day/pair slot already existed (skip_existing on).
    skipped_requests: list[BatchCreateRequest] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def has_progress(self) -> bool:
        return bool(self.created) or self.skipped > 0


def create_planned_batches(
    create_fn: Callable[[BatchCreateRequest], Any],
    requests: list[BatchCreateRequest],
    *,
    existing_batches: list[MusicHistoryBatch] | None = None,
    attempts: int = 3,
    retry_delay_sec: float = 1.5,
    sleep: Callable[[float], None] | None = None,
    skip_existing: bool = False,
) -> CreateBatchesResult:
    """Create the requested batches.

    By default every request is created: duplicates are legitimate (new takes,
    A/B versions, retries). Set ``skip_existing=True`` to skip a slot whose
    planned date + channel pair already exists — used to re-fill a multi-day plan
    without re-creating slots that already succeeded. Continue after a failure;
    retry leftovers.
    """
    planned = [request for request in requests if isinstance(request, BatchCreateRequest)]
    if skip_existing:
        pending = missing_create_requests(planned, existing_batches)
        pending_ids = {id(request) for request in pending}
        skipped_requests = [request for request in planned if id(request) not in pending_ids]
    else:
        pending = list(planned)
        skipped_requests = []
    result = CreateBatchesResult(
        planned=len(planned),
        skipped=len(skipped_requests),
        skipped_requests=skipped_requests,
    )
    if not pending:
        return result

    sleeper = sleep if sleep is not None else __import__("time").sleep
    last_errors: dict[int, str] = {}
    rate_limited_ids: set[int] = set()
    observed_wait: float | None = None

    for attempt in range(max(1, int(attempts))):
        still_pending: list[BatchCreateRequest] = []
        wait_hint: float | None = None
        for index, request in enumerate(pending):
            try:
                created = create_fn(request)
                result.created.append(created)
                last_errors.pop(id(request), None)
            except Exception as exc:
                last_errors[id(request)] = str(exc) or "Failed to create batch."
                if not is_retryable_create_error(exc):
                    result.failed.append((request, last_errors[id(request)]))
                    continue
                if getattr(exc, "status", None) == 429:
                    # The window is closed, so every remaining request in this
                    # sweep would 429 too. Keep them pending and wait once
                    # instead of spending the whole plan against a closed window.
                    blocked = [request, *pending[index + 1 :]]
                    for blocked_request in blocked:
                        last_errors[id(blocked_request)] = last_errors[id(request)]
                        rate_limited_ids.add(id(blocked_request))
                    observed_wait = retry_after_seconds(exc)
                    wait_hint = observed_wait or DEFAULT_RATE_LIMIT_WAIT_SEC
                    still_pending.extend(blocked)
                    break
                still_pending.append(request)
        pending = still_pending
        if not pending:
            break
        if attempt + 1 < max(1, int(attempts)):
            backoff = max(0.0, float(retry_delay_sec)) * (attempt + 1)
            wait = wait_hint if wait_hint is not None else backoff
            if wait > MAX_RETRY_WAIT_SEC:
                # Waiting minutes would look like a frozen Generate button; report instead.
                break
            sleeper(wait)

    for request in pending:
        result.failed.append((request, last_errors.get(id(request), "Failed to create batch.")))
    result.rate_limited = sum(1 for request, _ in result.failed if id(request) in rate_limited_ids)
    result.retry_after = observed_wait
    return result


def format_create_batches_summary(result: CreateBatchesResult) -> str:
    parts: list[str] = []
    if result.created:
        suffix = "s" if result.created_count != 1 else ""
        parts.append(f"Created {result.created_count} batch run{suffix}")
    if result.skipped:
        parts.append(f"{result.skipped} already existed")
    if result.failed:
        suffix = "s" if result.failed_count != 1 else ""
        parts.append(f"{result.failed_count} still missing")
    if not parts:
        return "No batch runs to create."
    return ", ".join(parts) + "."


def format_failed_create_slots(failed: list[tuple[BatchCreateRequest, str]]) -> str:
    labels: list[str] = []
    for request, error in failed:
        day = _ymd(request.from_date) or "unknown date"
        labels.append(f"{day} ({error})")
    return "; ".join(labels)


def format_failed_create_message(result: CreateBatchesResult) -> str:
    """User-facing line for a Generate that could not create every slot.

    When the failures are all rate limits, one short sentence with the cooldown
    beats repeating the same error once per planned day.
    """
    total = result.failed_count
    suffix = "s" if total != 1 else ""
    if total and result.rate_limited == total:
        wait = int(round(result.retry_after or 0))
        hint = f" Try again in {wait}s." if wait > 0 else ""
        return (
            f"Rate limit exceeded. {total} of {result.planned} batch run{suffix} "
            f"not created.{hint}"
        )
    return f"Could not create {total} batch run{suffix}: {format_failed_create_slots(result.failed)}"
