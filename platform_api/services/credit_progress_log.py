"""Readable credit operation logging for the API terminal."""

from __future__ import annotations

import logging

from platform_api.services.credit_units import format_credit_log_amount
from platform_api.terminal_log import emit

logger = logging.getLogger("platform_api.credits")


def _user_label(user_id: object) -> str:
    text = str(user_id or "").strip()
    return text[:8] if text else "—"


def _ref_label(ref_id: object | None) -> str:
    text = str(ref_id or "").strip()
    return text[:12] if text else ""


def _emit(level: int, message: str, *args: object) -> None:
    emit("credits", message, *args, level=level)


def log_deducted(
    *,
    user_id: object,
    amount_units: int,
    reason: str,
    ref_id: object | None = None,
    new_balance_units: int | None = None,
) -> None:
    balance = (
        f", balance now {format_credit_log_amount(new_balance_units)}"
        if new_balance_units is not None
        else ""
    )
    ref = f", ref={_ref_label(ref_id)}" if _ref_label(ref_id) else ""
    _emit(
        logging.INFO,
        "Deducted %s from user %s (%s%s%s)",
        format_credit_log_amount(amount_units),
        _user_label(user_id),
        reason,
        ref,
        balance,
    )


def log_refunded(
    *,
    user_id: object,
    amount_units: int,
    reason: str,
    ref_id: object | None = None,
    new_balance_units: int | None = None,
) -> None:
    balance = (
        f", balance now {format_credit_log_amount(new_balance_units)}"
        if new_balance_units is not None
        else ""
    )
    ref = f", ref={_ref_label(ref_id)}" if _ref_label(ref_id) else ""
    _emit(
        logging.INFO,
        "Refunded %s to user %s (%s%s%s)",
        format_credit_log_amount(amount_units),
        _user_label(user_id),
        reason,
        ref,
        balance,
    )


def log_added(
    *,
    user_id: object,
    amount_units: int,
    reason: str,
    ref_id: object | None = None,
    new_balance_units: int | None = None,
) -> None:
    balance = (
        f", balance now {format_credit_log_amount(new_balance_units)}"
        if new_balance_units is not None
        else ""
    )
    ref = f", ref={_ref_label(ref_id)}" if _ref_label(ref_id) else ""
    _emit(
        logging.INFO,
        "Added %s to user %s (%s%s%s)",
        format_credit_log_amount(amount_units),
        _user_label(user_id),
        reason,
        ref,
        balance,
    )


def log_subscription_quota(
    *,
    user_id: object,
    operation_type: str,
    ai_service: str,
    remaining: int | None = None,
    quota: int | None = None,
) -> None:
    if remaining is not None and quota is not None:
        detail = f", quota {remaining}/{quota} remaining"
    else:
        detail = ""
    _emit(
        logging.INFO,
        "Subscription quota used for user %s (%s via %s%s)",
        _user_label(user_id),
        operation_type,
        ai_service,
        detail,
    )


def log_batch_preflight(
    *,
    user_id: object,
    batch_id: object,
    song_count: int,
    total_cost_units: int,
    current_balance_units: int,
) -> None:
    _emit(
        logging.INFO,
        "Batch %s preflight OK for user %s: %d song(s), need %s, balance %s",
        _ref_label(batch_id) or "—",
        _user_label(user_id),
        song_count,
        format_credit_log_amount(total_cost_units),
        format_credit_log_amount(current_balance_units),
    )


def log_insufficient_credits(
    *,
    user_id: object,
    required_units: int,
    available_units: int,
    context: str,
) -> None:
    _emit(
        logging.WARNING,
        "Insufficient credits for user %s (%s): need %s, have %s",
        _user_label(user_id),
        context,
        format_credit_log_amount(required_units),
        format_credit_log_amount(available_units),
    )
