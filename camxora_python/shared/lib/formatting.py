"""Formatting helpers for shell pages."""

from __future__ import annotations

from datetime import date, datetime


def format_compact_number(value: int | float | None) -> str:
    if value is None:
        return "--"
    return f"{int(value):,}"


def format_optional(value: str | None, fallback: str = "--") -> str:
    normalized = str(value or "").strip()
    return normalized or fallback


def format_channel_role_label(role: str | None) -> str:
    """Present channel role using current product wording."""
    normalized = str(role or "").strip().lower()
    if normalized in {"n/a", "na", "not available"}:
        return "N/A"
    if normalized in {"ok", "primary"}:
        return "Primary"
    if normalized in {"alt", "secondary"}:
        return "Secondary"
    text = str(role or "").strip()
    return text or "—"


def format_album_slot_label(role: str | None) -> str:
    """Display label for per-channel album slots (OK/Alt → album 1 / album 2)."""
    normalized = str(role or "").strip().lower()
    if normalized in {"ok", "primary", "1", "album 1", "album1"}:
        return "album 1"
    if normalized in {"alt", "secondary", "2", "album 2", "album2"}:
        return "album 2"
    text = str(role or "").strip()
    return text or "—"


def format_short_date(value: str | datetime | date) -> str:
    parsed = _coerce_date(value)
    if parsed is None:
        return str(value)
    return parsed.strftime("%b %d")


def format_friendly_expiry(value: str | datetime | date | None) -> str:
    """Format an expiry date in a user-friendly way, e.g. 'Jun 12, 2026 (in 12 days)'."""
    if value is None:
        return "Not provided"
    if isinstance(value, str) and not value.strip():
        return "Not provided"
    parsed = _coerce_date(value)
    if parsed is None:
        return str(value)
    today = date.today()
    target_date = parsed.date() if isinstance(parsed, datetime) else parsed
    delta = (target_date - today).days
    date_str = parsed.strftime("%b %d, %Y")
    if delta < 0:
        return f"{date_str} (expired)"
    if delta == 0:
        return f"{date_str} (expires today)"
    if delta == 1:
        return f"{date_str} (expires tomorrow)"
    if delta <= 30:
        return f"{date_str} (in {delta} days)"
    return date_str


def format_run_date_label(value: str | datetime | date | None) -> str:
    """Format a user-selected batch run date for history tables."""
    if not value:
        return "—"
    parsed = _coerce_date(value)
    if parsed is None:
        return str(value)
    return parsed.strftime("%b %d, %Y")


def format_datetime(value: datetime | str | None) -> str:
    if value is None:
        return "--"
    parsed = value if isinstance(value, datetime) else _parse_datetime(value)
    if parsed is None:
        return str(value)
    parsed = _to_local_datetime(parsed)
    return parsed.strftime("%b %d, %Y %I:%M %p")


def percent_of(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round((part / total) * 100)))


def format_datetime_label(value: str | datetime | None) -> str:
    if not value:
        return "—"
    parsed = value if isinstance(value, datetime) else _parse_datetime(str(value))
    if parsed is None:
        return str(value)
    parsed = _to_local_datetime(parsed)
    return parsed.strftime("%b %d, %Y %H:%M")


def format_progress_updated_time(value: datetime | None, *, fallback: str = "—") -> str:
    """Format a progress row timestamp using the PC locale when Qt is available."""
    if value is None:
        return fallback
    local = _to_local_datetime(value)
    try:
        from PySide6.QtCore import QDateTime, QLocale

        qdt = QDateTime(
            local.year,
            local.month,
            local.day,
            local.hour,
            local.minute,
            local.second,
        )
        return QLocale.system().toString(qdt, QLocale.FormatType.ShortFormat)
    except Exception:
        return local.strftime("%x %X")


def today_ymd() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _to_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone()


def _coerce_date(value: str | datetime | date) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return _to_local_datetime(value).date()
    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) >= 10 and normalized[4] == "-" and normalized[7] == "-":
        try:
            return datetime.strptime(normalized[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    parsed = _parse_datetime(normalized)
    if parsed is None:
        return None
    return _to_local_datetime(parsed).date()


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
