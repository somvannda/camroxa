"""Generation Proxy — routes AI generation requests through the Platform API.

Implements the GenerationProxyPort protocol, providing:
- Song draft generation (LLM-based)
- Suno music submission and status polling
- Image generation (with base64 encoding/decoding)

All requests include the stored access token in the Authorization header.
On 401, a single token refresh is attempted before retrying the request.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Callable

import httpx

from python_app.services.api_errors import (
    GenerationError,
    InsufficientCreditsError,
    LicenseExpiredError,
    NetworkError,
)
from python_app.services.auth_client import AuthClientPort, AuthTokens
from python_app.services.token_store import StoredTokens, TokenStorePort

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0  # seconds — generation can be slow


class GenerationProxy:
    """Routes generation requests through the Platform API.

    Satisfies the GenerationProxyPort protocol. Uses httpx.Client (sync)
    for all HTTP communication. Designed to be called from worker threads.

    Args:
        base_url: Platform API base URL (e.g. "http://localhost:8000/api/v1").
        token_store: Token persistence layer for reading the current access token.
        auth_client: Auth client used to refresh tokens on 401 responses.
        timeout: Request timeout in seconds. Defaults to 60s.
    """

    def __init__(
        self,
        base_url: str,
        token_store: TokenStorePort,
        auth_client: AuthClientPort,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_store = token_store
        self._auth_client = auth_client
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public API (GenerationProxyPort)
    # ------------------------------------------------------------------

    def generate_song_draft(
        self,
        *,
        language: str,
        creativity_level: int,
        description: str,
        structure: str,
        avoid_titles: list[str] | None = None,
        avoid_albums: list[str] | None = None,
        avoid_openings: list[str] | None = None,
        forced_title: str = "",
        forced_album: str = "",
        forced_opening: str = "",
        on_log: Any = None,
        should_cancel: Any = None,
    ) -> dict[str, str]:
        """Generate a song draft via Platform API.

        Returns dict with keys: 'title', 'album', 'lyrics'.
        """
        body = {
            "language": language,
            "creativity_level": creativity_level,
            "description": description,
            "structure": structure,
            "avoid_titles": avoid_titles or [],
            "avoid_albums": avoid_albums or [],
            "avoid_openings": avoid_openings or [],
            "forced_title": forced_title,
            "forced_album": forced_album,
            "forced_opening": forced_opening,
        }

        response = self._request(
            "POST",
            "/generation/draft",
            json=body,
            on_log=on_log,
            should_cancel=should_cancel,
        )

        data = response.json()
        return {
            "title": data["title"],
            "album": data["album"],
            "lyrics": data["lyrics"],
        }

    def submit_suno(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool,
    ) -> str:
        """Submit music generation to Suno via Platform API.

        Returns task_id string.
        """
        body = {
            "model": model,
            "title": title,
            "lyrics": lyrics,
            "style": style,
            "instrumental": instrumental,
        }

        response = self._request("POST", "/generation/suno", json=body)
        data = response.json()
        return data["task_id"]

    def get_suno_status(self, task_id: str) -> dict:
        """Poll Suno task status via Platform API.

        Returns dict with keys: 'status', 'audioUrls'.
        """
        response = self._request("GET", f"/generation/suno/{task_id}")
        data = response.json()
        return {
            "status": data["status"],
            "audioUrls": data.get("audio_urls", []),
        }

    def generate_image(
        self,
        *,
        prompt: str,
        provider: str,
        resolution: str,
        style_strength: float,
        base_image_png_bytes: bytes | None = None,
    ) -> bytes:
        """Generate an image via Platform API.

        Returns PNG image bytes (decoded from base64 response).
        """
        base_image_b64: str | None = None
        if base_image_png_bytes is not None:
            base_image_b64 = base64.b64encode(base_image_png_bytes).decode("ascii")

        body = {
            "prompt": prompt,
            "provider": provider,
            "resolution": resolution,
            "style_strength": style_strength,
            "base_image": base_image_b64,
        }

        response = self._request("POST", "/generation/image", json=body)
        data = response.json()
        return base64.b64decode(data["image_base64"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """Read current access token from the token store."""
        tokens = self._token_store.load()
        if tokens is None:
            raise NetworkError(
                "No stored authentication tokens. Please log in.",
                status_code=None,
            )
        return tokens.access_token

    def _refresh_and_get_token(self) -> str:
        """Attempt token refresh and return the new access token.

        Saves the refreshed tokens to the token store.
        """
        tokens = self._token_store.load()
        if tokens is None:
            raise NetworkError(
                "No stored tokens available for refresh. Please log in.",
                status_code=None,
            )

        new_auth: AuthTokens = self._auth_client.refresh(tokens.refresh_token)
        self._token_store.save(new_auth.access_token, new_auth.refresh_token)
        return new_auth.access_token

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        on_log: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> httpx.Response:
        """Execute an authenticated HTTP request with 401-retry logic.

        Steps:
        1. Check should_cancel (if provided)
        2. Send request with current access token
        3. On 401: refresh token, then retry once
        4. On 402: raise InsufficientCreditsError
        5. On 403: raise LicenseExpiredError
        6. On success (2xx): return response
        7. On other errors: raise GenerationError
        """
        # Pre-request cancellation check
        if should_cancel is not None and should_cancel():
            raise GenerationError("Operation cancelled by user", status_code=None)

        access_token = self._get_access_token()
        url = f"{self._base_url}{path}"

        response = self._send(method, path, json=json, token=access_token, on_log=on_log)

        # Handle 401 — attempt one token refresh and retry
        if response.status_code == 401:
            logger.debug("Got 401 for %s %s, attempting token refresh", method, path)

            # Check cancellation before retry
            if should_cancel is not None and should_cancel():
                raise GenerationError("Operation cancelled by user", status_code=None)

            new_token = self._refresh_and_get_token()
            response = self._send(method, path, json=json, token=new_token, on_log=on_log)

            # Second 401 — propagate the error
            if response.status_code == 401:
                raise NetworkError(
                    "Authentication failed after token refresh. Please log in again.",
                    status_code=401,
                )

        # Handle specific error codes
        self._check_error_response(response, url)

        return response

    def _send(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        token: str,
        on_log: Callable[[str], None] | None = None,
    ) -> httpx.Response:
        """Send a single HTTP request, translating network errors."""
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {token}"}

        start_time = time.perf_counter()
        try:
            response = self._client.request(
                method,
                path,
                json=json,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise NetworkError(
                f"Request timed out: {method} {url}",
                status_code=None,
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise NetworkError(
                f"Connection failed: {method} {url} — {exc}",
                status_code=None,
            ) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(
                f"HTTP error for {method} {url}: {exc}",
                status_code=None,
            ) from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if on_log is not None:
            on_log(
                f"{method} {path} → {response.status_code} ({elapsed_ms:.0f}ms)"
            )

        return response

    def _check_error_response(self, response: httpx.Response, url: str) -> None:
        """Check response status and raise appropriate errors."""
        status = response.status_code

        if 200 <= status < 300:
            return

        if status == 402:
            msg = self._extract_message(response, "Insufficient credits")
            raise InsufficientCreditsError(msg, status_code=402)

        if status == 403:
            msg = self._extract_message(response, "License expired or inactive")
            raise LicenseExpiredError(msg, status_code=403)

        # Other errors — raise GenerationError
        msg = self._extract_message(response, f"Request failed with status {status}")
        raise GenerationError(f"{msg} ({url})", status_code=status)

    @staticmethod
    def _extract_message(response: httpx.Response, default: str) -> str:
        """Extract error message from JSON response body."""
        try:
            body = response.json()
            return body.get("message", body.get("detail", default))
        except Exception:  # noqa: BLE001
            return default

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

    def __enter__(self) -> GenerationProxy:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
