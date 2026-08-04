"""Estimate provider COGS (USD) from pricing / model-cost tables.

Mirrors admin_portal/src/lib/finance-estimates.ts so User Spent and Finance
agree on cost resolution. Estimates only — not provider invoices.
"""

from __future__ import annotations

from typing import Any


def _norm(value: str | None) -> str:
    return (value or "").strip()


def operation_aliases(operation: str) -> list[str]:
    op = _norm(operation)
    if not op:
        return []
    if op in {"music", "music_generation", "suno"}:
        return ["music", "music_generation"]
    return [op]


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _pricing_matches(
    row: dict[str, Any],
    operation: str,
    provider: str,
    model: str,
) -> bool:
    if _norm(row.get("operation_type")) not in operation_aliases(operation):
        return False
    if provider and _norm(row.get("ai_service")) != provider:
        return False
    if model:
        row_model = _norm(row.get("sub_model"))
        return not row_model or row_model == model
    return True


def resolve_cost_credits(
    pricing: list[dict[str, Any]],
    operation: str,
    provider: str | None,
    model: str | None,
) -> float | None:
    """Return external_cost in *display credits* per event, or None."""
    op = _norm(operation)
    prov = _norm(provider)
    mod = _norm(model)
    if not op:
        return None

    candidates: list[dict[str, Any]] = []
    for row in pricing:
        raw = row.get("external_cost_cents")
        if raw is None:
            continue
        try:
            cost = float(raw)
        except (TypeError, ValueError):
            continue
        if cost < 0:
            continue
        if _pricing_matches(row, op, prov, mod):
            candidates.append(row)
    if not candidates:
        return None

    from platform_api.services.credit_units import units_to_credits

    def _credits(row: dict[str, Any]) -> float:
        return units_to_credits(int(row["external_cost_cents"]))

    if mod:
        exact = [r for r in candidates if _norm(r.get("sub_model")) == mod]
        if exact:
            return _average([_credits(r) for r in exact])
        defaults = [r for r in candidates if not _norm(r.get("sub_model"))]
        if defaults:
            return _average([_credits(r) for r in defaults])

    if prov:
        return _average([_credits(r) for r in candidates])

    values = [_credits(r) for r in candidates]
    unique = {round(v, 6) for v in values}
    if len(unique) == 1:
        return values[0]
    return None


def resolve_model_cost_usd(
    model_costs: list[dict[str, Any]],
    operation: str,
    provider: str | None,
    model: str | None,
) -> float | None:
    op = _norm(operation)
    prov = _norm(provider)
    mod = _norm(model)
    if not op or not prov:
        return None

    aliases = operation_aliases(op)
    for_provider: list[dict[str, Any]] = []
    for row in model_costs:
        try:
            cost = float(row.get("cost_usd"))
        except (TypeError, ValueError):
            continue
        if cost < 0:
            continue
        if _norm(row.get("operation_type")) not in aliases:
            continue
        if _norm(row.get("ai_service")) != prov:
            continue
        for_provider.append(row)
    if not for_provider:
        return None

    if mod:
        exact = [r for r in for_provider if _norm(r.get("sub_model")) == mod]
        if exact:
            return _average([float(r["cost_usd"]) for r in exact])
        defaults = [r for r in for_provider if not _norm(r.get("sub_model"))]
        if defaults:
            return _average([float(r["cost_usd"]) for r in defaults])

    return _average([float(r["cost_usd"]) for r in for_provider])


def estimate_cogs_usd(
    *,
    events: int,
    operation: str,
    provider: str | None,
    model: str | None,
    pricing: list[dict[str, Any]],
    model_costs: list[dict[str, Any]],
    gcv: float | None,
) -> tuple[float | None, str]:
    """Return (est_cogs_usd, coverage) where coverage is pricing|model_cost|none."""
    if events <= 0:
        return 0.0, "none"

    cost_credits = resolve_cost_credits(pricing, operation, provider, model)
    if cost_credits is not None:
        credits_total = events * cost_credits
        if gcv is not None and gcv > 0:
            return credits_total * gcv, "pricing"
        return None, "pricing"

    cost_usd = resolve_model_cost_usd(model_costs, operation, provider, model)
    if cost_usd is not None:
        return events * cost_usd, "model_cost"

    return None, "none"


def prorate_plan_revenue_usd(
    *,
    price_cents: int,
    billing_cycle_days: int | None,
    from_date: Any | None,
    to_date: Any | None,
) -> float:
    """Estimate plan cash attributed to [from_date, to_date].

    Uses billing_cycle_days (default 30) to prorate list price across the
    selected window. Yearly plans (e.g. 365) get a smaller daily share.
    """
    if price_cents <= 0:
        return 0.0
    cycle = int(billing_cycle_days or 30)
    if cycle <= 0:
        cycle = 30

    if from_date is None or to_date is None:
        # No range → assume one full cycle of list price.
        return price_cents / 100.0

    start = from_date.date() if hasattr(from_date, "date") else from_date
    end = to_date.date() if hasattr(to_date, "date") else to_date
    days = max((end - start).days + 1, 1)
    return (price_cents / 100.0) * (days / cycle)
