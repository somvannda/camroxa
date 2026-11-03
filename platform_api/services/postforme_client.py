"""Thin async client for the Post for Me publishing API.

Docs: https://api.postforme.dev/docs
The project API key is server-side only. The desktop never talks to this
client; it receives short-lived signed upload URLs from our own API.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

from platform_api.exceptions import ExternalServiceError, ValidationError

logger = logging.getLogger(__name__)

POSTFORME_AUTH_HEADER = "Authorization"
POSTFORME_WEBHOOK_SECRET_HEADER = "Post-For-Me-Webhook-Secret"

_MAX_ATTEMPTS = 3
_MAX_BACKOFF_SECONDS = 8.0


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, min(_MAX_BACKOFF_SECONDS, float(raw)))
    except (TypeError, ValueError):
        return None


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list) and value:
                return "; ".join(str(item) for item in value)[:500]
    text = response.text.strip()
    return text[:500] if text else f"HTTP {response.status_code}"


class PostForMeClient:
    """JSON client with bounded retries for 429/5xx responses."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.postforme.dev/v1",
        timeout_seconds: int = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self._base_url = str(base_url or "https://api.postforme.dev/v1").rstrip("/")
        self._timeout = max(5, int(timeout_seconds or 30))
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _client(self) -> httpx.AsyncClient:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            POSTFORME_AUTH_HEADER: f"Bearer {self._api_key}",
        }
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
            transport=self._transport,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: list[tuple[str, str]] | None = None,
    ) -> Any:
        if not self.configured:
            raise ExternalServiceError(
                "Post for Me is not configured (PLATFORM_POSTFORME_API_KEY).",
                is_retryable=False,
            )

        last_error: Exception | None = None
        async with self._client() as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = await client.request(
                        method,
                        path,
                        json=json_body,
                        params=params,
                    )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = exc
                    if attempt >= _MAX_ATTEMPTS:
                        break
                    await asyncio.sleep(min(_MAX_BACKOFF_SECONDS, 0.5 * (2 ** (attempt - 1))))
                    continue

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt >= _MAX_ATTEMPTS:
                        raise ExternalServiceError(
                            f"Post for Me returned {response.status_code}: {_error_message(response)}",
                            is_retryable=True,
                            details={"status_code": response.status_code},
                        )
                    delay = _retry_after_seconds(response)
                    if delay is None:
                        delay = min(
                            _MAX_BACKOFF_SECONDS,
                            (0.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.2),
                        )
                    logger.warning(
                        "Post for Me %s %s -> %s, retrying in %.1fs (attempt %d/%d)",
                        method,
                        path,
                        response.status_code,
                        delay,
                        attempt,
                        _MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 400:
                    raise ExternalServiceError(
                        f"Post for Me returned {response.status_code}: {_error_message(response)}",
                        is_retryable=False,
                        details={"status_code": response.status_code},
                    )

                if response.status_code == 204 or not response.content:
                    return None
                try:
                    return response.json()
                except Exception as exc:
                    raise ExternalServiceError(
                        "Post for Me returned a non-JSON response.",
                        is_retryable=False,
                    ) from exc

        raise ExternalServiceError(
            f"Post for Me request failed: {last_error or 'unknown transport error'}",
            is_retryable=True,
        )

    # --- Media ---------------------------------------------------------------

    async def create_media_upload_url(self) -> dict[str, Any]:
        payload = await self._request("POST", "/media/create-upload-url")
        if not isinstance(payload, dict):
            raise ExternalServiceError("Post for Me returned an invalid upload URL payload.")
        if not str(payload.get("upload_url") or "").strip():
            raise ExternalServiceError("Post for Me did not return an upload_url.")
        if not str(payload.get("media_url") or "").strip():
            raise ExternalServiceError("Post for Me did not return a media_url.")
        return payload

    # --- Posts ---------------------------------------------------------------

    async def create_social_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Post payload must be an object.")
        result = await self._request("POST", "/social-posts", json_body=payload)
        if not isinstance(result, dict):
            raise ExternalServiceError("Post for Me returned an invalid post payload.")
        return result

    async def get_social_post(self, post_id: str) -> dict[str, Any]:
        post = str(post_id or "").strip()
        if not post:
            raise ValidationError("post_id is required.")
        result = await self._request("GET", f"/social-posts/{post}")
        return result if isinstance(result, dict) else {}

    async def list_social_posts_by_external_id(
        self, external_id: str
    ) -> list[dict[str, Any]]:
        external = str(external_id or "").strip()
        if not external:
            return []
        payload = await self._request(
            "GET",
            "/social-posts",
            params=[("external_id", external), ("limit", "10")],
        )
        return _data_list(payload)

    async def list_social_post_results(self, post_id: str) -> list[dict[str, Any]]:
        post = str(post_id or "").strip()
        if not post:
            return []
        payload = await self._request(
            "GET",
            "/social-post-results",
            params=[("post_id", post), ("limit", "50")],
        )
        return _data_list(payload)

    # --- Accounts ------------------------------------------------------------

    async def create_account_auth_url(
        self,
        *,
        platform: str,
        external_id: str,
        redirect_url_override: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "platform": str(platform or "").strip(),
            "external_id": str(external_id or "").strip(),
            "permissions": ["posts"],
        }
        if redirect_url_override:
            body["redirect_url_override"] = redirect_url_override
        result = await self._request("POST", "/social-accounts/auth-url", json_body=body)
        if not isinstance(result, dict) or not str(result.get("url") or "").strip():
            raise ExternalServiceError("Post for Me did not return an account auth URL.")
        return result

    async def list_accounts(
        self,
        *,
        account_ids: list[str] | None = None,
        external_id: str | None = None,
        platform: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: list[tuple[str, str]] = [("limit", str(max(1, min(100, int(limit)))))]
        for account_id in account_ids or []:
            value = str(account_id or "").strip()
            if value:
                params.append(("id", value))
        if external_id:
            params.append(("external_id", str(external_id).strip()))
        if platform:
            params.append(("platform", str(platform).strip()))
        payload = await self._request("GET", "/social-accounts", params=params)
        return _data_list(payload)

    async def disconnect_account(self, account_id: str) -> None:
        account = str(account_id or "").strip()
        if not account:
            raise ValidationError("account_id is required.")
        await self._request("POST", f"/social-accounts/{account}/disconnect", json_body={})

    # --- Webhooks ------------------------------------------------------------

    async def create_webhook(
        self, *, url: str, event_types: list[str]
    ) -> dict[str, Any]:
        body = {
            "url": str(url or "").strip(),
            "event_types": [str(item) for item in event_types if str(item).strip()],
        }
        result = await self._request("POST", "/webhooks", json_body=body)
        return result if isinstance(result, dict) else {}

    async def list_webhooks(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/webhooks")
        return _data_list(payload)


def _data_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []
