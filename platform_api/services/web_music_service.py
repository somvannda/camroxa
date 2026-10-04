"""Consumer music-web generation: quota, submit, list, download proxy."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi.responses import Response, StreamingResponse

from platform_api.ai.purposes.vocal_profile import truncate_suno_style
from platform_api.ai.registry import DEFAULT_SUNO_MUSIC_MODEL, SUNO_MUSIC_MODEL_IDS
from platform_api.exceptions import (
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    PlatformAPIError,
    QuotaExceededError,
    RateLimitedError,
    ValidationError,
)
from platform_api.models.enums import TaskStatus
from platform_api.models.products import (
    SUNO_TASK_SOURCE_WEB_MUSIC,
    WEB_MUSIC_CREDITS_PER_SONG,
)
from platform_api.ports.generation_port import SunoRequest
from platform_api.services.billing_calendar import billing_today
from platform_api.services.generation_service import GenerationService
from platform_api.services.suno_audio_resolver import (
    download_suno_mp3_bytes,
    download_suno_wav_bytes,
    fetch_timestamped_lrc_with_pool,
    refresh_suno_task_download_urls,
    urls_from_generate_poll,
    validate_mp3_bytes,
    validate_wav_bytes,
    variant_url_candidates,
)
from platform_api.services.streaming_upload_service import StreamingUploadService
from platform_api.services.audio_origin_proxy import (
    bounded_mp3_response,
    is_camxora_audio_proxy_url,
    is_initial_play_range,
    proxy_origin_audio,
)
from platform_api.services.storage_service import StorageServiceError
from platform_api.http_paths import canonical_api_path
from platform_api.services.web_music_play_tokens import (
    create_play_token,
    play_url_for_token,
    resolve_play_token,
)
from platform_api.services.suno_lrc import lrc_to_srt, looks_like_lrc

logger = logging.getLogger(__name__)

_DEFAULT_SLIDER_VALUE = 0.5


def _b2_key_is_task_scoped(storage_key: str | None, task_id: UUID) -> bool:
    """True when the object path contains this task id (not a shared untitled-ok.mp3)."""
    parts = [part for part in str(storage_key or "").replace("\\", "/").split("/") if part]
    return str(task_id) in parts


def _usable_web_music_b2_key(storage_key: Any, task_id: UUID) -> str | None:
    key = str(storage_key or "").strip()
    if key and _b2_key_is_task_scoped(key, task_id):
        return key
    return None


def _clip_is_playable(row: Any, *, variant: str, task_id: UUID) -> bool:
    """True when this clip can stream from our B2 (encrypted or legacy plaintext)."""
    variant_key = "alt" if str(variant or "ok").strip().lower() == "alt" else "ok"
    pkg = str(_row_value(row, "package_status_ok" if variant_key == "ok" else "package_status_alt") or "")
    if pkg == "ready":
        return True
    packaged = _row_value(
        row, "packaged_storage_key_ok" if variant_key == "ok" else "packaged_storage_key_alt"
    )
    if packaged:
        return True
    b2_col = "b2_storage_key_ok" if variant_key == "ok" else "b2_storage_key_alt"
    return bool(_usable_web_music_b2_key(_row_value(row, b2_col), task_id))


def _normalize_slider(value: float | None, *, default: float = _DEFAULT_SLIDER_VALUE) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if 0 <= parsed <= 1:
        return parsed
    return default

_VALID_MODELS = frozenset(SUNO_MUSIC_MODEL_IDS)

_WEB_MUSIC_STYLE_SYSTEM_PROMPT = (
    "You are a Suno AI music production prompt engineer.\n"
    "Turn the user's notes into ONE Suno-ready style string for the style field.\n\n"
    "Rules:\n"
    "- START from the user's Styles field text. Preserve their genres, instruments, mood, and BPM when present.\n"
    "- EXPAND sparse input (e.g. \"pop\", \"sad\") into specific production detail: subgenre, tempo/BPM, "
    "instrumentation, mix texture, energy, and vocal character.\n"
    "- REFINE messy input: dedupe tags, tighten wording, use clear comma-separated descriptors.\n"
    "- If title, lyrics, or song description are provided, align mood/genre with them but do NOT quote lyrics.\n"
    "- Output ONLY the final style string — no labels, quotes, markdown, numbering, or explanation.\n"
    "- Format like Suno examples: \"urbano, electric guitar, upbeat rock, 128 BPM, eurodance, crisp drums, warm bass\"\n"
    "- Include tempo/BPM when helpful. Mention key instruments and vocal tone when relevant.\n"
    "- Do NOT include negative tags or \"avoid/no\" language (the user sets those separately).\n"
    "- Stay under 1000 characters."
)


def build_web_music_style_user_prompt(
    *,
    style: str = "",
    lyrics: str = "",
    title: str = "",
    description: str = "",
    prompt: str = "",
) -> str:
    """Build the LLM user message for Suno style enhancement."""
    style_text = str(style or prompt or "").strip()
    lyrics_text = str(lyrics or "").strip()
    title_text = str(title or "").strip()
    description_text = str(description or "").strip()

    parts: list[str] = []
    if style_text:
        parts.append(
            "User's current Styles field (expand, refine, and turn this into a proper Suno style prompt):\n"
            f"{style_text}"
        )
    if title_text:
        parts.append(f"Song title (for mood/genre context only):\n{title_text}")
    if description_text:
        parts.append(f"Song description (for mood/genre context only):\n{description_text}")
    if lyrics_text:
        excerpt = lyrics_text[:400] + ("…" if len(lyrics_text) > 400 else "")
        parts.append(f"Lyrics excerpt (for mood/genre context only — do not quote lyrics in output):\n{excerpt}")

    if not parts:
        raise ValidationError(
            "Add style tags or a song description before generating styles.",
            details={"field": "style"},
        )
    return "\n\n".join(parts)


_AI_ASSIST_UNAVAILABLE = "AI assist is temporarily unavailable. Please try again in a moment."


def reraise_text_assist_failure(exc: BaseException) -> None:
    """Map LLM/provider failures to a user-facing 502 after credits are refunded."""
    if isinstance(exc, (ValidationError, QuotaExceededError)):
        raise exc
    logger.exception("text-assist LLM failed: %s", type(exc).__name__)
    details = getattr(exc, "details", None)
    raise ExternalServiceError(
        _AI_ASSIST_UNAVAILABLE,
        is_retryable=True,
        details=details if isinstance(details, dict) else None,
    ) from exc


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


def _clip_display_title(row: Any, *, variant: str, fallback: str) -> str:
    key = "title_ok" if str(variant or "ok").strip().lower() != "alt" else "title_alt"
    custom = str(_row_value(row, key) or "").strip()
    return custom or fallback


def _duration_seconds(row: Any, key: str) -> float | None:
    raw = _row_value(row, key)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


class WebMusicService:
    def __init__(
        self,
        pool: Any,
        generation_service: GenerationService,
        credit_service: Any | None = None,
        ai_routing_service: Any | None = None,
        pricing_service: Any | None = None,
        redis: Any | None = None,
        v3_billing: Any | None = None,
        v3_grant: Any | None = None,
        v3_store: Any | None = None,
        credit_repo: Any | None = None,
        settings_repo: Any | None = None,
    ) -> None:
        self._pool = pool
        self._generation = generation_service
        self._credit_service = credit_service
        self._ai_routing = ai_routing_service
        self._pricing = pricing_service
        self._redis = redis
        self._v3_billing = v3_billing
        self._v3_grant = v3_grant
        self._v3_store = v3_store
        self._credit_repo = credit_repo
        self._settings_repo = settings_repo
        self._upload_service = StreamingUploadService(pool)
        self._open_charges: dict[str, Any] = {}

    async def usage_today(self, user_id: UUID, *, usage_date: date | None = None) -> dict[str, Any]:
        """Return credit-based quota for the create UI."""
        if await self._credits_only_v3_enabled():
            return await self._usage_today_v3(user_id)

        if self._credit_service is None:
            is_pro = await self._has_pro(user_id)
            return await self._with_queue_fields(
                user_id, self._quota_payload(limit=0, used=0, is_pro=is_pro)
            )

        balance = await self._credit_service.get_detailed_balance(str(user_id))
        songs_remaining = balance.total_available // WEB_MUSIC_CREDITS_PER_SONG
        requires_upgrade = balance.total_available < WEB_MUSIC_CREDITS_PER_SONG
        is_pro = balance.has_subscription or await self._has_pro(user_id)
        # Free users may download their own generated tracks (MP3/WAV/LRC/SRT).
        can_download = True

        return await self._with_queue_fields(
            user_id,
            {
                "limit": balance.daily_free_limit if not balance.has_subscription else balance.monthly_granted,
                "used": balance.daily_free_used if not balance.has_subscription else balance.monthly_used,
                "remaining": songs_remaining,
                "is_pro": is_pro,
                "requires_upgrade": requires_upgrade and not await self._has_pro(user_id),
                "credits_remaining": balance.total_available,
                "credits_per_song": WEB_MUSIC_CREDITS_PER_SONG,
                "has_subscription": balance.has_subscription,
                "can_download": can_download,
                "daily_free_remaining": balance.daily_free_remaining,
                "daily_free_limit": balance.daily_free_limit,
            },
        )

    async def has_generation_credits(self, user_id: UUID) -> bool:
        """True when the user can pay for a generation from their own balance.

        Paid plans and any positive available balance count, including the
        free daily credit grant. Used to exempt credit-funded users from the
        per-IP daily generation farm cap (abuse_detection); their credits are
        then the only gate on how many songs they generate per day.
        """
        try:
            if await self._has_pro(user_id):
                return True

            if await self._credits_only_v3_enabled():
                spendable, _music_credits, paid_web = (
                    await self._web_music_charge_bridge().spendable_credits(user_id)
                )
                return paid_web or spendable > 0

            if self._credit_service is None:
                return False
            balance = await self._credit_service.get_detailed_balance(str(user_id))
            return bool(balance.has_subscription) or int(balance.total_available) > 0
        except Exception:
            logger.debug(
                "Credit check for generation cap failed for %s", user_id, exc_info=True
            )
            return False

    async def _is_paid_queue_user(self, user_id: UUID) -> bool:
        if self._credit_service is not None:
            try:
                balance = await self._credit_service.get_detailed_balance(str(user_id))
                if bool(getattr(balance, "has_subscription", False)):
                    return True
            except Exception:
                logger.debug("Paid-queue balance check failed for %s", user_id, exc_info=True)
        if await self._credits_only_v3_enabled():
            _, _, paid_web = await self._web_music_charge_bridge().spendable_credits(user_id)
            if paid_web:
                return True
        return await self._has_pro(user_id)

    async def _queue_cap_for_user(self, user_id: UUID) -> int:
        from platform_api.services.job_types import (
            WEB_MUSIC_GENERATE_QUEUE_CAP_FREE,
            WEB_MUSIC_GENERATE_QUEUE_CAP_PAID,
        )

        if await self._is_paid_queue_user(user_id):
            return WEB_MUSIC_GENERATE_QUEUE_CAP_PAID
        return WEB_MUSIC_GENERATE_QUEUE_CAP_FREE

    async def _active_generate_queue_count(self, user_id: UUID) -> int:
        from platform_api.dependencies import get_job_queue_repo
        from platform_api.services.job_types import JOB_WEB_MUSIC_GENERATE

        try:
            return await get_job_queue_repo().count_active_for_user(
                user_id, JOB_WEB_MUSIC_GENERATE
            )
        except Exception:
            logger.debug("Generate queue count failed for %s", user_id, exc_info=True)
            return 0

    async def _with_queue_fields(self, user_id: UUID, quota: dict[str, Any]) -> dict[str, Any]:
        payload = dict(quota)
        payload["queue_limit"] = await self._queue_cap_for_user(user_id)
        payload["queue_used"] = await self._active_generate_queue_count(user_id)
        return payload

    async def _has_pro(self, user_id: UUID) -> bool:
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM licenses
            WHERE user_id = $1
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            user_id,
        )
        return row is not None

    async def _has_web_subscription(self, user_id: UUID) -> bool:
        """Check if user has an active web music subscription."""
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM web_subscriptions
            WHERE user_id = $1
              AND status = 'active'
              AND (cancel_at_period_end = false OR current_period_end > NOW())
            LIMIT 1
            """,
            user_id,
        )
        return row is not None

    async def _has_paid_web_subscription(self, user_id: UUID) -> bool:
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM web_subscriptions ws
            INNER JOIN plans p ON p.id = ws.plan_id
            WHERE ws.user_id = $1
              AND ws.status = 'active'
              AND ws.current_period_end > NOW()
              AND COALESCE(p.price_cents, 0) > 0
            LIMIT 1
            """,
            user_id,
        )
        return row is not None

    async def _credits_only_v3_enabled(self) -> bool:
        from platform_api.services.v3.generate_charge import (
            CREDITS_ONLY_V3_CHARGE_SETTING_KEY,
            credits_only_v3_charge_enabled,
            parse_bool_flag,
        )

        if self._settings_repo is not None:
            return await credits_only_v3_charge_enabled(self._settings_repo)
        try:
            row = await self._pool.fetchrow(
                "SELECT value FROM system_settings WHERE key = $1",
                CREDITS_ONLY_V3_CHARGE_SETTING_KEY,
            )
            raw = row["value"] if row is not None else None
            parsed = parse_bool_flag(raw)
            if parsed is not None:
                return parsed
        except Exception:
            logger.debug("credits_only_v3_charge lookup failed; using env default", exc_info=True)
        return await credits_only_v3_charge_enabled(None)

    def _web_music_charge_bridge(self) -> Any:
        from platform_api.services.v3.web_music_charge import WebMusicChargeBridge

        return WebMusicChargeBridge(
            v3_billing=self._v3_billing_service(),
            v3_grant=self._v3_grant_service(),
            v3_store=self._v3_store_service(),
            credit_repo=self._credit_repo_service(),
            credit_service=self._credit_service,
            has_paid_web_subscription=self._has_paid_web_subscription,
        )

    def _v3_billing_service(self) -> Any:
        if self._v3_billing is not None:
            return self._v3_billing
        from platform_api.dependencies import get_v3_billing_service

        return get_v3_billing_service()

    def _v3_grant_service(self) -> Any:
        if self._v3_grant is not None:
            return self._v3_grant
        from platform_api.dependencies import get_v3_grant_service

        return get_v3_grant_service()

    def _v3_store_service(self) -> Any:
        if self._v3_store is not None:
            return self._v3_store
        from platform_api.dependencies import get_v3_store

        return get_v3_store()

    def _credit_repo_service(self) -> Any:
        if self._credit_repo is not None:
            return self._credit_repo
        from platform_api.dependencies import get_credit_repo

        return get_credit_repo()

    def _public_quota(
        self,
        *,
        credits_remaining: int,
        credits_per_song: int,
        is_pro: bool,
        has_subscription: bool,
        daily_free_remaining: int = 0,
        daily_free_limit: int = 0,
        limit: int = 0,
        used: int = 0,
    ) -> dict[str, Any]:
        per_song = max(1, int(credits_per_song or WEB_MUSIC_CREDITS_PER_SONG))
        remaining_songs = max(0, int(credits_remaining)) // per_song
        return {
            "limit": limit,
            "used": used,
            "remaining": remaining_songs,
            "is_pro": is_pro,
            "requires_upgrade": int(credits_remaining) < per_song,
            "credits_remaining": int(credits_remaining),
            "credits_per_song": per_song,
            "has_subscription": has_subscription,
            "can_download": True,
            "daily_free_remaining": daily_free_remaining,
            "daily_free_limit": daily_free_limit,
        }

    async def _usage_today_v3(self, user_id: UUID) -> dict[str, Any]:
        spendable, music_credits, paid_web = await self._web_music_charge_bridge().spendable_credits(
            user_id
        )
        is_pro = await self._has_pro(user_id)
        has_subscription = paid_web or await self._has_web_subscription(user_id)
        daily_limit = 0
        daily_remaining = 0
        if not is_pro and not paid_web:
            plan = await self._v3_store_service().get_active_free_plan()
            daily_limit = int((plan or {}).get("daily_credits") or 0)
            daily_remaining = spendable
        return await self._with_queue_fields(
            user_id,
            self._public_quota(
                credits_remaining=spendable,
                credits_per_song=music_credits or WEB_MUSIC_CREDITS_PER_SONG,
                is_pro=is_pro,
                has_subscription=has_subscription,
                daily_free_remaining=daily_remaining,
                daily_free_limit=daily_limit,
                limit=daily_limit if not paid_web and not is_pro else spendable,
                used=max(0, daily_limit - daily_remaining) if daily_limit else 0,
            ),
        )

    async def _can_download(self, user_id: UUID) -> bool:
        if await self._has_pro(user_id):
            return True
        return await self._has_web_subscription(user_id)

    async def _require_download_access(self, user_id: UUID) -> None:
        # Free users are allowed to download the tracks they generated.
        # Ownership is enforced per-row inside every download path
        # (WHERE user_id = ...), so no subscription/pro gate applies here.
        del user_id
        return

    def _quota_payload(
        self,
        *,
        limit: int,
        used: int,
        is_pro: bool,
    ) -> dict[str, Any]:
        remaining = 0 if is_pro else max(0, limit - used)
        requires_upgrade = (not is_pro) and remaining <= 0
        return {
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "is_pro": is_pro,
            "requires_upgrade": requires_upgrade,
        }

    async def _charge_for_text_operation(
        self,
        user_id: UUID,
        *,
        operation: str,
        consume_source: str,
    ) -> tuple[Any, Any, int]:
        """Resolve routing, charge display credits, return (routing, chain, charged_amount)."""
        import math

        from platform_api.services.credit_units import units_to_credits
        from platform_api.services.v2.credit_service import InsufficientCreditsError

        if self._ai_routing is None or self._pricing is None:
            raise ValidationError(
                "AI assist is not configured.",
                details={"reason": "missing_routing_or_pricing"},
            )
        if self._credit_service is None and not await self._credits_only_v3_enabled():
            raise ValidationError(
                "AI assist is not configured.",
                details={"reason": "missing_routing_or_pricing"},
            )

        routing = await self._ai_routing.resolve(operation)
        chain = await self._ai_routing.resolve_text_chain(operation)

        if await self._credits_only_v3_enabled():
            reservation_id = str(uuid4())
            charged = await self._web_music_charge_bridge().charge(
                user_id,
                operation,
                ref_id=reservation_id,
            )
            self._open_charges[reservation_id] = charged
            self._open_charges[f"text:{user_id}:{operation}"] = charged
            return routing, chain, charged.amount_credits

        if self._credit_service is None:
            raise ValidationError(
                "AI assist is not configured.",
                details={"reason": "missing_routing_or_pricing"},
            )

        provider = str(routing.provider)
        sub_model = str(routing.sub_model or "").strip() or None
        price_units = int(await self._pricing.get_price(provider, operation, sub_model))
        if price_units <= 0:
            raise ValidationError(
                f"Pricing is not configured for {operation}. Add it in Admin → Credits.",
                details={"operation": operation, "provider": provider},
            )

        display_price = units_to_credits(price_units)
        charge_amount = max(1, int(math.ceil(display_price))) if display_price > 0 else 1
        balance = await self._credit_service.get_total_balance(str(user_id))
        if balance < charge_amount:
            raise QuotaExceededError(
                f"This action needs {charge_amount} credits. You have {balance}.",
                details={
                    "credits_required": charge_amount,
                    "credits_available": balance,
                    "requires_upgrade": True,
                },
            )
        try:
            await self._credit_service.consume_credits(str(user_id), charge_amount, consume_source)
        except InsufficientCreditsError as exc:
            raise QuotaExceededError(
                "Subscribe or top up to use AI assist.",
                details={"requires_upgrade": True},
            ) from exc
        return routing, chain, charge_amount

    async def _refund_text_operation(self, user_id: UUID, amount: int, source: str) -> None:
        if await self._credits_only_v3_enabled():
            operation = "lyric" if "lyric" in source else "style" if "style" in source else source
            charge = self._open_charges.pop(f"text:{user_id}:{operation}", None)
            if charge is None and "lyric" in source:
                charge = self._open_charges.pop(f"text:{user_id}:web_music_lyrics", None)
            if charge is None and "style" in source:
                charge = self._open_charges.pop(f"text:{user_id}:web_music_style", None)
            if charge is not None:
                await self._web_music_charge_bridge().refund(user_id, charge)
            return
        if self._credit_service is None or amount <= 0:
            return
        await self._credit_service.refund_credits(str(user_id), amount, source)

    async def generate_draft(self, user_id: UUID, prompt: str) -> tuple[str, str]:
        """Generate lyrics and title via configured text LLM (credit-priced)."""
        safe_prompt = str(prompt or "").strip()
        if not safe_prompt:
            raise ValidationError("Describe the song for lyric generation.", details={"field": "prompt"})

        routing, chain, charged = await self._charge_for_text_operation(
            user_id,
            operation="web_music_lyrics",
            consume_source="web_music_lyrics",
        )
        provider = str(routing.provider)
        provider_chain = [
            (str(item.provider), str(item.sub_model or ""))
            for item in chain
            if str(item.sub_model or "").strip()
        ]
        system_prompt = (
            "Write original song lyrics for AI music generation. "
            "Return exactly in this format:\n"
            "TITLE: <short song title>\n"
            "---\n"
            "<lyrics with verses and chorus, no markdown>"
        )
        try:
            raw = await self._generation.generate_text(
                system_prompt=system_prompt,
                user_prompt=safe_prompt[:5000],
                provider=provider,
                model=str(routing.sub_model or ""),
                temperature=0.9,
                max_tokens=900,
                provider_chain=provider_chain or None,
            )
        except Exception as exc:
            await self._refund_text_operation(user_id, charged, "web_music_lyrics_refund")
            reraise_text_assist_failure(exc)

        text = str(raw or "").strip()
        title = "Untitled"
        lyrics = text
        if "TITLE:" in text.upper():
            head, _, body = text.partition("\n")
            title = head.split(":", 1)[1].strip() or title
            lyrics = body.strip()
        if lyrics.startswith("---"):
            lyrics = lyrics[3:].strip()
        if not lyrics:
            lyrics = text
        if not title or title == "Untitled":
            first_line = next((line.strip() for line in lyrics.splitlines() if line.strip()), "")
            title = first_line[:80] or safe_prompt[:80] or "Untitled"
        self._open_charges.pop(f"text:{user_id}:web_music_lyrics", None)
        return lyrics[:5000], title[:200]

    async def generate_styles(
        self,
        user_id: UUID,
        *,
        style: str = "",
        lyrics: str = "",
        title: str = "",
        description: str = "",
        prompt: str = "",
    ) -> str:
        """Generate a Suno-ready style string via configured text LLM (credit-priced)."""
        user_prompt = build_web_music_style_user_prompt(
            style=style,
            lyrics=lyrics,
            title=title,
            description=description,
            prompt=prompt,
        )

        routing, chain, charged = await self._charge_for_text_operation(
            user_id,
            operation="web_music_style",
            consume_source="web_music_style",
        )
        provider = str(routing.provider)
        provider_chain = [
            (str(item.provider), str(item.sub_model or ""))
            for item in chain
            if str(item.sub_model or "").strip()
        ]
        try:
            raw = await self._generation.generate_text(
                system_prompt=_WEB_MUSIC_STYLE_SYSTEM_PROMPT,
                user_prompt=user_prompt[:2000],
                provider=provider,
                model=str(routing.sub_model or ""),
                temperature=0.75,
                max_tokens=320,
                provider_chain=provider_chain or None,
            )
        except Exception as exc:
            await self._refund_text_operation(user_id, charged, "web_music_style_refund")
            reraise_text_assist_failure(exc)

        cleaned = str(raw or "").strip().strip('"').strip("'")
        if cleaned.lower().startswith("style:"):
            cleaned = cleaned.split(":", 1)[1].strip()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if len(lines) > 1:
            cleaned = ", ".join(lines)
        self._open_charges.pop(f"text:{user_id}:web_music_style", None)
        return truncate_suno_style(cleaned)
    
    async def _reserve_via_credits(self, user_id: UUID, *, reservation_id: str) -> dict[str, Any]:
        """Reserve a song slot by consuming credits (subscription or daily free pool)."""
        from platform_api.services.v2.credit_service import InsufficientCreditsError

        if self._credit_service is None:
            logger.error("Credit service not available for user %s", user_id)
            raise QuotaExceededError(
                "Credit system unavailable. Please try again later.",
                details={"requires_upgrade": True},
            )

        user_key = str(user_id)
        balance = await self._credit_service.get_detailed_balance(user_key)

        if balance.total_available < WEB_MUSIC_CREDITS_PER_SONG:
            songs_remaining = balance.total_available // WEB_MUSIC_CREDITS_PER_SONG
            raise QuotaExceededError(
                f"Insufficient credits. You need {WEB_MUSIC_CREDITS_PER_SONG} credits per song. "
                f"You have {balance.total_available} credits ({songs_remaining} songs remaining).",
                details={
                    "credits_required": WEB_MUSIC_CREDITS_PER_SONG,
                    "credits_available": balance.total_available,
                    "songs_remaining": songs_remaining,
                    "requires_upgrade": True,
                },
            )

        try:
            await self._credit_service.consume_credits(
                user_id=user_key,
                amount=WEB_MUSIC_CREDITS_PER_SONG,
                source="web_music_generation",
                reference_id=reservation_id,
            )
        except InsufficientCreditsError as exc:
            raise QuotaExceededError(
                str(exc),
                details={"requires_upgrade": True},
            ) from exc

        updated = await self._credit_service.get_detailed_balance(user_key)
        songs_remaining = updated.total_available // WEB_MUSIC_CREDITS_PER_SONG

        logger.info(
            "User %s consumed %s credits for music generation. Remaining: %s credits (%s songs)",
            user_id,
            WEB_MUSIC_CREDITS_PER_SONG,
            updated.total_available,
            songs_remaining,
        )

        return {
            "limit": updated.daily_free_limit if not updated.has_subscription else updated.monthly_granted,
            "used": updated.daily_free_used if not updated.has_subscription else updated.monthly_used,
            "remaining": songs_remaining,
            "is_pro": updated.has_subscription or await self._has_pro(user_id),
            "requires_upgrade": False,
            "credits_remaining": updated.total_available,
            "credits_per_song": WEB_MUSIC_CREDITS_PER_SONG,
            "has_subscription": updated.has_subscription,
            "daily_free_remaining": updated.daily_free_remaining,
            "daily_free_limit": updated.daily_free_limit,
        }

    async def _reserve_daily_slot(self, user_id: UUID, *, reservation_id: str) -> dict[str, Any]:
        if await self._credits_only_v3_enabled():
            charged = await self._web_music_charge_bridge().charge(
                user_id,
                "music",
                ref_id=reservation_id,
            )
            self._open_charges[reservation_id] = charged
            spendable, music_credits, paid_web = await self._web_music_charge_bridge().spendable_credits(
                user_id
            )
            is_pro = await self._has_pro(user_id)
            return self._public_quota(
                credits_remaining=spendable,
                credits_per_song=charged.amount_credits or music_credits or WEB_MUSIC_CREDITS_PER_SONG,
                is_pro=is_pro,
                has_subscription=paid_web or await self._has_web_subscription(user_id),
            )

        if await self._has_pro(user_id):
            logger.info("Desktop Pro user %s creating on web music without credit charge", user_id)
            return self._quota_payload(limit=999, used=0, is_pro=True)

        return await self._reserve_via_credits(user_id, reservation_id=reservation_id)

    async def _release_daily_slot(
        self,
        user_id: UUID,
        *,
        reference_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        if await self._credits_only_v3_enabled():
            charge = self._open_charges.pop(reference_id, None) if reference_id else None
            if charge is not None:
                await self._web_music_charge_bridge().refund(user_id, charge)
                return
            # The charge lives in the API process's ``_open_charges``; a worker
            # process (or a restarted API) never has it. Reverse the recorded
            # debit instead, idempotently, so a failed song is really refunded.
            await self._refund_v3_music_by_reference(
                user_id,
                reference_id=reference_id,
                task_id=task_id,
            )
            return
        if await self._has_pro(user_id) or self._credit_service is None:
            return
        await self._credit_service.refund_credits(
            str(user_id),
            WEB_MUSIC_CREDITS_PER_SONG,
            "web_music_generation",
            reference_id=reference_id,
        )

    async def _refund_v3_music_by_reference(
        self,
        user_id: UUID,
        *,
        reference_id: str | None,
        task_id: str | None,
    ) -> None:
        """Reverse a v3 ``music`` debit when the in-memory charge is gone.

        The charge is written to ``credit_transactions`` (reason ``v3_music``)
        keyed by the reservation id, which ``_link_generation_debit_reference``
        rewrites to the task id once the job is queued. Either id can be present
        by the time a failed submit is refunded, so match on both. The refund is
        keyed on the debit row id, making worker re-attempts no-ops.
        """
        refs = [ref for ref in (reference_id, task_id) if ref]
        if not refs:
            return
        row = await self._pool.fetchrow(
            """
            SELECT id, amount
            FROM credit_transactions
            WHERE user_id = $1
              AND direction = 'debit'
              AND reason = 'v3_music'
              AND ref_id = ANY($2::text[])
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            refs,
        )
        if row is None:
            logger.warning(
                "No v3_music debit to refund user=%s refs=%s", user_id, refs
            )
            return
        amount_units = int(row["amount"] or 0)
        if amount_units <= 0:
            return
        from platform_api.services.credit_units import units_to_credits

        await self._v3_refund_billing().refund(
            user_id=user_id,
            op="music",
            amount_credits=units_to_credits(amount_units),
            ref_id=str(row["id"]),
        )

    def _v3_refund_billing(self) -> Any:
        """A refund-only v3 billing service.

        The worker process may not have Redis/usage-enforcement wired (it
        tolerates ``get_redis`` failing), so the durable refund builds the
        credits-only service without the enforcement collaborator rather than
        going through ``get_v3_billing_service``.
        """
        from platform_api.dependencies import (
            get_credit_pricing_service,
            get_credit_repo,
            get_v3_store,
        )
        from platform_api.services.v3.credits_only_billing_service import (
            CreditsOnlyBillingService,
        )

        return CreditsOnlyBillingService(
            store=get_v3_store(),
            credit_repo=get_credit_repo(),
            pricing_service=get_credit_pricing_service(),
            enforcement=None,
        )

    async def _link_generation_debit_reference(
        self,
        user_id: UUID,
        reservation_id: str,
        task_id: str,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE credit_transactions
            SET ref_id = $3
            WHERE user_id = $1
              AND ref_id = $2
              AND direction = 'debit'
              AND reason IN (
                    'consumed_web_music_generation',
                    'consumed_web_music_music',
                    'v3_music'
              )
            """,
            user_id,
            reservation_id,
            task_id,
        )

    async def generate(
        self,
        user_id: UUID,
        *,
        mode: str,
        lyrics: str,
        style: str,
        title: str,
        instrumental: bool,
        model: str,
        prompt: str,
        negative_tags: str | None = None,
        vocal_gender: str | None = None,
        style_weight: float | None = None,
        weirdness_constraint: float | None = None,
        audio_weight: float | None = None,
        workspace_id: UUID | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "service.generate enter user=%s mode=%r instr=%s model=%r title_len=%s lyrics_len=%s style_len=%s prompt_len=%s workspace=%s",
            user_id, mode, instrumental, model, len(title or ""), len(lyrics or ""), len(style or ""), len(prompt or ""), workspace_id,
        )
        normalized_model = str(model or DEFAULT_SUNO_MUSIC_MODEL).strip().upper()
        if normalized_model not in _VALID_MODELS:
            raise ValidationError(
                "model must be one of V6, V6_MINI, V6_WILD, V5_5, V5.",
                details={"field": "model"},
            )
        mode_key = str(mode or "advanced").strip().lower()
        if mode_key not in ("simple", "advanced"):
            raise ValidationError("mode must be simple or advanced.", details={"field": "mode"})

        safe_lyrics = str(lyrics or "").strip()
        safe_prompt = str(prompt or "").strip()
        safe_negative = str(negative_tags or "").strip()
        raw_title = str(title or "").strip()
        safe_style = str(style or "").strip()

        if mode_key == "simple":
            if not safe_prompt:
                raise ValidationError(
                    "Describe the song you want to create.",
                    details={"field": "prompt"},
                )
            if not safe_style:
                safe_style = truncate_suno_style(safe_prompt) or "Contemporary pop"
        else:
            if not instrumental and not safe_lyrics:
                raise ValidationError("Lyrics are required.", details={"field": "lyrics"})
            if not safe_style:
                safe_style = "Contemporary pop"

        from platform_api.dependencies import get_suno_blocklist_service
        from platform_api.services.web_music_suno_guard import (
            is_valid_web_music_title,
            prepare_web_music_title,
            raise_if_suno_blocklisted,
        )

        logger.info("service.generate step blocklist_load user=%s", user_id)
        runtime_config = await get_suno_blocklist_service().get_runtime_config()
        safe_title = prepare_web_music_title(title=raw_title, lyrics=safe_lyrics)
        logger.info("service.generate step title_ready user=%s safe_title=%r", user_id, safe_title[:120])
        if mode_key != "simple":
            if not is_valid_web_music_title(safe_title):
                raise ValidationError(
                    "Enter a song title (at least 2 letters, no URLs or empty brackets).",
                    details={"field": "title", "title": raw_title[:160]},
                )
            logger.info("service.generate step blocklist_check user=%s", user_id)
            raise_if_suno_blocklisted(
                runtime_config,
                title=safe_title,
                lyrics=safe_lyrics if not instrumental else "",
                style=safe_style,
                negative_tags=safe_negative,
            )

        queue_limit = await self._queue_cap_for_user(user_id)
        queue_used = await self._active_generate_queue_count(user_id)
        if queue_used >= queue_limit:
            raise RateLimitedError(
                f"You already have {queue_used} songs waiting. Wait until one starts at Suno.",
                retry_after=5,
                details={"queue_used": queue_used, "queue_limit": queue_limit},
            )

        reservation_id = str(uuid4())
        logger.info("service.generate step reserve user=%s reservation=%s", user_id, reservation_id)
        # Charge only after title/blocklist checks so 422s do not burn daily credits.
        quota = await self._reserve_daily_slot(user_id, reservation_id=reservation_id)
        logger.info("service.generate step reserved_ok user=%s reservation=%s", user_id, reservation_id)

        if mode_key == "simple":
            try:
                logger.info("service.generate step simple_lyrics_llm user=%s", user_id)
                generated_lyrics, generated_title = await self._generation.generate_suno_lyrics(
                    safe_prompt
                )
            except Exception:
                await self._release_daily_slot(user_id, reference_id=reservation_id)
                raise
            safe_lyrics = str(generated_lyrics or "").strip() or safe_prompt
            safe_title = prepare_web_music_title(
                title=raw_title or str(generated_title or ""),
                lyrics=safe_lyrics,
            ) or prepare_web_music_title(title=safe_prompt, lyrics="")
            try:
                if not is_valid_web_music_title(safe_title):
                    raise ValidationError(
                        "Enter a song title (at least 2 letters, no URLs or empty brackets).",
                        details={"field": "title"},
                    )
                raise_if_suno_blocklisted(
                    runtime_config,
                    title=safe_title,
                    lyrics=safe_lyrics if not instrumental else "",
                    style=safe_style,
                    negative_tags=safe_negative,
                )
            except Exception:
                await self._release_daily_slot(user_id, reference_id=reservation_id)
                raise

        stored_style_weight = _normalize_slider(style_weight)
        stored_weirdness = _normalize_slider(weirdness_constraint)
        stored_audio_weight = _normalize_slider(audio_weight)
        stored_vocal_gender = (
            vocal_gender.lower()
            if vocal_gender and vocal_gender.lower() in ("m", "f", "both")
            else None
        )
        try:
            logger.info("service.generate step submit_suno user=%s reservation=%s", user_id, reservation_id)
            task_id = await self._enqueue_web_generate(
                user_id,
                reservation_id=reservation_id,
                model=normalized_model,
                title=safe_title,
                lyrics=safe_lyrics if not instrumental else (safe_lyrics or "Instrumental"),
                style=safe_style,
                instrumental=instrumental,
                negative_tags=safe_negative or None,
                vocal_gender=stored_vocal_gender,
                style_weight=stored_style_weight,
                weirdness_constraint=stored_weirdness,
                audio_weight=stored_audio_weight,
                workspace_id=workspace_id,
            )
            logger.info("service.generate step submitted_ok user=%s reservation=%s task=%s", user_id, reservation_id, task_id)
        except Exception:
            await self._release_daily_slot(user_id, reference_id=reservation_id)
            raise

        await self._link_generation_debit_reference(user_id, reservation_id, str(task_id))
        self._open_charges.pop(reservation_id, None)

        resolved_workspace_id = await self._resolve_workspace_id(user_id, workspace_id)
        return {
            "task_id": str(task_id),
            "status": "QUEUED",
            "title": safe_title,
            "style": safe_style,
            "quota": await self._with_queue_fields(user_id, quota),
            "workspace_id": str(resolved_workspace_id),
        }

    async def _enqueue_web_generate(
        self,
        user_id: UUID,
        *,
        reservation_id: str,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool,
        negative_tags: str | None,
        vocal_gender: str | None,
        style_weight: float,
        weirdness_constraint: float,
        audio_weight: float,
        workspace_id: UUID | None,
    ) -> UUID:
        from platform_api.dependencies import get_job_queue_repo
        from platform_api.services.generation_service import compute_suno_request_hash
        from platform_api.services.job_types import (
            JOB_WEB_MUSIC_GENERATE,
            PRI_WEB_MUSIC_FREE,
            PRI_WEB_MUSIC_PAID,
        )

        task_id = uuid4()
        request_hash = compute_suno_request_hash(
            model=model,
            title=title,
            lyrics=lyrics,
            style=style,
            instrumental=instrumental,
        )
        resolved_workspace_id = await self._resolve_workspace_id(user_id, workspace_id)
        await self._pool.execute(
            """
            INSERT INTO suno_tasks (
                id, user_id, request_hash, model, title, lyrics, style,
                instrumental, external_task_id, status, source, workspace_id,
                negative_tags, vocal_gender, style_weight, weirdness_constraint,
                audio_weight, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8, NULL, $9, $10, $11,
                $12, $13, $14, $15,
                $16, NOW(), NOW()
            )
            """,
            task_id,
            user_id,
            request_hash,
            model,
            title,
            lyrics,
            style,
            instrumental,
            TaskStatus.PENDING.value,
            SUNO_TASK_SOURCE_WEB_MUSIC,
            resolved_workspace_id,
            str(negative_tags).strip() if negative_tags else None,
            vocal_gender,
            style_weight,
            weirdness_constraint,
            audio_weight,
        )
        paid = await self._is_paid_queue_user(user_id)
        await get_job_queue_repo().enqueue(
            user_id=user_id,
            job_type=JOB_WEB_MUSIC_GENERATE,
            payload={
                "user_id": str(user_id),
                "task_id": str(task_id),
                "reservation_id": reservation_id,
            },
            priority=PRI_WEB_MUSIC_PAID if paid else PRI_WEB_MUSIC_FREE,
            max_attempts=3,
        )
        return task_id

    async def fulfill_queued_generate(self, user_id: UUID, task_id: UUID, *, reservation_id: str) -> None:
        """Send one queued web song to Suno. Refunds if Suno never accepts it."""
        row = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, external_task_id,
                   negative_tags, vocal_gender, style_weight, weirdness_constraint,
                   audio_weight
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if row is None:
            raise NotFoundError("Queued song was not found.")
        if str(row["external_task_id"] or "").strip():
            return

        request = SunoRequest(
            model=str(row["model"] or DEFAULT_SUNO_MUSIC_MODEL),
            title=str(row["title"] or ""),
            lyrics=str(row["lyrics"] or "Instrumental"),
            style=str(row["style"] or "Contemporary pop"),
            instrumental=bool(row["instrumental"]),
            negative_tags=str(row["negative_tags"] or "").strip() or None,
            vocal_gender=str(row["vocal_gender"] or "").strip() or None,
            style_weight=row["style_weight"],
            weirdness_constraint=row["weirdness_constraint"],
            audio_weight=row["audio_weight"],
        )
        try:
            external_task_id = await self._generation.submit_suno_external_id(request)
        except Exception:
            await self._release_daily_slot(
                user_id,
                reference_id=reservation_id,
                task_id=str(task_id),
            )
            await self._pool.execute(
                """
                UPDATE suno_tasks
                SET status = $3, error_message = $4, updated_at = NOW()
                WHERE id = $1 AND user_id = $2
                """,
                task_id,
                user_id,
                TaskStatus.FAILED.value,
                "Could not start this song at Suno. Credits were refunded.",
            )
            raise

        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET external_task_id = $3, status = $4, error_message = NULL, updated_at = NOW()
            WHERE id = $1 AND user_id = $2
            """,
            task_id,
            user_id,
            external_task_id,
            TaskStatus.PENDING.value,
        )
        await self._link_generation_debit_reference(user_id, reservation_id, str(task_id))
        self._open_charges.pop(reservation_id, None)

    async def _resolve_workspace_id(
        self,
        user_id: UUID,
        workspace_id: UUID | None,
    ) -> UUID:
        if workspace_id is not None:
            row = await self._pool.fetchrow(
                """
                SELECT id FROM web_music_workspaces
                WHERE id = $1 AND user_id = $2
                """,
                workspace_id,
                user_id,
            )
            if row is None:
                raise NotFoundError(
                    "Workspace not found.",
                    details={"workspace_id": str(workspace_id)},
                )
            return UUID(str(row["id"]))
        return await self.ensure_default_workspace(user_id)

    async def ensure_default_workspace(self, user_id: UUID) -> UUID:
        row = await self._pool.fetchrow(
            """
            SELECT id FROM web_music_workspaces
            WHERE user_id = $1 AND is_default = true
            LIMIT 1
            """,
            user_id,
        )
        if row is not None:
            return UUID(str(row["id"]))
        row = await self._pool.fetchrow(
            """
            INSERT INTO web_music_workspaces (user_id, name, is_default)
            VALUES ($1, 'My Workspace', true)
            RETURNING id
            """,
            user_id,
        )
        return UUID(str(row["id"]))

    async def list_workspaces(self, user_id: UUID) -> list[dict[str, Any]]:
        await self.ensure_default_workspace(user_id)
        rows = await self._pool.fetch(
            """
            SELECT id, name, is_default, created_at
            FROM web_music_workspaces
            WHERE user_id = $1
            ORDER BY is_default DESC, created_at ASC
            """,
            user_id,
        )
        return [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "is_default": bool(row["is_default"]),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
            for row in rows
        ]

    async def create_workspace(self, user_id: UUID, *, name: str) -> dict[str, Any]:
        safe_name = str(name or "").strip()
        if not safe_name:
            raise ValidationError("Workspace name is required.", details={"field": "name"})
        if len(safe_name) > 120:
            raise ValidationError(
                "Workspace name must be 120 characters or fewer.",
                details={"field": "name"},
            )
        row = await self._pool.fetchrow(
            """
            INSERT INTO web_music_workspaces (user_id, name, is_default)
            VALUES ($1, $2, false)
            RETURNING id, name, is_default, created_at
            """,
            user_id,
            safe_name,
        )
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "is_default": bool(row["is_default"]),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }

    async def update_workspace(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        name: str,
    ) -> dict[str, Any]:
        safe_name = str(name or "").strip()
        if not safe_name:
            raise ValidationError("Workspace name is required.", details={"field": "name"})
        if len(safe_name) > 120:
            raise ValidationError(
                "Workspace name must be 120 characters or fewer.",
                details={"field": "name"},
            )
        row = await self._pool.fetchrow(
            """
            UPDATE web_music_workspaces
            SET name = $3
            WHERE id = $1 AND user_id = $2
            RETURNING id, name, is_default, created_at
            """,
            workspace_id,
            user_id,
            safe_name,
        )
        if row is None:
            raise NotFoundError(
                "Workspace not found.",
                details={"workspace_id": str(workspace_id)},
            )
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "is_default": bool(row["is_default"]),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }

    async def list_generations(
        self,
        user_id: UUID,
        *,
        limit: int = 40,
        offset: int = 0,
        workspace_id: UUID | None = None,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        resolved_workspace_id = await self._resolve_workspace_id(user_id, workspace_id)
        total = int(
            await self._pool.fetchval(
                """
                SELECT COUNT(*)::int FROM suno_tasks
                WHERE user_id = $1 AND source = $2 AND workspace_id = $3
                """,
                user_id,
                SUNO_TASK_SOURCE_WEB_MUSIC,
                resolved_workspace_id,
            )
            or 0
        )
        rows = await self._pool.fetch(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   negative_tags, vocal_gender, style_weight, weirdness_constraint, audio_weight,
                   b2_storage_key_ok, b2_storage_key_alt, workspace_id,
                   image_url_ok, image_url_alt, duration_ok, duration_alt,
                   audio_id_ok, audio_id_alt, title_ok, title_alt, stream_ready_ok, stream_ready_alt,
                   encrypted_original_key_ok, encrypted_original_key_alt,
                   package_status_ok, package_status_alt,
                   content_key_id_ok, content_key_id_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE user_id = $1 AND source = $2 AND workspace_id = $3
            ORDER BY created_at DESC
            LIMIT $4 OFFSET $5
            """,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
            resolved_workspace_id,
            safe_limit,
            safe_offset,
        )
        return {
            "items": [await self._task_payload(row, user_id) for row in rows],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    async def get_generation(self, user_id: UUID, task_id: UUID) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id, negative_tags, vocal_gender, style_weight,
                   weirdness_constraint, audio_weight, image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt, duration_ok, duration_alt,
                   audio_id_ok, audio_id_alt, title_ok, title_alt, stream_ready_ok, stream_ready_alt,
                   encrypted_original_key_ok, encrypted_original_key_alt,
                   package_status_ok, package_status_alt,
                   content_key_id_ok, content_key_id_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        row = await self._refresh_pending_from_suno(row)
        row = await self._ensure_cover_urls(row)
        row = await self._ensure_durations(row)
        row = await self._ensure_stream_ready(row)
        self._schedule_ingest_if_unready(row)
        return await self._task_payload(row, user_id)

    async def update_generation_title(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        title: str,
        variant: str | None = None,
    ) -> dict[str, Any]:
        cleaned = " ".join(str(title or "").split()).strip()
        if not cleaned:
            raise ValidationError("Title is required.", details={"field": "title"})
        if len(cleaned) > 200:
            cleaned = cleaned[:200]
        variant_key = str(variant or "").strip().lower()
        if variant_key in ("ok", "alt"):
            column = "title_ok" if variant_key == "ok" else "title_alt"
            updated = await self._pool.fetchrow(
                f"""
                UPDATE suno_tasks
                SET {column} = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND source = $4
                RETURNING id
                """,
                cleaned,
                task_id,
                user_id,
                SUNO_TASK_SOURCE_WEB_MUSIC,
            )
        else:
            updated = await self._pool.fetchrow(
                """
                UPDATE suno_tasks
                SET title = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND source = $4
                RETURNING id
                """,
                cleaned,
                task_id,
                user_id,
                SUNO_TASK_SOURCE_WEB_MUSIC,
            )
        if updated is None:
            raise NotFoundError("Generation not found.")
        return await self.get_generation(user_id, task_id)

    async def _poll_suno_task_status(self, external_task_id: str):
        """Poll record-info across the pool's keys.

        record-info is scoped to the account that created the task, so with a
        multi-account pool a single round-robin key gets 403 for tasks it does
        not own. `poll_suno_generate_with_pool` iterates every active key until
        the owner answers, without disabling the non-owner keys.
        """
        from platform_api.services.suno_audio_resolver import poll_suno_generate_with_pool

        return await poll_suno_generate_with_pool(self._pool, external_task_id)

    async def _refresh_pending_from_suno(self, row: Any) -> Any:
        """If the callback has not landed yet, poll the provider's record-info."""
        status = str(_row_value(row, "status") or "").strip().lower()
        if status not in {"pending", "running"}:
            return row
        external_id = str(_row_value(row, "external_task_id") or "").strip()
        if not external_id:
            return row
        try:
            polled = await self._poll_suno_task_status(external_id)
        except Exception as exc:
            logger.warning("Web music Suno poll failed for %s: %s", row["id"], exc)
            return row
        if polled.state == "success":
            urls = urls_from_generate_poll(polled)
            await self._pool.execute(
                """
                UPDATE suno_tasks
                SET status = $2,
                    audio_url_ok = COALESCE(NULLIF(BTRIM($3), ''), audio_url_ok),
                    audio_url_alt = COALESCE(NULLIF(BTRIM($4), ''), audio_url_alt),
                    audio_id_ok = COALESCE(NULLIF(BTRIM($5), ''), audio_id_ok),
                    audio_id_alt = COALESCE(NULLIF(BTRIM($6), ''), audio_id_alt),
                    image_url_ok = COALESCE(NULLIF(BTRIM($7), ''), image_url_ok),
                    image_url_alt = COALESCE(NULLIF(BTRIM($8), ''), image_url_alt),
                    duration_ok = COALESCE($9::double precision, duration_ok),
                    duration_alt = COALESCE($10::double precision, duration_alt),
                    updated_at = NOW()
                WHERE id = $1
                """,
                row["id"],
                TaskStatus.SUCCESS.value,
                urls.audio_url_ok,
                urls.audio_url_alt,
                urls.audio_id_ok,
                urls.audio_id_alt,
                urls.image_url_ok,
                urls.image_url_alt,
                urls.duration_ok,
                urls.duration_alt,
            )
            try:
                self._upload_service.schedule_web_music_b2_backfill(
                    suno_task_id=UUID(str(row["id"])),
                )
            except Exception as exc:
                logger.warning(
                    "Web music B2 pre-upload schedule failed task=%s: %s",
                    row["id"],
                    exc,
                )
        elif polled.state == "failed":
            await self._pool.execute(
                """
                UPDATE suno_tasks
                SET status = $2,
                    error_message = COALESCE(NULLIF(BTRIM($3), ''), error_message),
                    updated_at = NOW()
                WHERE id = $1
                """,
                row["id"],
                TaskStatus.FAILED.value,
                polled.error or "Suno generation failed.",
            )
        else:
            return row
        refreshed = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id, negative_tags, vocal_gender, style_weight,
                   weirdness_constraint, audio_weight, image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt, duration_ok, duration_alt,
                   audio_id_ok, audio_id_alt, title_ok, title_alt, stream_ready_ok, stream_ready_alt,
                   encrypted_original_key_ok, encrypted_original_key_alt,
                   package_status_ok, package_status_alt,
                   content_key_id_ok, content_key_id_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1
            """,
            row["id"],
        )
        return refreshed or row

    async def _ensure_cover_urls(self, row: Any) -> Any:
        """Backfill Suno cover art when audio is ready but image URLs were not stored yet."""
        status = str(_row_value(row, "status") or "").strip().lower()
        if status != "success":
            return row
        if str(_row_value(row, "image_url_ok") or "").strip() or str(_row_value(row, "image_url_alt") or "").strip():
            return row
        external_id = str(_row_value(row, "external_task_id") or "").strip()
        if not external_id:
            return row
        try:
            polled = await self._poll_suno_task_status(external_id)
        except Exception as exc:
            logger.warning("Web music Suno cover poll failed for %s: %s", row["id"], exc)
            return row
        if polled.state != "success":
            return row
        urls = urls_from_generate_poll(polled)
        if not urls.image_url_ok and not urls.image_url_alt:
            return row
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET image_url_ok = COALESCE(NULLIF(BTRIM($2), ''), image_url_ok),
                image_url_alt = COALESCE(NULLIF(BTRIM($3), ''), image_url_alt),
                updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
            urls.image_url_ok,
            urls.image_url_alt,
        )
        refreshed = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id, negative_tags, vocal_gender, style_weight,
                   weirdness_constraint, audio_weight, image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt, duration_ok, duration_alt,
                   audio_id_ok, audio_id_alt, title_ok, title_alt, stream_ready_ok, stream_ready_alt,
                   encrypted_original_key_ok, encrypted_original_key_alt,
                   package_status_ok, package_status_alt,
                   content_key_id_ok, content_key_id_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1
            """,
            row["id"],
        )
        return refreshed or row

    async def _ensure_durations(self, row: Any) -> Any:
        """Backfill Suno clip durations so the Create list does not wait on audio metadata."""
        status = str(_row_value(row, "status") or "").strip().lower()
        if status != "success":
            return row
        ok_ready = bool(_row_value(row, "audio_url_ok") or _row_value(row, "b2_storage_key_ok"))
        alt_ready = bool(_row_value(row, "audio_url_alt") or _row_value(row, "b2_storage_key_alt"))
        need_ok = ok_ready and _row_value(row, "duration_ok") is None
        need_alt = alt_ready and _row_value(row, "duration_alt") is None
        if not need_ok and not need_alt:
            return row
        external_id = str(_row_value(row, "external_task_id") or "").strip()
        if not external_id:
            return row
        try:
            polled = await self._poll_suno_task_status(external_id)
        except Exception as exc:
            logger.warning("Web music duration poll failed for %s: %s", row["id"], exc)
            return row
        if polled.state != "success":
            return row
        urls = urls_from_generate_poll(polled)
        if urls.duration_ok is None and urls.duration_alt is None:
            return row
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET duration_ok = COALESCE($2::double precision, duration_ok),
                duration_alt = COALESCE($3::double precision, duration_alt),
                updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
            urls.duration_ok,
            urls.duration_alt,
        )
        refreshed = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id, negative_tags, vocal_gender, style_weight,
                   weirdness_constraint, audio_weight, image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt, duration_ok, duration_alt,
                   audio_id_ok, audio_id_alt, title_ok, title_alt, stream_ready_ok, stream_ready_alt,
                   encrypted_original_key_ok, encrypted_original_key_alt,
                   package_status_ok, package_status_alt,
                   content_key_id_ok, content_key_id_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1
            """,
            row["id"],
        )
        return refreshed or row

    async def _ensure_stream_ready(self, row: Any) -> Any:
        """Mark a clip Ready only when our B2 object exists (plaintext leftover or packaged)."""
        status = str(_row_value(row, "status") or "").strip().lower()
        if status != "success":
            return row
        try:
            task_id = row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"]))
        except (KeyError, TypeError, ValueError):
            return row

        variants = (
            ("ok", "stream_ready_ok", "b2_storage_key_ok", "package_status_ok", "packaged_storage_key_ok"),
            ("alt", "stream_ready_alt", "b2_storage_key_alt", "package_status_alt", "packaged_storage_key_alt"),
        )
        marks: dict[str, bool] = {}
        for _variant, ready_col, b2_col, pkg_col, packaged_col in variants:
            if bool(_row_value(row, ready_col)):
                continue
            if str(_row_value(row, pkg_col) or "") == "ready" or _row_value(row, packaged_col):
                marks[ready_col] = True
                continue
            if _usable_web_music_b2_key(_row_value(row, b2_col), task_id):
                marks[ready_col] = True
        if not marks:
            return row
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET stream_ready_ok = COALESCE($2, stream_ready_ok),
                stream_ready_alt = COALESCE($3, stream_ready_alt),
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            True if marks.get("stream_ready_ok") else None,
            True if marks.get("stream_ready_alt") else None,
        )
        refreshed = await self._pool.fetchrow(
            """
            SELECT id, title, lyrics, style, model, instrumental, status,
                   audio_url_ok, audio_url_alt, error_message, created_at, updated_at,
                   external_task_id, negative_tags, vocal_gender, style_weight,
                   weirdness_constraint, audio_weight, image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt, duration_ok, duration_alt,
                   audio_id_ok, audio_id_alt, title_ok, title_alt, stream_ready_ok, stream_ready_alt,
                   encrypted_original_key_ok, encrypted_original_key_alt,
                   package_status_ok, package_status_alt,
                   content_key_id_ok, content_key_id_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1
            """,
            row["id"],
        )
        return refreshed or row

    async def _mint_owner_play_url(self, user_id: UUID, task_id: UUID, variant: str) -> str:
        del user_id
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in {"ok", "alt"}:
            variant_key = "ok"
        # Variant is in the path so the browser cannot reuse one media cache
        # entry across Version 1 / Version 2 (`?variant=` is not enough).
        return self._safe_client_play_url(
            canonical_api_path(f"web-music/generations/{task_id}/stream/{variant_key}")
        )

    async def _mint_public_play_url(self, task_id: UUID, variant: str) -> str:
        variant_key = str(variant or "ok").strip().lower()
        if self._redis is None:
            return self._safe_client_play_url(
                canonical_api_path(f"web-music/generations/{task_id}/stream/{variant_key}")
            )
        token = await create_play_token(
            self._redis,
            task_id=task_id,
            variant=variant_key,
            access="public",
        )
        return self._safe_client_play_url(play_url_for_token(token))

    @staticmethod
    def _safe_client_play_url(url: str) -> str:
        text = str(url or "").strip()
        return text if is_camxora_audio_proxy_url(text) else ""

    async def proxy_playback(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
        range_header: str | None,
    ) -> Response:
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        row = await self._fetch_playable_task_row(user_id, task_id, variant_key)
        return await self._proxy_row(
            row,
            task_id=task_id,
            variant_key=variant_key,
            range_header=range_header,
        )

    async def proxy_playback_from_token(
        self,
        token: str,
        *,
        session_user_id: str | None = None,
        range_header: str | None = None,
    ) -> Response:
        if not session_user_id:
            raise ForbiddenError("Sign in to play music.")
        if self._redis is None:
            raise ValidationError("Playback tokens are not available.")
        resolved = await resolve_play_token(self._redis, token)
        if resolved is None:
            raise NotFoundError("Play link expired or invalid.")
        task_id = UUID(resolved["task_id"])
        variant_key = resolved["variant"]
        access = resolved["access"]
        if access == "owner":
            owner_id = resolved.get("user_id")
            if not session_user_id or not owner_id or session_user_id != owner_id:
                raise ForbiddenError("This play link is not valid for your session.")
        row = await self._fetch_playable_task_row(UUID(session_user_id), task_id, variant_key)
        return await self._proxy_row(
            row,
            task_id=task_id,
            variant_key=variant_key,
            range_header=range_header,
        )

    async def _proxy_row(
        self,
        row: Any,
        *,
        task_id: UUID,
        variant_key: str,
        range_header: str | None,
    ) -> Response:
        pkg = str(
            _row_value(
                row,
                "package_status_ok" if variant_key == "ok" else "package_status_alt",
            )
            or ""
        )
        if pkg == "ready":
            raise ValidationError(
                "This track requires the encrypted player.",
                details={"code": "encrypted_playback_required"},
            )
        origin = await self._origin_playback_url(row, task_id=task_id, variant_key=variant_key)
        if origin is None:
            data, _filename, content_type = await self._serve_mp3_row(
                row, task_id=task_id, variant_key=variant_key
            )
            return bounded_mp3_response(data, range_header, media_type=content_type)
        url, source = origin
        if is_initial_play_range(range_header):
            await self._increment_play_count(task_id, variant_key)
            if source == "suno":
                self._schedule_b2_backfill(task_id, variant_key)
        return await proxy_origin_audio(url, range_header=range_header)

    async def _origin_playback_url(
        self,
        row: Any,
        *,
        task_id: UUID,
        variant_key: str,
    ) -> tuple[str, Literal["b2", "suno"]] | None:
        """Server-side origin only. Never return this URL to the browser."""
        status = str(row["status"] or "").upper()
        if status != "SUCCESS":
            return None

        b2_key = _usable_web_music_b2_key(
            row["b2_storage_key_ok"] if variant_key == "ok" else row["b2_storage_key_alt"],
            task_id,
        )
        if b2_key:
            try:
                from platform_api.services.streaming_config_service import resolve_streaming_storage_config
                from platform_api.services.storage_service import StorageService

                config = await resolve_streaming_storage_config(self._pool)
                if config.configured:
                    storage = StorageService.from_config(config)
                    url = await storage.get_signed_get_url(str(b2_key))
                    if url:
                        return str(url), "b2"
            except Exception as exc:
                logger.warning(
                    "Signed B2 play URL failed task=%s variant=%s: %s",
                    task_id,
                    variant_key,
                    exc,
                )
        return None

    def _schedule_ingest_if_unready(self, row: Any) -> None:
        """Retry B2 ingest when SUCCESS already landed but Create is still Finishing."""
        status = str(_row_value(row, "status") or "").strip().lower()
        if status != "success":
            return
        try:
            task_id = row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"]))
        except (KeyError, TypeError, ValueError):
            return
        for variant in ("ok", "alt"):
            if _clip_is_playable(row, variant=variant, task_id=task_id):
                continue
            url_col = "audio_url_ok" if variant == "ok" else "audio_url_alt"
            if not str(_row_value(row, url_col) or "").strip():
                continue
            self._schedule_b2_backfill(task_id, variant)

    def _schedule_b2_backfill(self, task_id: UUID, variant: str) -> None:
        try:
            self._upload_service.schedule_web_music_b2_backfill(
                suno_task_id=task_id,
                variant=variant,
            )
        except Exception as exc:
            logger.warning("B2 backfill schedule failed task=%s variant=%s: %s", task_id, variant, exc)

    def _schedule_lrc_b2_upload(self, task_id: UUID, variant: str, lrc_text: str | None = None) -> None:
        try:
            self._upload_service.schedule_web_music_lrc_upload(
                suno_task_id=task_id,
                variant=variant,
                lrc_text=lrc_text,
            )
        except Exception as exc:
            logger.warning("LRC B2 upload schedule failed task=%s variant=%s: %s", task_id, variant, exc)

    async def _fetch_playable_task_row(
        self,
        user_id: UUID | None,
        task_id: UUID,
        variant_key: str,
    ) -> Any:
        if user_id is not None:
            row = await self._pool.fetchrow(
                """
                SELECT id, title, status, audio_url_ok, audio_url_alt, external_task_id,
                       b2_storage_key_ok, b2_storage_key_alt,
                       encrypted_original_key_ok, encrypted_original_key_alt,
                       package_status_ok, package_status_alt,
                       content_key_id_ok, content_key_id_alt,
                       packaged_storage_key_ok, packaged_storage_key_alt
                FROM suno_tasks
                WHERE id = $1 AND user_id = $2 AND source = $3
                """,
                task_id,
                user_id,
                SUNO_TASK_SOURCE_WEB_MUSIC,
            )
            if row is not None:
                return row
        row = await self._pool.fetchrow(
            """
            SELECT t.id, t.title, t.status, t.audio_url_ok, t.audio_url_alt, t.external_task_id,
                   t.b2_storage_key_ok, t.b2_storage_key_alt,
                   t.encrypted_original_key_ok, t.encrypted_original_key_alt,
                   t.package_status_ok, t.package_status_alt,
                   t.content_key_id_ok, t.content_key_id_alt,
                   t.packaged_storage_key_ok, t.packaged_storage_key_alt
            FROM suno_tasks t
            JOIN web_music_playlist_items i
              ON i.suno_task_id = t.id AND i.variant = $3
            JOIN web_music_playlists p
              ON p.id = i.playlist_id AND p.is_public = TRUE
            WHERE t.id = $1 AND t.source = $2
            LIMIT 1
            """,
            task_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
            variant_key,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        return row

    async def _serve_mp3_row(
        self,
        row: Any,
        *,
        task_id: UUID,
        variant_key: str,
        allow_suno_ingest: bool = False,
    ) -> tuple[bytes, str, str]:
        status = str(row["status"] or "").upper()
        if status != "SUCCESS":
            raise ValidationError(
                "This song is not ready to download yet.",
                details={"status": status},
            )

        title = str(row["title"] or "camxora-track").strip() or "camxora-track"
        filename = f"{title}-{variant_key}.mp3"
        plaintext = await self._load_plaintext_mp3_row(
            row,
            task_id=task_id,
            variant_key=variant_key,
            allow_suno_ingest=allow_suno_ingest,
        )
        return plaintext, filename, "audio/mpeg"

    async def _maybe_decrypt_suno_export(
        self,
        data: bytes,
        *,
        task_id: UUID,
        variant_key: str,
    ) -> bytes:
        from platform_api.services.audio_package_service import AudioPackageService
        from platform_api.services.audio_packager import looks_like_camxora_audio

        if not data or not looks_like_camxora_audio(data):
            return data
        return await AudioPackageService(self._pool).decrypt_suno_export(
            data,
            subject_id=task_id,
            variant=variant_key,
        )

    async def _load_plaintext_mp3_row(
        self,
        row: Any,
        *,
        task_id: UUID,
        variant_key: str,
        allow_suno_ingest: bool,
    ) -> bytes:
        from platform_api.services.audio_package_service import AudioPackageService
        from platform_api.services.audio_packager import looks_like_camxora_audio
        from platform_api.services.streaming_config_service import resolve_streaming_storage_config
        from platform_api.services.storage_service import StorageService

        enc_key = _row_value(
            row,
            "encrypted_original_key_ok" if variant_key == "ok" else "encrypted_original_key_alt",
        )
        key_id = _row_value(
            row,
            "content_key_id_ok" if variant_key == "ok" else "content_key_id_alt",
        )
        if enc_key and key_id:
            try:
                config = await resolve_streaming_storage_config(self._pool)
                if config.configured:
                    wrapped = await self._pool.fetchval(
                        "SELECT wrapped_key FROM content_keys WHERE id = $1 AND status = 'active'",
                        key_id,
                    )
                    if wrapped:
                        storage = StorageService.from_config(config)
                        return await AudioPackageService(self._pool).decrypt_stored_original(
                            storage, str(enc_key), wrapped
                        )
            except Exception as exc:
                logger.warning(
                    "Encrypted original decrypt failed task=%s variant=%s: %s",
                    task_id,
                    variant_key,
                    exc,
                )

        b2_key = _usable_web_music_b2_key(
            row["b2_storage_key_ok"] if variant_key == "ok" else row["b2_storage_key_alt"],
            task_id,
        )
        if b2_key:
            try:
                data = await self._download_from_backblaze(b2_key)
                if looks_like_camxora_audio(data):
                    try:
                        data = await self._maybe_decrypt_suno_export(
                            data,
                            task_id=task_id,
                            variant_key=variant_key,
                        )
                    except Exception as exc:
                        logger.warning(
                            "B2 ciphertext decrypt failed task=%s variant=%s: %s",
                            task_id,
                            variant_key,
                            exc,
                        )
                        data = b""
                if not data:
                    pass
                elif not validate_mp3_bytes(data):
                    logger.warning(
                        "B2 object failed MP3 validation task=%s variant=%s key=%s",
                        task_id,
                        variant_key,
                        b2_key,
                    )
                    self._schedule_b2_backfill(task_id, variant_key)
                else:
                    return data
            except Exception as exc:
                logger.warning(
                    "B2 download failed for task=%s variant=%s: %s",
                    task_id,
                    variant_key,
                    exc,
                )

        if not allow_suno_ingest:
            raise NotFoundError("Audio file is not available yet. Please try again in a moment.")

        self._schedule_b2_backfill(task_id, variant_key)
        external_task_id = str(row["external_task_id"] or "").strip()
        last_error: Exception | None = None
        for attempt in range(1, 6):
            refreshed = None
            if external_task_id:
                try:
                    refreshed = await refresh_suno_task_download_urls(
                        external_task_id,
                        poll_status=self._poll_suno_task_status,
                    )
                except Exception as exc:
                    logger.warning("Web music URL refresh failed for %s: %s", task_id, exc)
            candidates = variant_url_candidates(
                variant=variant_key,
                stored_ok=str(row["audio_url_ok"] or ""),
                stored_alt=str(row["audio_url_alt"] or ""),
                refreshed=refreshed,
                include_other_variant=False,
            )
            if candidates:
                try:
                    return await download_suno_mp3_bytes(candidates[0], fallback_urls=candidates[1:])
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Web music MP3 download CDN retry %s/5 task=%s variant=%s: %s",
                        attempt,
                        task_id,
                        variant_key,
                        exc,
                    )
            if attempt < 5:
                await asyncio.sleep(2.0)
        del last_error
        raise NotFoundError("Audio file is not available yet. Please try again in a moment.")

    async def _watermark_owner_export(
        self,
        data: bytes,
        *,
        user_id: UUID,
        task_id: UUID,
        variant: str,
        format: str,
        actor: str = "owner",
    ) -> bytes:
        from platform_api.config import get_settings
        from platform_api.services.content_license_service import ContentLicenseService
        from platform_api.services.forensic_watermark import watermark_audio_bytes

        licenses = ContentLicenseService(self._pool, redis=self._redis)
        export_id = await licenses.record_export_event(
            user_id=user_id,
            suno_task_id=task_id,
            variant=variant,
            format=format,
            actor=actor,
        )
        settings = get_settings()
        secret = (settings.content_audio_kek or settings.encryption_master_key or "camxora-watermark")
        marked, payload_hash = watermark_audio_bytes(
            data,
            user_id=user_id,
            export_id=export_id or uuid4(),
            secret=secret,
        )
        if export_id is not None:
            try:
                wm_id = await self._pool.fetchval(
                    """
                    INSERT INTO audio_watermarks (export_event_id, user_id, payload_hash, method)
                    VALUES ($1, $2, $3, 'forensic_v1')
                    RETURNING id
                    """,
                    export_id,
                    user_id,
                    payload_hash,
                )
                await self._pool.execute(
                    "UPDATE export_events SET watermark_id = $2 WHERE id = $1",
                    export_id,
                    wm_id,
                )
            except Exception as exc:
                logger.warning("audio_watermarks insert failed: %s", exc)
        return marked

    async def stream_by_play_token(
        self,
        token: str,
        *,
        session_user_id: str | None = None,
    ) -> tuple[bytes, str, str]:
        if not session_user_id:
            raise ForbiddenError("Sign in to play music.")
        if self._redis is None:
            raise ValidationError("Playback tokens are not available.")
        resolved = await resolve_play_token(self._redis, token)
        if resolved is None:
            raise NotFoundError("Play link expired or invalid.")
        task_id = UUID(resolved["task_id"])
        variant_key = resolved["variant"]
        access = resolved["access"]
        if access == "owner":
            owner_id = resolved.get("user_id")
            if not session_user_id or not owner_id or session_user_id != owner_id:
                raise ForbiddenError("This play link is not valid for your session.")
            row = await self._fetch_playable_task_row(UUID(session_user_id), task_id, variant_key)
        else:
            row = await self._fetch_playable_task_row(
                UUID(session_user_id),
                task_id,
                variant_key,
            )
        pkg = str(
            _row_value(row, "package_status_ok" if variant_key == "ok" else "package_status_alt")
            or ""
        )
        if pkg == "ready":
            raise ValidationError(
                "This track requires the encrypted player.",
                details={"code": "encrypted_playback_required"},
            )
        return await self._serve_mp3_row(row, task_id=task_id, variant_key=variant_key)

    async def download_mp3(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
        require_subscription: bool = True,
    ) -> tuple[bytes, str, str]:
        if require_subscription:
            await self._require_download_access(user_id)
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        row = await self._fetch_playable_task_row(user_id, task_id, variant_key)
        data, filename, content_type = await self._serve_mp3_row(
            row,
            task_id=task_id,
            variant_key=variant_key,
            allow_suno_ingest=True,
        )
        from platform_api.services.mp3_duration_header import ensure_mp3_duration_header_async

        data = await ensure_mp3_duration_header_async(data)
        marked = await self._watermark_owner_export(
            data,
            user_id=user_id,
            task_id=task_id,
            variant=variant_key,
            format="mp3",
        )
        return marked, filename, content_type

    async def download_wav(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
    ) -> tuple[bytes, str, str]:
        try:
            data, filename, content_type = await self._download_wav_inner(user_id, task_id, variant=variant)
            variant_key = str(variant or "ok").strip().lower()
            marked = await self._watermark_owner_export(
                data,
                user_id=user_id,
                task_id=task_id,
                variant=variant_key if variant_key in {"ok", "alt"} else "ok",
                format="wav",
            )
            return marked, filename, content_type
        except ExternalServiceError as exc:
            logger.warning(
                "Web music WAV upstream error task=%s variant=%s: %s",
                task_id,
                variant,
                exc,
            )
            raise ValidationError(
                f"{exc.message} Please try again in a few moments."
                if "try again" not in str(exc.message or "").lower()
                else str(exc.message),
            ) from exc
        except PlatformAPIError:
            raise
        except StorageServiceError as exc:
            logger.warning(
                "Web music WAV storage error task=%s variant=%s: %s",
                task_id,
                variant,
                exc,
            )
            raise ValidationError(
                "WAV file is not ready yet. Please try again in a few moments.",
            ) from exc
        except Exception as exc:
            logger.exception(
                "Web music WAV download failed task=%s variant=%s",
                task_id,
                variant,
            )
            raise ValidationError(
                "WAV conversion failed. Please try again in a few moments.",
            ) from exc

    async def _download_wav_inner(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
    ) -> tuple[bytes, str, str]:
        await self._require_download_access(user_id)
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        
        wav_task_id_col = "wav_task_id_ok" if variant_key == "ok" else "wav_task_id_alt"
        wav_url_col = "wav_url_ok" if variant_key == "ok" else "wav_url_alt"
        wav_status_col = "wav_status_ok" if variant_key == "ok" else "wav_status_alt"
        b2_wav_key_col = "b2_wav_storage_key_ok" if variant_key == "ok" else "b2_wav_storage_key_alt"
        audio_id_col = f"audio_id_{variant_key}"

        row = await self._pool.fetchrow(
            f"""
            SELECT id, title, status, audio_url_ok, audio_url_alt, external_task_id,
                   {wav_task_id_col} as wav_task_id,
                   {wav_url_col} as wav_url,
                   {wav_status_col} as wav_status,
                   {b2_wav_key_col} as b2_wav_key,
                   {audio_id_col} as audio_id
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        
        status = str(_row_value(row, "status") or "").upper()
        if status != "SUCCESS":
            raise ValidationError(
                "This song is not ready for WAV download yet.",
                details={"status": status},
            )

        # Check if WAV is available in Backblaze
        b2_wav_key = _usable_web_music_b2_key(_row_value(row, "b2_wav_key"), task_id)
        if b2_wav_key:
            try:
                data = await self._download_from_backblaze(b2_wav_key)
                try:
                    data = await self._maybe_decrypt_suno_export(
                        data,
                        task_id=task_id,
                        variant_key=variant_key,
                    )
                except Exception as exc:
                    logger.warning(
                        "B2 WAV decrypt failed task=%s variant=%s: %s",
                        task_id,
                        variant_key,
                        exc,
                    )
                    data = b""
                if data and validate_wav_bytes(data):
                    title = str(row["title"] or "camxora-track").strip() or "camxora-track"
                    filename = f"{title}-{variant_key}.wav"
                    return data, filename, "audio/wav"
                logger.warning(
                    "B2 WAV failed validation task=%s variant=%s key=%s",
                    task_id,
                    variant_key,
                    b2_wav_key,
                )
            except Exception as exc:
                logger.warning("B2 WAV download failed for task=%s variant=%s, falling back to Suno: %s", 
                             task_id, variant_key, exc)
        
        external_task_id = str(_row_value(row, "external_task_id") or "").strip()
        if not external_task_id:
            raise ValidationError("Cannot convert to WAV: missing external task ID.")

        wav_task_id = str(_row_value(row, "wav_task_id") or "").strip()
        wav_url = str(_row_value(row, "wav_url") or "").strip()
        wav_status = str(_row_value(row, "wav_status") or "pending").strip().lower()
        if wav_status == "failed":
            logger.info(
                "Retrying web music WAV conversion task=%s variant=%s existing_task=%s",
                task_id,
                variant_key,
                wav_task_id or "-",
            )
            wav_status = "pending"
            # Keep wav_task_id so we re-poll instead of submitting a duplicate job.

        if not wav_task_id:
            audio_id = str(_row_value(row, "audio_id") or "").strip()
            for attempt in range(1, 6):
                if audio_id:
                    break
                refreshed = None
                try:
                    refreshed = await refresh_suno_task_download_urls(
                        external_task_id,
                        poll_status=self._poll_suno_task_status,
                    )
                except Exception as exc:
                    logger.warning(
                        "Web music WAV URL refresh failed for %s attempt=%s/5: %s",
                        task_id,
                        attempt,
                        exc,
                    )
                if refreshed:
                    audio_id = (
                        refreshed.audio_id_ok if variant_key == "ok" else refreshed.audio_id_alt
                    )
                if audio_id:
                    break
                logger.info(
                    "Waiting for this clip audio id for WAV task=%s variant=%s attempt=%s/5",
                    task_id,
                    variant_key,
                    attempt,
                )
                if attempt < 5:
                    await asyncio.sleep(2.0)

            if not audio_id:
                raise ValidationError(
                    "WAV file is not ready yet. Please try again in a few moments."
                )
            
            from platform_api.clients.suno_client import extract_suno_wav_task_id
            from platform_api.services.suno_audio_resolver import (
                call_with_owning_suno_key,
            )

            # WAV conversion is account-scoped: pick the key that owns the task.
            wav_response, _ = await call_with_owning_suno_key(
                self._pool,
                lambda api_key, ext=external_task_id, aid=audio_id: self._generation._suno_client.submit_wav_task(
                    task_id=ext,
                    audio_id=aid,
                    api_key=api_key,
                ),
            )
            wav_task_id = extract_suno_wav_task_id(wav_response)
            
            await self._pool.execute(
                f"""
                UPDATE suno_tasks
                SET {wav_task_id_col} = $1, {wav_status_col} = 'pending'
                WHERE id = $2
                """,
                wav_task_id,
                task_id,
            )
            wav_status = "pending"
        
        if wav_task_id and (wav_status != "success" or not wav_url):
            from platform_api.clients.suno_client import parse_suno_wav_poll
            
            max_attempts = 30
            for attempt in range(max_attempts):
                poll_id = wav_task_id
                poll_response, _ = await call_with_owning_suno_key(
                    self._pool,
                    lambda api_key, tid=poll_id: self._generation._suno_client.poll_wav_status(
                        wav_task_id=tid,
                        api_key=api_key,
                    ),
                )
                poll_status, poll_wav_url, poll_error = parse_suno_wav_poll(poll_response)
                
                if poll_status == "success" and poll_wav_url:
                    await self._pool.execute(
                        f"""
                        UPDATE suno_tasks
                        SET {wav_url_col} = $1, {wav_status_col} = 'success'
                        WHERE id = $2
                        """,
                        poll_wav_url,
                        task_id,
                    )
                    wav_url = poll_wav_url
                    wav_status = "success"
                    break
                elif poll_status == "failed":
                    await self._pool.execute(
                        f"""
                        UPDATE suno_tasks
                        SET {wav_status_col} = 'failed'
                        WHERE id = $1
                        """,
                        task_id,
                    )
                    raise ValidationError(
                        f"WAV conversion failed: {poll_error or 'Unknown error'}",
                        details={"wav_task_id": wav_task_id},
                    )
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2.0)
        
        if not wav_url:
            raise ValidationError(
                "WAV file is not ready yet. Please try again in a few moments.",
                details={"wav_status": wav_status},
            )
        
        last_error: Exception | None = None
        data: bytes | None = None
        for attempt in range(1, 6):
            try:
                data = await download_suno_wav_bytes(wav_url)
                if validate_wav_bytes(data):
                    break
                data = None
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Web music WAV download CDN retry %s/5 task=%s variant=%s: %s",
                    attempt,
                    task_id,
                    variant_key,
                    exc,
                )
            if attempt < 5:
                await asyncio.sleep(2.0)
        if data is None or not validate_wav_bytes(data):
            raise ValidationError(
                "WAV file is not ready yet. Please try again in a few moments.",
                details={"wav_status": wav_status},
            )
        title = str(row["title"] or "camxora-track").strip() or "camxora-track"
        filename = f"{title}-{variant_key}.wav"
        return data, filename, "audio/wav"

    async def download_timed_lyrics(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
        lyric_format: str = "lrc",
    ) -> tuple[bytes, str, str]:
        """Fetch Suno word alignments and return karaoke LRC or SRT text."""
        await self._require_download_access(user_id)
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        format_key = str(lyric_format or "lrc").strip().lower()
        if format_key not in ("lrc", "srt"):
            raise ValidationError("format must be lrc or srt.", details={"field": "format"})

        row = await self._pool.fetchrow(
            """
            SELECT id, title, status, instrumental, external_task_id,
                   audio_id_ok, audio_id_alt,
                   b2_lrc_storage_key_ok, b2_lrc_storage_key_alt
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        if bool(row["instrumental"]):
            raise ValidationError(
                "Timed lyrics are not available for instrumental tracks.",
                details={"instrumental": True},
            )
        status = str(row["status"] or "").upper()
        if status != "SUCCESS":
            raise ValidationError(
                "Timed lyrics are not ready yet.",
                details={"status": status},
            )

        b2_lrc_key = _usable_web_music_b2_key(
            row.get("b2_lrc_storage_key_ok")
            if variant_key == "ok"
            else row.get("b2_lrc_storage_key_alt"),
            task_id,
        )
        if b2_lrc_key:
            try:
                lrc_bytes = await self._download_from_backblaze(str(b2_lrc_key))
                lrc_bytes = await self._maybe_decrypt_suno_export(
                    lrc_bytes,
                    task_id=task_id,
                    variant_key=variant_key,
                )
                lrc_cached = lrc_bytes.decode("utf-8")
                if looks_like_lrc(lrc_cached):
                    title = str(row["title"] or "camxora-track").strip() or "camxora-track"
                    if format_key == "srt":
                        body = lrc_to_srt(lrc_cached)
                        if not body.strip():
                            raise ValidationError(
                                "Could not convert timed lyrics to SRT.",
                                details={"reason": "srt_conversion_failed"},
                            )
                        filename = f"{title}.srt"
                        content_type = "application/x-subrip; charset=utf-8"
                    else:
                        body = lrc_cached
                        filename = f"{title}.lrc"
                        content_type = "text/plain; charset=utf-8"
                    return await self._finish_lyrics_export(
                        body.encode("utf-8"),
                        filename,
                        content_type,
                        user_id=user_id,
                        task_id=task_id,
                        variant=variant_key,
                        format=format_key,
                    )
            except ValidationError:
                raise
            except Exception as exc:
                logger.warning(
                    "B2 LRC download failed for task=%s variant=%s, falling back to Suno: %s",
                    task_id,
                    variant_key,
                    exc,
                )

        external_task_id = str(row["external_task_id"] or "").strip()
        audio_id = str(row[f"audio_id_{variant_key}"] or "").strip()
        if external_task_id and not audio_id:
            try:
                polled = await self._poll_suno_task_status(external_task_id)
            except Exception as exc:
                logger.warning("Web music audio_id poll failed for %s: %s", task_id, exc)
                polled = None
            if polled and polled.state == "success":
                urls = urls_from_generate_poll(polled)
                audio_id = (
                    str(urls.audio_id_ok or "").strip()
                    if variant_key == "ok"
                    else str(urls.audio_id_alt or "").strip()
                )
                if urls.audio_id_ok or urls.audio_id_alt:
                    await self._pool.execute(
                        """
                        UPDATE suno_tasks
                        SET audio_id_ok = COALESCE(NULLIF(BTRIM($2), ''), audio_id_ok),
                            audio_id_alt = COALESCE(NULLIF(BTRIM($3), ''), audio_id_alt),
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        task_id,
                        urls.audio_id_ok,
                        urls.audio_id_alt,
                    )

        if not external_task_id or not audio_id:
            raise ValidationError(
                "Timed lyrics are not available for this track yet. Try again in a few minutes.",
                details={"missing": "audio_id"},
            )

        lrc = await fetch_timestamped_lrc_with_pool(
            self._pool,
            external_task_id=external_task_id,
            audio_id=audio_id,
        )
        if not looks_like_lrc(lrc):
            raise ValidationError(
                "Timed lyrics are not available yet. Suno may still be processing alignments — try again shortly.",
                details={"reason": "empty_lrc"},
            )

        self._schedule_lrc_b2_upload(task_id, variant_key, lrc)

        title = str(row["title"] or "camxora-track").strip() or "camxora-track"
        if format_key == "srt":
            body = lrc_to_srt(lrc)
            if not body.strip():
                raise ValidationError(
                    "Could not convert timed lyrics to SRT.",
                    details={"reason": "srt_conversion_failed"},
                )
            filename = f"{title}.srt"
            content_type = "application/x-subrip; charset=utf-8"
        else:
            body = lrc
            filename = f"{title}.lrc"
            content_type = "text/plain; charset=utf-8"
        return await self._finish_lyrics_export(
            body.encode("utf-8"),
            filename,
            content_type,
            user_id=user_id,
            task_id=task_id,
            variant=variant_key,
            format=format_key,
        )

    async def _finish_lyrics_export(
        self,
        data: bytes,
        filename: str,
        content_type: str,
        *,
        user_id: UUID,
        task_id: UUID,
        variant: str,
        format: str,
    ) -> tuple[bytes, str, str]:
        from platform_api.services.content_license_service import ContentLicenseService

        await ContentLicenseService(self._pool, redis=self._redis).record_export_event(
            user_id=user_id,
            suno_task_id=task_id,
            variant=variant,
            format=format,
            actor="owner",
        )
        return data, filename, content_type

    async def _task_payload(self, row: Any, user_id: UUID) -> dict[str, Any]:
        task_id = str(row["id"])
        created = row["created_at"]
        if isinstance(created, datetime) and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        title = row["title"] or "Untitled"
        title_ok = _clip_display_title(row, variant="ok", fallback=title)
        title_alt = _clip_display_title(row, variant="alt", fallback=title)
        image_ok = str(_row_value(row, "image_url_ok") or "").strip() or None
        image_alt = str(_row_value(row, "image_url_alt") or "").strip() or None
        ok_ready = _clip_is_playable(row, variant="ok", task_id=UUID(task_id))
        alt_ready = _clip_is_playable(row, variant="alt", task_id=UUID(task_id))
        return {
            "id": task_id,
            "title": title,
            "lyrics": row["lyrics"] or "",
            "style": row["style"] or "",
            "model": row["model"] or "V5",
            "instrumental": bool(row["instrumental"]),
            "status": str(row["status"] or "pending").upper(),
            "error_message": row["error_message"],
            "created_at": created,
            "negative_tags": _row_value(row, "negative_tags") or None,
            "vocal_gender": _row_value(row, "vocal_gender") or None,
            "style_weight": float(row["style_weight"]) if _row_value(row, "style_weight") is not None else None,
            "weirdness_constraint": float(row["weirdness_constraint"]) if _row_value(row, "weirdness_constraint") is not None else None,
            "audio_weight": float(row["audio_weight"]) if _row_value(row, "audio_weight") is not None else None,
            "clips": [
                {
                    "variant": "ok",
                    "title": title_ok,
                    "label": f"{title_ok} · Version 1",
                    "audio_url": await self._mint_owner_play_url(user_id, UUID(task_id), "ok") if ok_ready else "",
                    "download_url": f"{canonical_api_path(f'web-music/generations/{task_id}/download')}?variant=ok",
                    "ready": ok_ready,
                    "package_status": str(_row_value(row, "package_status_ok") or "none"),
                    "image_url": image_ok,
                    "duration_seconds": _duration_seconds(row, "duration_ok"),
                },
                {
                    "variant": "alt",
                    "title": title_alt,
                    "label": f"{title_alt} · Version 2",
                    "audio_url": await self._mint_owner_play_url(user_id, UUID(task_id), "alt") if alt_ready else "",
                    "download_url": f"{canonical_api_path(f'web-music/generations/{task_id}/download')}?variant=alt",
                    "ready": alt_ready,
                    "package_status": str(_row_value(row, "package_status_alt") or "none"),
                    "image_url": image_alt,
                    "duration_seconds": _duration_seconds(row, "duration_alt"),
                },
            ],
        }

    async def _download_from_backblaze(self, storage_key: str) -> bytes:
        """Download MP3 from Backblaze B2 storage."""
        from platform_api.services.streaming_config_service import resolve_streaming_storage_config
        from platform_api.services.storage_service import StorageService

        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            raise NotFoundError("Backblaze storage is not configured.")
        
        storage = StorageService.from_config(config)
        data = await storage.download_bytes(key=storage_key)
        if not data:
            raise NotFoundError(f"File not found in Backblaze: {storage_key}")
        return data

    # ─── Playlists ───────────────────────────────────────────────────────

    def _playlist_slug(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return (slug[:200] or "playlist")

    async def _unique_playlist_slug(self, user_id: UUID, name: str) -> str:
        base = self._playlist_slug(name)
        slug = base
        suffix = 2
        while True:
            existing = await self._pool.fetchrow(
                """
                SELECT 1 FROM web_music_playlists
                WHERE user_id = $1 AND slug = $2
                """,
                user_id,
                slug,
            )
            if existing is None:
                return slug
            slug = f"{base}-{suffix}"
            suffix += 1

    def _playlist_payload(self, row: Any, *, song_count: int = 0) -> dict[str, Any]:
        created = row["created_at"]
        updated = row["updated_at"]
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "description": row.get("description"),
            "is_public": bool(row["is_public"]),
            "song_count": song_count,
            "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
            "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else str(updated or ""),
        }

    async def list_playlists(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT p.*, COUNT(i.id)::int AS song_count
            FROM web_music_playlists p
            LEFT JOIN web_music_playlist_items i ON i.playlist_id = p.id
            WHERE p.user_id = $1
            GROUP BY p.id
            ORDER BY p.updated_at DESC, p.created_at DESC
            """,
            user_id,
        )
        return [self._playlist_payload(row, song_count=int(row["song_count"] or 0)) for row in rows]

    async def list_playlist_memberships(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT p.id AS playlist_id, p.name AS playlist_name, i.suno_task_id, i.variant
            FROM web_music_playlists p
            JOIN web_music_playlist_items i ON i.playlist_id = p.id
            WHERE p.user_id = $1
            ORDER BY p.updated_at DESC, i.position ASC, i.added_at ASC
            """,
            user_id,
        )
        return [
            {
                "playlist_id": str(row["playlist_id"]),
                "playlist_name": str(row["playlist_name"] or "Playlist"),
                "task_id": str(row["suno_task_id"]),
                "variant": str(row["variant"] or "ok"),
            }
            for row in rows
        ]

    async def create_playlist(
        self,
        user_id: UUID,
        *,
        name: str,
        description: str | None = None,
        is_public: bool = False,
    ) -> dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValidationError("Playlist name is required.", details={"field": "name"})
        slug = await self._unique_playlist_slug(user_id, clean_name)
        row = await self._pool.fetchrow(
            """
            INSERT INTO web_music_playlists (user_id, name, slug, description, is_public)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            user_id,
            clean_name[:200],
            slug,
            (description or "").strip() or None,
            is_public,
        )
        if row is None:
            raise ValidationError("Unable to create playlist.")
        return self._playlist_payload(row, song_count=0)

    async def get_playlist(
        self,
        user_id: UUID | None,
        playlist_id: UUID,
        *,
        allow_public: bool = False,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT p.*, COUNT(i.id)::int AS song_count
            FROM web_music_playlists p
            LEFT JOIN web_music_playlist_items i ON i.playlist_id = p.id
            WHERE p.id = $1
            GROUP BY p.id
            """,
            playlist_id,
        )
        if row is None:
            raise NotFoundError("Playlist not found.")
        owner_id = row["user_id"]
        is_owner = user_id is not None and owner_id == user_id
        if not is_owner and not (allow_public and bool(row["is_public"])):
            raise ForbiddenError("You do not have access to this playlist.")
        payload = self._playlist_payload(row, song_count=int(row["song_count"] or 0))
        payload["is_owner"] = is_owner
        return payload

    async def update_playlist(
        self,
        user_id: UUID,
        playlist_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
    ) -> dict[str, Any]:
        await self.get_playlist(user_id, playlist_id)
        fields: list[str] = []
        values: list[Any] = []
        idx = 1
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValidationError("Playlist name is required.", details={"field": "name"})
            fields.append(f"name = ${idx}")
            values.append(clean_name[:200])
            idx += 1
            fields.append(f"slug = ${idx}")
            values.append(await self._unique_playlist_slug(user_id, clean_name))
            idx += 1
        if description is not None:
            fields.append(f"description = ${idx}")
            values.append(description.strip() or None)
            idx += 1
        if is_public is not None:
            fields.append(f"is_public = ${idx}")
            values.append(is_public)
            idx += 1
        if not fields:
            return await self.get_playlist(user_id, playlist_id)
        fields.append("updated_at = NOW()")
        values.extend([playlist_id, user_id])
        row = await self._pool.fetchrow(
            f"""
            UPDATE web_music_playlists
            SET {", ".join(fields)}
            WHERE id = ${idx} AND user_id = ${idx + 1}
            RETURNING *
            """,
            *values,
        )
        if row is None:
            raise NotFoundError("Playlist not found.")
        return self._playlist_payload(row)

    async def delete_playlist(self, user_id: UUID, playlist_id: UUID) -> None:
        result = await self._pool.execute(
            """
            DELETE FROM web_music_playlists
            WHERE id = $1 AND user_id = $2
            """,
            playlist_id,
            user_id,
        )
        if result.endswith("0"):
            raise NotFoundError("Playlist not found.")

    async def list_playlist_items(
        self,
        user_id: UUID | None,
        playlist_id: UUID,
        *,
        allow_public: bool = False,
    ) -> list[dict[str, Any]]:
        await self.get_playlist(user_id, playlist_id, allow_public=allow_public)
        rows = await self._pool.fetch(
            """
            SELECT
                i.id,
                i.suno_task_id,
                i.variant,
                i.position,
                i.added_at,
                t.title,
                t.style,
                t.status,
                t.audio_url_ok,
                t.audio_url_alt,
                t.b2_storage_key_ok,
                t.b2_storage_key_alt,
                t.package_status_ok,
                t.package_status_alt,
                t.packaged_storage_key_ok,
                t.packaged_storage_key_alt,
                t.image_url_ok,
                t.image_url_alt
            FROM web_music_playlist_items i
            JOIN suno_tasks t ON t.id = i.suno_task_id
            WHERE i.playlist_id = $1
            ORDER BY i.position ASC, i.added_at ASC
            """,
            playlist_id,
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            variant = str(row["variant"] or "ok")
            task_id = str(row["suno_task_id"])
            ready = _clip_is_playable(row, variant=variant, task_id=UUID(task_id))
            pkg = str(
                _row_value(row, "package_status_ok" if variant == "ok" else "package_status_alt")
                or "none"
            )
            image_url = str(
                row["image_url_ok"] if variant == "ok" else row["image_url_alt"] or ""
            ).strip() or None
            added = row["added_at"]
            if user_id is not None:
                play_url = await self._mint_owner_play_url(user_id, UUID(task_id), variant) if ready else ""
            else:
                play_url = await self._mint_public_play_url(UUID(task_id), variant) if ready else ""
            items.append(
                {
                    "id": str(row["id"]),
                    "task_id": task_id,
                    "variant": variant,
                    "position": int(row["position"]),
                    "title": str(row["title"] or "Untitled"),
                    "style": str(row["style"] or ""),
                    "status": str(row["status"] or "PENDING").upper(),
                    "ready": ready,
                    "package_status": pkg,
                    "audio_url": play_url,
                    "image_url": image_url,
                    "added_at": added.isoformat() if hasattr(added, "isoformat") else str(added or ""),
                }
            )
        return items

    async def add_playlist_item(
        self,
        user_id: UUID,
        playlist_id: UUID,
        *,
        task_id: UUID,
        variant: str = "ok",
    ) -> dict[str, Any]:
        await self.get_playlist(user_id, playlist_id)
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        task = await self._pool.fetchrow(
            """
            SELECT id, title, style, status, audio_url_ok, audio_url_alt,
                   image_url_ok, image_url_alt,
                   b2_storage_key_ok, b2_storage_key_alt,
                   package_status_ok, package_status_alt,
                   packaged_storage_key_ok, packaged_storage_key_alt
            FROM suno_tasks
            WHERE id = $1 AND user_id = $2 AND source = $3
            """,
            task_id,
            user_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
        )
        if task is None:
            raise NotFoundError("Generation not found.")
        if str(task["status"] or "").upper() != "SUCCESS":
            raise ValidationError("Only completed songs can be added to a playlist.")
        ready = _clip_is_playable(task, variant=variant_key, task_id=task_id)
        if not ready:
            raise ValidationError("This song version is not ready yet.")

        next_position = await self._pool.fetchval(
            """
            SELECT COALESCE(MAX(position), 0) + 1
            FROM web_music_playlist_items
            WHERE playlist_id = $1
            """,
            playlist_id,
        )
        row = await self._pool.fetchrow(
            """
            INSERT INTO web_music_playlist_items (playlist_id, suno_task_id, variant, position)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (playlist_id, suno_task_id, variant) DO UPDATE
            SET position = EXCLUDED.position
            RETURNING id, suno_task_id, variant, position, added_at
            """,
            playlist_id,
            task_id,
            variant_key,
            int(next_position or 1),
        )
        await self._pool.execute(
            "UPDATE web_music_playlists SET updated_at = NOW() WHERE id = $1",
            playlist_id,
        )
        if row is None:
            raise ValidationError("Unable to add song to playlist.")
        added = row["added_at"]
        return {
            "id": str(row["id"]),
            "task_id": str(row["suno_task_id"]),
            "variant": str(row["variant"]),
            "position": int(row["position"]),
            "title": str(task["title"] or "Untitled"),
            "style": str(task["style"] or ""),
            "ready": ready,
            "package_status": str(
                _row_value(task, "package_status_ok" if variant_key == "ok" else "package_status_alt")
                or "none"
            ),
            "audio_url": await self._mint_owner_play_url(user_id, task_id, variant_key),
            "image_url": str(
                task["image_url_ok"] if variant_key == "ok" else task["image_url_alt"] or ""
            ).strip()
            or None,
            "added_at": added.isoformat() if hasattr(added, "isoformat") else str(added or ""),
        }

    async def remove_playlist_item(
        self,
        user_id: UUID,
        playlist_id: UUID,
        *,
        item_id: UUID,
    ) -> None:
        await self.get_playlist(user_id, playlist_id)
        result = await self._pool.execute(
            """
            DELETE FROM web_music_playlist_items i
            USING web_music_playlists p
            WHERE i.id = $1
              AND i.playlist_id = $2
              AND p.id = i.playlist_id
              AND p.user_id = $3
            """,
            item_id,
            playlist_id,
            user_id,
        )
        if result.endswith("0"):
            raise NotFoundError("Playlist item not found.")
        await self._pool.execute(
            "UPDATE web_music_playlists SET updated_at = NOW() WHERE id = $1",
            playlist_id,
        )

    def _public_creator_payload(self, row: Any) -> dict[str, Any]:
        user_id = str(row.get("user_id") or row.get("id"))
        avatar_raw = str(row.get("avatar_url") or row.get("creator_avatar_url") or "").strip()
        return {
            "user_id": user_id,
            "artist_name": str(row.get("artist_name") or row.get("creator_name") or row.get("display_name") or "Camxora Creator"),
            "avatar_url": canonical_api_path(f"media/users/{user_id}/avatar") if avatar_raw else None,
        }

    def _public_playlist_payload(self, row: Any) -> dict[str, Any]:
        updated = row["updated_at"]
        creator = self._public_creator_payload(row)
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "description": row.get("description"),
            "song_count": int(row["song_count"] or 0),
            "cover_url": str(row.get("cover_url") or "").strip() or None,
            "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else str(updated or ""),
            "creator_user_id": creator["user_id"],
            "creator_name": creator["artist_name"],
            "creator_avatar_url": creator["avatar_url"],
        }

    async def list_public_playlists(self, *, limit: int = 24, offset: int = 0) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT
                p.id,
                p.user_id,
                p.name,
                p.slug,
                p.description,
                p.updated_at,
                u.display_name AS creator_name,
                u.avatar_url AS creator_avatar_url,
                COUNT(i.id)::int AS song_count,
                cover.cover_url
            FROM web_music_playlists p
            JOIN users u ON u.id = p.user_id
            LEFT JOIN web_music_playlist_items i ON i.playlist_id = p.id
            LEFT JOIN LATERAL (
                SELECT CASE
                    WHEN i2.variant = 'ok' THEN NULLIF(t.image_url_ok, '')
                    ELSE COALESCE(NULLIF(t.image_url_alt, ''), NULLIF(t.image_url_ok, ''))
                END AS cover_url
                FROM web_music_playlist_items i2
                JOIN suno_tasks t ON t.id = i2.suno_task_id
                WHERE i2.playlist_id = p.id
                ORDER BY i2.position ASC, i2.added_at ASC
                LIMIT 1
            ) cover ON TRUE
            WHERE p.is_public = TRUE
            GROUP BY
                p.id,
                p.user_id,
                p.name,
                p.slug,
                p.description,
                p.updated_at,
                u.display_name,
                u.avatar_url,
                cover.cover_url
            ORDER BY p.updated_at DESC, p.created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM web_music_playlists WHERE is_public = TRUE"
        )
        return {
            "items": [self._public_playlist_payload(row) for row in rows],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }

    async def list_public_artists(self, *, limit: int = 48, offset: int = 0) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT
                u.id AS user_id,
                u.display_name AS artist_name,
                u.avatar_url,
                COUNT(DISTINCT p.id)::int AS playlist_count,
                COUNT(i.id)::int AS track_count
            FROM users u
            JOIN web_music_playlists p ON p.user_id = u.id AND p.is_public = TRUE
            LEFT JOIN web_music_playlist_items i ON i.playlist_id = p.id
            GROUP BY u.id, u.display_name, u.avatar_url
            HAVING COUNT(DISTINCT p.id) > 0
            ORDER BY track_count DESC, artist_name ASC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int FROM (
                SELECT u.id
                FROM users u
                JOIN web_music_playlists p ON p.user_id = u.id AND p.is_public = TRUE
                GROUP BY u.id
            ) public_creators
            """
        )
        items = []
        for row in rows:
            creator = self._public_creator_payload(row)
            items.append(
                {
                    "user_id": creator["user_id"],
                    "artist_name": creator["artist_name"],
                    "avatar_url": creator["avatar_url"],
                    "playlist_count": int(row["playlist_count"] or 0),
                    "track_count": int(row["track_count"] or 0),
                }
            )
        return {"items": items, "total": int(total or 0), "limit": limit, "offset": offset}

    async def get_public_artist(self, user_id: UUID) -> dict[str, Any] | None:
        user_row = await self._pool.fetchrow(
            """
            SELECT id, display_name, avatar_url
            FROM users
            WHERE id = $1
            """,
            user_id,
        )
        if user_row is None:
            return None

        playlist_rows = await self._pool.fetch(
            """
            SELECT
                p.id,
                p.user_id,
                p.name,
                p.slug,
                p.description,
                p.updated_at,
                u.display_name AS creator_name,
                u.avatar_url AS creator_avatar_url,
                COUNT(i.id)::int AS song_count,
                cover.cover_url
            FROM web_music_playlists p
            JOIN users u ON u.id = p.user_id
            LEFT JOIN web_music_playlist_items i ON i.playlist_id = p.id
            LEFT JOIN LATERAL (
                SELECT CASE
                    WHEN i2.variant = 'ok' THEN NULLIF(t.image_url_ok, '')
                    ELSE COALESCE(NULLIF(t.image_url_alt, ''), NULLIF(t.image_url_ok, ''))
                END AS cover_url
                FROM web_music_playlist_items i2
                JOIN suno_tasks t ON t.id = i2.suno_task_id
                WHERE i2.playlist_id = p.id
                ORDER BY i2.position ASC, i2.added_at ASC
                LIMIT 1
            ) cover ON TRUE
            WHERE p.user_id = $1 AND p.is_public = TRUE
            GROUP BY
                p.id,
                p.user_id,
                p.name,
                p.slug,
                p.description,
                p.updated_at,
                u.display_name,
                u.avatar_url,
                cover.cover_url
            ORDER BY p.updated_at DESC, p.created_at DESC
            """,
            user_id,
        )

        wm_stats = await self._pool.fetchrow(
            """
            SELECT
                COUNT(DISTINCT p.id)::int AS playlist_count,
                COUNT(i.id)::int AS track_count
            FROM web_music_playlists p
            LEFT JOIN web_music_playlist_items i ON i.playlist_id = p.id
            WHERE p.user_id = $1 AND p.is_public = TRUE
            """,
            user_id,
        )

        streaming_stats = await self._pool.fetchrow(
            """
            SELECT
                COUNT(DISTINCT a.id)::int AS album_count,
                COUNT(t.id)::int AS track_count
            FROM stream_albums a
            JOIN stream_tracks t
              ON t.album_id = a.id AND t.publish_status = 'published'
            WHERE a.user_id = $1 AND a.publish_status = 'published'
            """,
            user_id,
        )

        playlist_count = int(wm_stats["playlist_count"] or 0) if wm_stats else 0
        wm_track_count = int(wm_stats["track_count"] or 0) if wm_stats else 0
        album_count = int(streaming_stats["album_count"] or 0) if streaming_stats else 0
        stream_track_count = int(streaming_stats["track_count"] or 0) if streaming_stats else 0

        if playlist_count == 0 and album_count == 0:
            return None

        album_rows = await self._pool.fetch(
            """
            SELECT
                a.id,
                a.album_name,
                a.user_id,
                u.display_name AS artist_name,
                COUNT(t.id)::int AS track_count,
                COALESCE(SUM(t.play_count), 0)::bigint AS play_count
            FROM stream_albums a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN stream_tracks t
              ON t.album_id = a.id AND t.publish_status = 'published'
            WHERE a.user_id = $1 AND a.publish_status = 'published'
            GROUP BY a.id, a.album_name, a.user_id, u.display_name
            HAVING COUNT(t.id) > 0
            ORDER BY a.published_at DESC NULLS LAST, a.album_name ASC
            """,
            user_id,
        )

        profile_row = {
            "id": user_row["id"],
            "display_name": user_row["display_name"],
            "avatar_url": user_row["avatar_url"],
        }
        creator = self._public_creator_payload(profile_row)
        return {
            "user_id": creator["user_id"],
            "artist_name": creator["artist_name"],
            "avatar_url": creator["avatar_url"],
            "playlist_count": playlist_count,
            "album_count": album_count,
            "track_count": wm_track_count + stream_track_count,
            "playlists": [self._public_playlist_payload(row) for row in playlist_rows],
            "albums": [
                {
                    "id": str(row["id"]),
                    "album_name": str(row["album_name"]),
                    "artist_name": str(row["artist_name"] or creator["artist_name"]),
                    "user_id": str(row["user_id"]),
                    "track_count": int(row["track_count"] or 0),
                    "play_count": int(row["play_count"] or 0),
                    "cover_url": None,
                }
                for row in album_rows
            ],
        }

    async def list_public_recent_tracks(self, *, limit: int = 12, offset: int = 0) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT
                i.id AS item_id,
                i.suno_task_id,
                i.variant,
                i.added_at,
                t.title,
                t.style,
                t.user_id,
                u.display_name AS artist_name,
                p.name AS playlist_name,
                CASE
                    WHEN i.variant = 'ok' THEN NULLIF(t.image_url_ok, '')
                    ELSE COALESCE(NULLIF(t.image_url_alt, ''), NULLIF(t.image_url_ok, ''))
                END AS cover_url,
                COALESCE(pc.play_count, 0)::int AS play_count,
                CASE WHEN i.variant = 'ok' THEN t.package_status_ok ELSE t.package_status_alt END AS package_status
            FROM web_music_playlist_items i
            JOIN web_music_playlists p ON p.id = i.playlist_id AND p.is_public = TRUE
            JOIN suno_tasks t ON t.id = i.suno_task_id
            JOIN users u ON u.id = t.user_id
            LEFT JOIN web_music_play_counts pc
              ON pc.task_id = i.suno_task_id AND pc.variant = i.variant
            WHERE UPPER(t.status) = 'SUCCESS'
              AND (
                (i.variant = 'ok' AND (
                    COALESCE(t.package_status_ok, 'none') = 'ready'
                    OR COALESCE(t.b2_storage_key_ok, t.audio_url_ok) IS NOT NULL
                ))
                OR (i.variant = 'alt' AND (
                    COALESCE(t.package_status_alt, 'none') = 'ready'
                    OR COALESCE(t.b2_storage_key_alt, t.audio_url_alt) IS NOT NULL
                ))
              )
            ORDER BY i.added_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        total = await self._pool.fetchval(
            """
            SELECT COUNT(*)::int
            FROM web_music_playlist_items i
            JOIN web_music_playlists p ON p.id = i.playlist_id AND p.is_public = TRUE
            JOIN suno_tasks t ON t.id = i.suno_task_id
            WHERE UPPER(t.status) = 'SUCCESS'
              AND (
                (i.variant = 'ok' AND (
                    COALESCE(t.package_status_ok, 'none') = 'ready'
                    OR COALESCE(t.b2_storage_key_ok, t.audio_url_ok) IS NOT NULL
                ))
                OR (i.variant = 'alt' AND (
                    COALESCE(t.package_status_alt, 'none') = 'ready'
                    OR COALESCE(t.b2_storage_key_alt, t.audio_url_alt) IS NOT NULL
                ))
              )
            """
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            task_id = str(row["suno_task_id"])
            variant = str(row["variant"] or "ok")
            added = row["added_at"]
            items.append(
                {
                    "id": f"{task_id}:{variant}",
                    "task_id": task_id,
                    "variant": variant,
                    "title": str(row["title"] or "Untitled"),
                    "artist_name": str(row["artist_name"] or "Camxora Creator"),
                    "user_id": str(row["user_id"]),
                    "playlist_name": str(row["playlist_name"] or ""),
                    "style": str(row["style"] or ""),
                    "genre": str(row["style"] or "").strip() or None,
                    "cover_url": str(row.get("cover_url") or "").strip() or None,
                    "play_url": await self._mint_public_play_url(UUID(task_id), variant),
                    "package_status": str(row.get("package_status") or "none"),
                    "added_at": added.isoformat() if hasattr(added, "isoformat") else str(added or ""),
                    "play_count": int(row.get("play_count") or 0),
                }
            )
        return {"items": items, "total": int(total or 0), "limit": limit, "offset": offset}

    async def _increment_play_count(self, task_id: UUID, variant: str) -> int:
        variant_key = str(variant or "ok").strip().lower()
        value = await self._pool.fetchval(
            """
            INSERT INTO web_music_play_counts (task_id, variant, play_count)
            VALUES ($1, $2, 1)
            ON CONFLICT (task_id, variant) DO UPDATE
            SET play_count = web_music_play_counts.play_count + 1,
                updated_at = NOW()
            RETURNING play_count
            """,
            task_id,
            variant_key,
        )
        return int(value or 0)

    async def list_liked_generation_keys(self, user_id: UUID) -> list[str]:
        rows = await self._pool.fetch(
            """
            SELECT task_id, variant
            FROM web_music_likes
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [f"{row['task_id']}:{row['variant']}" for row in rows]

    async def like_generation(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
    ) -> bool:
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        row = await self._pool.fetchrow(
            """
            SELECT t.id
            FROM suno_tasks t
            WHERE t.id = $1
              AND t.source = $2
              AND UPPER(t.status) = 'SUCCESS'
              AND (
                t.user_id = $3
                OR EXISTS (
                  SELECT 1
                  FROM web_music_playlist_items i
                  JOIN web_music_playlists p
                    ON p.id = i.playlist_id AND p.is_public = TRUE
                  WHERE i.suno_task_id = t.id AND i.variant = $4
                )
              )
            """,
            task_id,
            SUNO_TASK_SOURCE_WEB_MUSIC,
            user_id,
            variant_key,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        result = await self._pool.execute(
            """
            INSERT INTO web_music_likes (user_id, task_id, variant)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, task_id, variant) DO NOTHING
            """,
            user_id,
            task_id,
            variant_key,
        )
        return result.endswith("INSERT 0 1")

    async def unlike_generation(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        variant: str,
    ) -> bool:
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in ("ok", "alt"):
            raise ValidationError("variant must be ok or alt.", details={"field": "variant"})
        result = await self._pool.execute(
            """
            DELETE FROM web_music_likes
            WHERE user_id = $1 AND task_id = $2 AND variant = $3
            """,
            user_id,
            task_id,
            variant_key,
        )
        return result.endswith("DELETE 1")


def content_disposition(filename: str, *, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    ascii_name = "".join(ch if ch.isascii() and ch not in '"\\' else "_" for ch in filename) or "track.mp3"
    encoded = quote(filename)
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
