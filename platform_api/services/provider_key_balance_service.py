"""Per-key provider balance monitoring for Admin dashboard.

Fetches remaining credits/money for each key-pool entry so ops can top up
on time. Providers without a public balance API are marked unsupported.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

BALANCE_PROVIDERS = ("suno", "slai", "fal", "openai", "deepseek", "kie")
_CACHE_PREFIX = "provider_key_balance:"
_DAY_PREFIX = "provider_key_balance_day:"
_DEFAULT_TTL = 45
_DAY_TTL_SECONDS = 60 * 60 * 40  # cover past UTC midnight with margin


class RedisProtocol(Protocol):
    async def get(self, key: str) -> str | bytes | None: ...

    async def setex(self, key: str, seconds: int, value: str) -> Any: ...


class KeyPoolProtocol(Protocol):
    async def list_keys(self, provider: str) -> list[Any]: ...

    async def get_decrypted_key_value(self, key_id: UUID) -> str: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def compute_day_usage(
    *,
    current: float,
    start: float | None,
    last: float | None,
) -> tuple[float, float]:
    """Return ``(day_start_balance, used_today)`` from balance drop.

    - First reading of the day: start = current, used = 0
    - Balance dropped: used = start - current
    - Top-up (current > last): shift start up by the increase so prior usage
      for the day is preserved
    """
    if start is None:
        return float(current), 0.0
    new_start = float(start)
    if last is not None and current > last + 1e-9:
        new_start = float(start) + (float(current) - float(last))
    used = max(0.0, new_start - float(current))
    return new_start, used


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_suno(raw: dict[str, Any]) -> tuple[float | None, str | None, str]:
    """Legacy reseller payloads return ``{"code":200,"data":100}`` (data is int) or nested credits."""
    data = raw.get("data")
    # Official shape: data is the remaining credit count itself.
    if isinstance(data, (int, float, str)) and not isinstance(data, bool):
        amount = _as_float(data)
        if amount is not None:
            return amount, None, "credits"
    payload = data if isinstance(data, dict) else raw
    credits = (
        payload.get("credits")
        or payload.get("credit")
        or payload.get("balance")
        or payload.get("credit_balance")
        or payload.get("remaining_credits")
        or raw.get("credits")
        or raw.get("balance")
    )
    amount = _as_float(credits)
    return amount, None, "credits"


def _normalize_deepseek(raw: dict[str, Any]) -> tuple[float | None, str | None, str]:
    infos = raw.get("balance_infos") or []
    if not isinstance(infos, list) or not infos:
        return None, None, "currency"
    # Prefer USD, else first entry.
    chosen = None
    for info in infos:
        if isinstance(info, dict) and str(info.get("currency", "")).upper() == "USD":
            chosen = info
            break
    if chosen is None:
        chosen = infos[0] if isinstance(infos[0], dict) else {}
    amount = _as_float(chosen.get("total_balance"))
    currency = str(chosen.get("currency") or "USD")
    return amount, currency, "currency"


def _normalize_fal(raw: dict[str, Any]) -> tuple[float | None, str | None, str]:
    credits = raw.get("credits") if isinstance(raw.get("credits"), dict) else {}
    amount = _as_float(credits.get("current_balance"))
    currency = str(credits.get("currency") or "USD")
    return amount, currency, "currency"


# Official SLAI balance host (distinct from generation host api.slai.shop).
_SLAI_BALANCE_URL = "https://slai-api.slai.shop/v1/balance"
# Ledger stores micro-units; dashboard credits = availableUnits / 1_000_000.
_SLAI_UNITS_PER_CREDIT = 1_000_000


def _normalize_slai(raw: dict[str, Any]) -> tuple[float | None, str | None, str]:
    """SLAI ``GET /v1/balance`` → display credits from ``availableUnits``."""
    payload = raw.get("balance")
    balance = payload if isinstance(payload, dict) else raw
    units = _as_float(
        balance.get("availableUnits")
        if isinstance(balance, dict)
        else None
    )
    if units is None and isinstance(balance, dict):
        units = _as_float(balance.get("available_units"))
    if units is None:
        return None, None, "credits"
    return units / _SLAI_UNITS_PER_CREDIT, None, "credits"


def _normalize_kie(raw: dict[str, Any]) -> tuple[float | None, str | None, str]:
    """kie.ai ``GET /api/v1/chat/credit`` → ``{"code":200,"data":100}``."""
    data = raw.get("data")
    if isinstance(data, (int, float, str)) and not isinstance(data, bool):
        amount = _as_float(data)
        if amount is not None:
            return amount, None, "credits"
    payload = data if isinstance(data, dict) else raw
    credits = payload.get("credits") or payload.get("balance") or raw.get("credits")
    amount = _as_float(credits)
    return amount, None, "credits"


class ProviderKeyBalanceService:
    """Query remaining balance for every key-pool entry (by label)."""

    def __init__(
        self,
        *,
        redis: RedisProtocol | None,
        key_pool,
        settings,
        cache_ttl_seconds: int = _DEFAULT_TTL,
    ) -> None:
        self._redis = redis
        self._key_pool = key_pool
        self._settings = settings
        self._cache_ttl = max(15, int(cache_ttl_seconds))

    async def get_all_balances(self, *, force_refresh: bool = False) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        for provider in BALANCE_PROVIDERS:
            providers.append(await self._balances_for_provider(provider, force_refresh=force_refresh))
        return {"providers": providers, "checked_at": _now_iso()}

    async def _balances_for_provider(
        self, provider: str, *, force_refresh: bool
    ) -> dict[str, Any]:
        if self._key_pool is None:
            return {
                "provider": provider,
                "keys": [],
                "error": "Key pool is not configured",
            }
        try:
            entries = await self._key_pool.list_keys(provider)
        except Exception as exc:
            logger.warning("Failed listing keys for %s: %s", provider, exc)
            return {"provider": provider, "keys": [], "error": str(exc)[:200]}

        results = await asyncio.gather(
            *[
                self._balance_for_key(provider, entry, force_refresh=force_refresh)
                for entry in entries
            ]
        )
        return {"provider": provider, "keys": list(results)}

    async def _balance_for_key(
        self, provider: str, entry: Any, *, force_refresh: bool
    ) -> dict[str, Any]:
        key_id = entry.id
        base = {
            "key_id": str(key_id),
            "label": str(entry.label),
            "key_status": str(getattr(entry.status, "value", entry.status)),
            "priority": int(getattr(entry, "priority", 50) or 50),
            "balance": None,
            "currency": None,
            "unit": "credits",
            "display": None,
            "fetch_status": "unknown",
            "error": None,
            "checked_at": _now_iso(),
            "raw": None,
            "used_today": None,
            "day_start_balance": None,
        }

        cache_key = f"{_CACHE_PREFIX}{provider}:{key_id}"
        if not force_refresh:
            cached = await self._read_cache(cache_key)
            if cached is not None:
                cached["key_status"] = base["key_status"]
                cached["label"] = base["label"]
                cached["priority"] = base["priority"]
                if cached.get("fetch_status") == "ok":
                    cached["fetch_status"] = "cached"
                await self._attach_day_usage(
                    cached,
                    provider=provider,
                    key_id=str(key_id),
                    # Cache hit: no top-up detection vs a prior sample in this call.
                    previous_balance=_as_float(cached.get("balance")),
                )
                return cached

        try:
            api_key = await self._key_pool.get_decrypted_key_value(key_id)
        except Exception as exc:
            base["fetch_status"] = "error"
            base["error"] = f"decrypt failed: {str(exc)[:120]}"
            return base

        try:
            previous_balance = None
            if force_refresh:
                prev_cached = await self._read_cache(cache_key)
                if prev_cached is not None:
                    previous_balance = _as_float(prev_cached.get("balance"))

            amount, currency, unit, raw, fetch_status, error = await self._fetch_provider_balance(
                provider, api_key, base_url=getattr(entry, "base_url", None)
            )
            base["balance"] = amount
            base["currency"] = currency
            base["unit"] = unit
            base["fetch_status"] = fetch_status
            base["error"] = error
            base["raw"] = raw
            base["display"] = self._format_display(amount, currency, unit, fetch_status, error)
            await self._attach_day_usage(
                base,
                provider=provider,
                key_id=str(key_id),
                previous_balance=previous_balance if previous_balance is not None else amount,
            )
            if fetch_status in {"ok", "unsupported"}:
                await self._write_cache(cache_key, base)
            return base
        except Exception as exc:
            logger.warning("Balance fetch failed provider=%s label=%s: %s", provider, entry.label, exc)
            base["fetch_status"] = "error"
            base["error"] = str(exc)[:200]
            base["display"] = "Error"
            return base

    async def _attach_day_usage(
        self,
        payload: dict[str, Any],
        *,
        provider: str,
        key_id: str,
        previous_balance: float | None,
    ) -> None:
        """Stamp ``used_today`` / ``day_start_balance`` from Redis day snapshot."""
        amount = _as_float(payload.get("balance"))
        if amount is None:
            payload["used_today"] = None
            payload["day_start_balance"] = None
            return

        day_key = f"{_DAY_PREFIX}{provider}:{key_id}:{_utc_day()}"
        snap = await self._read_cache(day_key)
        start = _as_float(snap.get("start")) if isinstance(snap, dict) else None
        last = previous_balance
        if last is None and isinstance(snap, dict):
            last = _as_float(snap.get("last"))

        new_start, used = compute_day_usage(current=amount, start=start, last=last)
        payload["day_start_balance"] = new_start
        payload["used_today"] = used
        await self._write_cache_ttl(
            day_key,
            {"start": new_start, "last": amount, "used": used, "updated_at": _now_iso()},
            _DAY_TTL_SECONDS,
        )

    async def _fetch_provider_balance(
        self, provider: str, api_key: str, base_url: str | None = None
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        if provider == "suno":
            return await self._fetch_suno(api_key, base_url=base_url)
        if provider == "deepseek":
            return await self._fetch_deepseek(api_key)
        if provider == "fal":
            return await self._fetch_fal(api_key)
        if provider == "slai":
            return await self._fetch_slai(api_key)
        if provider == "kie":
            return await self._fetch_kie(api_key)
        if provider == "openai":
            return await self._fetch_openai(api_key)
        return None, None, "credits", None, "unsupported", f"Unknown provider: {provider}"

    async def _fetch_suno(
        self, api_key: str, base_url: str | None = None
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        # Each key knows its own upstream host; fall back to the env default.
        base = str(
            base_url or getattr(self._settings, "suno_api_base_url", "") or ""
        ).rstrip("/")
        url = f"{base}/api/v1/generate/credit"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            raw = response.json()
        if not isinstance(raw, dict):
            return None, None, "credits", raw, "error", "Suno credit response was not JSON object"
        # Legacy reseller payloads wrap failures as HTTP 200 + code != 200
        code = raw.get("code")
        if code is not None and int(code) != 200:
            return (
                None,
                None,
                "credits",
                raw,
                "error",
                str(raw.get("msg") or f"Suno credit API code={code}")[:200],
            )
        amount, currency, unit = _normalize_suno(raw)
        if amount is None:
            return None, currency, unit, raw, "error", "Could not parse Suno credit response"
        return amount, currency, unit, raw, "ok", None

    async def _fetch_deepseek(
        self, api_key: str
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        base = str(getattr(self._settings, "deepseek_api_base_url", "") or "https://api.deepseek.com").rstrip("/")
        url = f"{base}/user/balance"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            raw = response.json()
        amount, currency, unit = _normalize_deepseek(raw if isinstance(raw, dict) else {})
        if amount is None:
            return None, currency, unit, raw, "error", "Could not parse DeepSeek balance"
        return amount, currency, unit, raw, "ok", None

    async def _fetch_fal(
        self, api_key: str
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        key = (api_key or "").strip().strip('"').strip("'")
        url = "https://api.fal.ai/v1/account/billing"
        # fal platform keys are typically "key_id:key_secret"
        headers_candidates = [
            {"Authorization": f"Key {key}", "Accept": "application/json"},
            {"Authorization": key, "Accept": "application/json"},
            {"Authorization": f"Bearer {key}", "Accept": "application/json"},
        ]
        if ":" not in key and key:
            # Some stored values are only the secret half — still try Key prefix variants.
            headers_candidates.append(
                {"Authorization": f"Key {key}:{key}", "Accept": "application/json"}
            )
        last_error: str | None = None
        async with httpx.AsyncClient(timeout=20.0) as client:
            for headers in headers_candidates:
                response = await client.get(url, params={"expand": "credits"}, headers=headers)
                if response.status_code in {401, 403}:
                    last_error = f"HTTP {response.status_code}"
                    continue
                if response.status_code >= 400:
                    last_error = f"HTTP {response.status_code}: {(response.text or '')[:120]}"
                    continue
                raw = response.json()
                amount, currency, unit = _normalize_fal(raw if isinstance(raw, dict) else {})
                if amount is None:
                    return None, currency, unit, raw, "error", "Could not parse fal billing credits"
                return amount, currency, unit, raw, "ok", None
        return (
            None,
            "USD",
            "currency",
            None,
            "error",
            (
                f"{last_error or 'fal billing unauthorized'}. "
                "Billing requires an ADMIN-scope key "
                "(fal.ai/dashboard/keys → scope Admin), "
                "header form: Authorization: Key id:secret, "
                "and ?expand=credits. API-scope keys get 403."
            ),
        )
    async def _fetch_slai(
        self, api_key: str
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        """Fetch remaining SLAI credits via official ``GET /v1/balance``."""
        configured = str(
            getattr(self._settings, "slai_api_base_url", "") or ""
        ).rstrip("/")
        candidates = [_SLAI_BALANCE_URL]
        if configured:
            root = configured[:-3] if configured.endswith("/v1") else configured
            alt = f"{root}/v1/balance"
            if alt not in candidates:
                candidates.append(alt)

        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        last_error: str | None = None
        async with httpx.AsyncClient(timeout=20.0) as client:
            for url in candidates:
                try:
                    response = await client.get(url, headers=headers)
                    if response.status_code in {401, 403}:
                        return (
                            None,
                            None,
                            "credits",
                            None,
                            "error",
                            f"SLAI balance unauthorized (HTTP {response.status_code})",
                        )
                    if response.status_code >= 400:
                        last_error = f"HTTP {response.status_code}: {(response.text or '')[:120]}"
                        continue
                    raw = response.json()
                    if not isinstance(raw, dict):
                        last_error = "SLAI balance response was not a JSON object"
                        continue
                    amount, currency, unit = _normalize_slai(raw)
                    if amount is None:
                        return (
                            None,
                            currency,
                            unit,
                            raw,
                            "error",
                            "Could not parse SLAI availableUnits",
                        )
                    return amount, currency, unit, raw, "ok", None
                except Exception as exc:
                    last_error = str(exc)[:160]
                    continue
        return (
            None,
            None,
            "credits",
            None,
            "error",
            last_error or "SLAI balance request failed",
        )

    async def _fetch_kie(
        self, api_key: str
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        """Fetch remaining kie.ai credits via ``GET /api/v1/chat/credit``."""
        base = str(
            getattr(self._settings, "kie_api_base_url", "") or "https://api.kie.ai"
        ).rstrip("/")
        url = f"{base}/api/v1/chat/credit"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            response.raise_for_status()
            raw = response.json()
        if not isinstance(raw, dict):
            return None, None, "credits", raw, "error", "kie.ai credit response was not JSON object"
        code = raw.get("code")
        if code is not None and int(code) != 200:
            return (
                None,
                None,
                "credits",
                raw,
                "error",
                str(raw.get("msg") or f"kie.ai credit API code={code}")[:200],
            )
        amount, currency, unit = _normalize_kie(raw)
        if amount is None:
            return None, currency, unit, raw, "error", "Could not parse kie.ai credit response"
        return amount, currency, unit, raw, "ok", None

    async def _fetch_openai(
        self, api_key: str
    ) -> tuple[float | None, str | None, str, Any, str, str | None]:
        """OpenAI does not expose remaining prepaid balance via API.

        Even Organization Admin keys only unlock usage/costs (spend), not
        leftover credit balance. Remaining balance is browser-dashboard only.
        """
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        # Prove the key type: admin keys can hit organization costs; balance still unavailable.
        from datetime import datetime, timedelta, timezone

        start = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
        costs_url = f"https://api.openai.com/v1/organization/costs?start_time={start}&limit=1"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                costs = await client.get(costs_url, headers=headers)
                if costs.status_code in {200, 400}:
                    # 200/400 means admin auth reached the costs API; still no balance field.
                    return (
                        None,
                        "USD",
                        "currency",
                        None,
                        "unsupported",
                        "OpenAI has no remaining-credit API (Admin keys only expose spend/costs). "
                        "Check platform.openai.com → Settings → Billing.",
                    )
                if costs.status_code in {401, 403}:
                    # Not an admin key (or wrong org) — still no balance API either.
                    return (
                        None,
                        "USD",
                        "currency",
                        None,
                        "unsupported",
                        "OpenAI does not expose remaining credit via API. "
                        "Check platform.openai.com → Settings → Billing.",
                    )
                return (
                    None,
                    "USD",
                    "currency",
                    None,
                    "unsupported",
                    "OpenAI does not expose remaining credit via API. "
                    "Check platform.openai.com → Settings → Billing.",
                )
        except Exception:
            return (
                None,
                "USD",
                "currency",
                None,
                "unsupported",
                "OpenAI does not expose remaining credit via API. "
                "Check platform.openai.com → Settings → Billing.",
            )

    @staticmethod
    def _format_display(
        amount: float | None,
        currency: str | None,
        unit: str,
        fetch_status: str,
        error: str | None,
    ) -> str:
        if fetch_status == "unsupported":
            return "N/A — check provider site"
        if amount is None:
            return error or "Unknown"
        if unit == "currency":
            cur = currency or "USD"
            return f"{amount:,.2f} {cur}"
        label = "units" if unit == "units" else "credits"
        if amount == int(amount):
            return f"{int(amount):,} {label}"
        return f"{amount:,.2f} {label}"

    async def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        if self._redis is None:
            return None
        try:
            cached = await self._redis.get(cache_key)
            if cached is None:
                return None
            raw = cached if isinstance(cached, str) else cached.decode("utf-8")
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    async def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        await self._write_cache_ttl(cache_key, payload, self._cache_ttl)

    async def _write_cache_ttl(
        self, cache_key: str, payload: dict[str, Any], ttl_seconds: int
    ) -> None:
        if self._redis is None:
            return
        try:
            to_store = dict(payload)
            if cache_key.startswith(_DAY_PREFIX):
                to_store.pop("raw", None)
            elif isinstance(to_store.get("raw"), (dict, list)):
                pass  # keep raw for short balance cache
            await self._redis.setex(
                cache_key, max(15, int(ttl_seconds)), json.dumps(to_store, default=str)
            )
        except Exception:
            logger.debug("Failed to cache provider balance %s", cache_key, exc_info=True)
