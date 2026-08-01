"""HTTP client for platform_api — mirrors platformClient.ts."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Literal

import httpx

from shared.services.secure_storage import SecureStorage

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class PlatformApiError(Exception):
    """Raised when the platform API returns a non-success response."""

    def __init__(self, status: int, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


class PlatformClient:
    """Authenticated HTTP client with token refresh on 401."""

    def __init__(self, storage: SecureStorage | None = None, *, default_timeout: float = 30.0) -> None:
        self._storage = storage or SecureStorage()
        self._default_timeout = default_timeout
        self._tokens_provider: Any = None
        self._refresh_callback: Any = None
        self._logout_callback: Any = None
        self._invalidated_token: str | None = None
        self._refresh_lock = threading.Lock()

    def set_session_handlers(
        self,
        *,
        get_tokens: Any,
        refresh_session: Any,
        clear_session: Any,
    ) -> None:
        self._tokens_provider = get_tokens
        self._refresh_callback = refresh_session
        self._logout_callback = clear_session

    def base_url(self) -> str:
        return self._storage.get_api_base_url()

    def request(
        self,
        path: str,
        *,
        method: Method = "GET",
        body: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = False,
        _retry: bool = True,
        timeout: float | None = None,
    ) -> Any:
        response = self._send(
            path,
            method=method,
            body=body,
            params=params,
            auth=auth,
            _retry=_retry,
            accept="application/json",
            timeout=timeout if timeout is not None else self._default_timeout,
        )
        if response.status_code == 204:
            return None
        return _read_json(response)

    def request_bytes(
        self,
        path: str,
        *,
        method: Method = "GET",
        auth: bool = False,
        _retry: bool = True,
        timeout: float | None = None,
        max_network_attempts: int = 2,
    ) -> bytes:
        """Fetch a binary payload (logo/cover images, etc).

        Large downloads are the most exposed to transient connection drops
        (e.g. "peer closed connection without sending complete message
        body" mid-transfer). GET is idempotent, so a bounded retry here is
        safe and saves the caller from surfacing a one-off network hiccup
        as a hard failure.
        """
        attempts = max(1, int(max_network_attempts)) if method.upper() == "GET" else 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = self._send(
                    path,
                    method=method,
                    auth=auth,
                    _retry=_retry,
                    accept="*/*",
                    timeout=timeout if timeout is not None else self._default_timeout,
                )
                return bytes(response.content or b"")
            except PlatformApiError as exc:
                # Only transport-level failures (status 0) are worth retrying —
                # a real 4xx/5xx from the server won't fix itself.
                if exc.status != 0 or attempt >= attempts:
                    raise
                last_error = exc
                try:
                    from shared.services.app_logger import log_warn

                    log_warn(
                        f"Retrying {method.upper()} {path} after transient network error "
                        f"(attempt {attempt + 1}/{attempts}): {exc}",
                        category="api",
                    )
                except Exception:
                    pass
                time.sleep(min(1.5 * attempt, 3.0))
        if last_error is not None:
            raise last_error
        raise PlatformApiError(0, "Request failed with no response.")

    def _send(
        self,
        path: str,
        *,
        method: Method = "GET",
        body: dict[str, Any] | list[Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = False,
        _retry: bool = True,
        accept: str = "application/json",
        timeout: float | None = None,
    ) -> httpx.Response:
        effective_timeout = timeout if timeout is not None else self._default_timeout
        url = f"{self.base_url()}{path if path.startswith('/') else f'/{path}'}"
        headers = {"Accept": accept}
        if body is not None:
            headers["Content-Type"] = "application/json"

        if auth:
            tokens = self._tokens_provider() if self._tokens_provider else None
            if tokens is None:
                self._handle_unauthenticated()
                raise PlatformApiError(401, "Unauthenticated")
            if self._invalidated_token and tokens.accessToken == self._invalidated_token:
                self._handle_unauthenticated()
                raise PlatformApiError(401, "Session expired")
            headers["Authorization"] = f"Bearer {tokens.accessToken}"

        try:
            response = httpx.request(
                method,
                url,
                headers=headers,
                json=body,
                params=params,
                timeout=effective_timeout,
            )
        except httpx.ConnectError as exc:
            err = PlatformApiError(
                0,
                f"Cannot connect to {self.base_url()}. Start platform_api (uvicorn on port 8000).",
            )
            _log_api_error(method, path, err)
            raise err from exc
        except httpx.TimeoutException as exc:
            err = PlatformApiError(0, f"Request timed out contacting {self.base_url()}.")
            _log_api_error(method, path, err)
            raise err from exc
        except httpx.HTTPError as exc:
            err = PlatformApiError(0, f"Network error: {exc}")
            _log_api_error(method, path, err)
            raise err from exc

        if response.status_code == 401 and auth:
            payload = _read_json(response)
            tokens = self._tokens_provider() if self._tokens_provider else None
            if tokens is not None:
                self._invalidated_token = tokens.accessToken
            refreshed = self._refresh_callback(force=True) if self._refresh_callback else False
            if refreshed and _retry:
                self._invalidated_token = None
                return self._send(
                    path,
                    method=method,
                    body=body,
                    params=params,
                    auth=auth,
                    _retry=False,
                    accept=accept,
                    timeout=effective_timeout,
                )
            self._handle_unauthenticated()
            err = PlatformApiError(401, "Session expired", payload)
            _log_api_error(method, path, err)
            raise err

        if not response.is_success:
            payload = _read_json(response)
            message = _extract_error_message(payload, response.status_code)
            err = PlatformApiError(response.status_code, message, payload)
            _log_api_error(method, path, err)
            raise err

        return response

    def _handle_unauthenticated(self) -> None:
        if self._logout_callback:
            self._logout_callback()


def _log_api_error(method: str, path: str, err: PlatformApiError) -> None:
    # Avoid recursive noise if log sync itself fails repeatedly.
    if str(path).rstrip("/").endswith("/client-logs") and method.upper() == "POST":
        return
    if err.status == 422 and "/youtube/" in path and "playlists" in path:
        lowered = str(err).lower()
        if "youtube sign-in expired" in lowered or "reconnect from the youtube tab" in lowered:
            return
    try:
        from shared.services.app_logger import log_error, sanitize_error_body

        detail = sanitize_error_body(str(err), status=err.status)
        log_error(f"{method.upper()} {path} → {err.status}: {detail}", category="api")
    except Exception:
        return


def _read_json(response: httpx.Response) -> Any:
    text = response.text
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_error_message(payload: Any, status: int) -> str:
    """Pull a human-readable message from platform_api / FastAPI error bodies."""
    candidates: list[Any] = []
    if isinstance(payload, dict):
        nested = payload.get("error")
        if isinstance(nested, dict):
            candidates.extend([nested.get("message"), nested.get("detail")])
            details = nested.get("details")
            if isinstance(details, str) and details.strip():
                candidates.append(details)
        candidates.extend([payload.get("message"), payload.get("detail"), payload.get("error")])
    elif isinstance(payload, str):
        candidates.append(payload)

    for value in candidates:
        text = _normalize_error_value(value)
        if text:
            return _friendly_status_message(status, text)

    return _friendly_status_message(status, None)


def _normalize_error_value(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            for key in ("msg", "message", "detail"):
                nested = first.get(key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
        text = str(first).strip()
        return text or None
    if isinstance(value, dict):
        for key in ("message", "detail", "msg"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _friendly_status_message(status: int, server_message: str | None) -> str:
    """Prefer server text; fall back to clear status-based copy (never raw 'Request failed (N)')."""
    from shared.services.app_logger import sanitize_error_body

    text = sanitize_error_body((server_message or "").strip(), status=status)
    if text.startswith("[omitted HTML/gateway error body"):
        text = ""
    # Normalize common auth wording for login UX.
    if text.lower() in {"invalid credentials.", "invalid credentials"}:
        return "Incorrect email or password."
    if text:
        # Keep UI messages short — long dumps are rarely useful to end users.
        if len(text) > 280:
            text = text[:277].rstrip() + "…"
        return text

    defaults = {
        400: "The request could not be completed. Please check your input and try again.",
        401: "Incorrect email or password.",
        403: "You do not have permission to do that.",
        404: "The requested item was not found.",
        409: "That action conflicts with existing data.",
        422: "Some fields are invalid. Please review and try again.",
        429: "Too many requests. Please wait a moment and try again.",
        500: "Something went wrong on the server. Please try again.",
        502: "The service is temporarily unavailable. Please try again.",
        503: "The service is temporarily unavailable. Please try again.",
    }
    return defaults.get(status, "Something went wrong. Please try again.")
