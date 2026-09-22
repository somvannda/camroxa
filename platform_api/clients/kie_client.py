"""Async HTTP client for the kie.ai unified Market image API.

Uses kie.ai's async task pattern:
  1. POST /api/v1/jobs/createTask  -> {code, msg, data:{taskId}}
  2. GET  /api/v1/jobs/recordInfo?taskId=... until state is success/fail

Text-to-image models (e.g. Grok Imagine Image 2.0) only accept a prompt and an
aspect ratio — there is no reference-image input on this endpoint.

The result is normalized to ``{"data": [{"url": ...}]}`` so the existing image
byte extractor can download it, matching the SLAI/CALA response shape.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from platform_api.ai.registry import resolve_image_model_id
from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "grok-imagine-image-2-0/text-to-image"
_SUCCESS_STATES = frozenset({"success"})
_FAILURE_STATES = frozenset({"fail"})
# kie.ai may return errors as HTTP 200 with a non-200 ``code`` in the body.
# These codes are key/billing related and must trigger key-pool failover, so
# they are re-raised as ``httpx.HTTPStatusError`` (what execute_with_failover
# inspects).
_EXHAUSTED_CODES = frozenset({402, 403})
_RATE_LIMITED_CODES = frozenset({429, 433})
_RETRYABLE_BODY_CODES = frozenset({408, 455, 500, 501})


def _aspect_ratio(width: int, height: int) -> str:
    """Map requested dimensions to a kie.ai supported aspect ratio.

    Supported values: 1:1, 2:3, 3:2, 16:9, 9:16.
    """
    if width <= 0 or height <= 0 or width == height:
        return "1:1"
    ratio = width / height
    if width > height:
        return "16:9" if ratio >= 1.7 else "3:2"
    return "9:16" if ratio <= 0.6 else "2:3"


def _synthetic_status_error(code: int, message: str, *, url: str) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError for a body-level kie.ai error code."""
    request = httpx.Request("POST", url)
    response = httpx.Response(status_code=code, request=request, text=message)
    return httpx.HTTPStatusError(message, request=request, response=response)


class KieClient:
    """Async client for kie.ai's unified Market image API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = (settings.kie_api_base_url or "https://api.kie.ai").rstrip("/")
        self._poll_interval = 3.0
        self._max_poll_seconds = 300.0

    async def close(self) -> None:
        """No persistent client to close (uses per-request clients)."""
        pass

    async def generate_image(
        self,
        *,
        prompt: str,
        model_id: str | None = None,
        width: int = 1920,
        height: int = 1080,
        style_strength: float = 0.6,
        reference_image_base64: str | None = None,
        extra_params: dict[str, Any] | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Submit a text-to-image task and poll until the image is ready."""
        if not api_key:
            raise ExternalServiceError(
                "kie.ai API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "kie"},
            )
        # Text-to-image has no reference/style input; accepted for interface parity.
        _ = (style_strength, reference_image_base64)

        model = resolve_image_model_id("kie", model_id, default=_DEFAULT_MODEL)
        input_params: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": _aspect_ratio(width, height),
        }
        if extra_params:
            input_params.update(extra_params)
        payload: dict[str, Any] = {"model": model, "input": input_params}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        create_url = f"{self._base_url}/api/v1/jobs/createTask"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=15.0),
                headers=headers,
            ) as client:
                response = await client.post(create_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalServiceError(
                "kie.ai createTask timeout",
                is_retryable=True,
                details={"provider": "kie", "reason": "timeout"},
            ) from exc
        except httpx.HTTPStatusError:
            # Surface HTTP 402/403/429 to the key-pool failover loop.
            raise
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                f"kie.ai connection error: {exc}",
                is_retryable=True,
                details={"provider": "kie", "reason": "connection_error"},
            ) from exc

        self._raise_for_body_code(data, url=create_url)
        task_id = self._extract_task_id(data)
        if not task_id:
            raise ExternalServiceError(
                "kie.ai did not return a taskId.",
                is_retryable=False,
                details={"provider": "kie"},
            )
        logger.info("kie.ai task submitted (model=%s taskId=%s)", model, task_id)
        return await self._poll_for_result(api_key, task_id)

    async def _poll_for_result(
        self,
        api_key: str,
        task_id: str,
        *,
        max_wait: float | None = None,
    ) -> dict[str, Any]:
        """Poll kie.ai recordInfo until the task reaches a terminal state."""
        max_wait = self._max_poll_seconds if max_wait is None else max_wait
        poll_url = f"{self._base_url}/api/v1/jobs/recordInfo"
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        elapsed = 0.0

        while elapsed < max_wait:
            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    headers=headers,
                ) as client:
                    resp = await client.get(poll_url, params={"taskId": task_id})
                    resp.raise_for_status()
                    data = resp.json()
            except httpx.HTTPStatusError:
                raise
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.debug("kie.ai poll attempt failed (taskId=%s): %s", task_id, exc)
                continue

            self._raise_for_body_code(data, url=poll_url)
            payload = data.get("data") if isinstance(data, dict) else None
            if not isinstance(payload, dict):
                continue

            state = str(payload.get("state") or "").strip().lower()
            if state in _SUCCESS_STATES:
                return self._normalize_success(payload, task_id=task_id)
            if state in _FAILURE_STATES:
                fail_msg = str(
                    payload.get("failMsg") or payload.get("failCode") or "unknown"
                )
                raise ExternalServiceError(
                    f"kie.ai generation failed: {fail_msg}",
                    is_retryable=False,
                    details={
                        "provider": "kie",
                        "task_id": task_id,
                        "fail_code": payload.get("failCode"),
                        "fail_msg": payload.get("failMsg"),
                    },
                )
            # waiting / queuing / generating -> keep polling

        raise ExternalServiceError(
            f"kie.ai task did not complete within {int(max_wait)}s (taskId={task_id})",
            is_retryable=True,
            details={"provider": "kie", "task_id": task_id},
        )

    @staticmethod
    def _normalize_success(payload: dict[str, Any], *, task_id: str) -> dict[str, Any]:
        """Convert a success payload into the standard ``data[].url`` shape."""
        result_json = payload.get("resultJson")
        parsed: Any = result_json
        if isinstance(result_json, str) and result_json.strip():
            try:
                parsed = json.loads(result_json)
            except (ValueError, TypeError):
                parsed = None

        urls: list[str] = []
        if isinstance(parsed, dict):
            raw_urls = parsed.get("resultUrls")
            if isinstance(raw_urls, list):
                urls = [str(u) for u in raw_urls if u]

        if not urls:
            raise ExternalServiceError(
                "kie.ai returned no result URLs.",
                is_retryable=False,
                details={"provider": "kie", "task_id": task_id},
            )
        return {"data": [{"url": urls[0]}]}

    @staticmethod
    def _extract_task_id(data: Any) -> str:
        payload = data.get("data") if isinstance(data, dict) else None
        if isinstance(payload, dict):
            return str(payload.get("taskId") or "").strip()
        return ""

    @staticmethod
    def _raise_for_body_code(data: Any, *, url: str) -> None:
        """Raise on kie.ai body-level error codes (which may arrive as HTTP 200)."""
        if not isinstance(data, dict):
            raise ExternalServiceError(
                "kie.ai returned a non-JSON response.",
                is_retryable=False,
                details={"provider": "kie"},
            )
        code = data.get("code")
        if code is None:
            return
        try:
            code_int = int(code)
        except (TypeError, ValueError):
            return
        if code_int == 200:
            return

        message = str(data.get("msg") or f"kie.ai error code={code_int}")
        if code_int in _EXHAUSTED_CODES:
            raise _synthetic_status_error(code_int, message, url=url)
        if code_int in _RATE_LIMITED_CODES:
            # 433 (subkey limit) is treated as a rate limit so the key rotates.
            raise _synthetic_status_error(429, message, url=url)
        raise ExternalServiceError(
            f"kie.ai error {code_int}: {message}",
            is_retryable=code_int in _RETRYABLE_BODY_CODES,
            details={"provider": "kie", "status_code": code_int},
        )
