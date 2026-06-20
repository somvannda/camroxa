from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# Model registry — maps model key to FAL queue endpoint
# ---------------------------------------------------------------------------

_FAL_MODELS: dict[str, dict[str, Any]] = {
    "flux-dev-i2i": {
        "endpoint": "https://queue.fal.run/fal-ai/flux/dev/image-to-image",
        "label": "FLUX.1 Dev (img2img)",
        "image_field": "image_url",  # single URL string
        "supports_strength": True,
        "supports_guidance": True,
        "default_steps": 28,
        "min_steps": 10,
        "max_steps": 50,
        "default_strength": 0.85,
        "default_guidance": 3.5,
    },
    "flux2-klein": {
        "endpoint": "https://queue.fal.run/fal-ai/flux-2/klein/4b/edit",
        "label": "FLUX.2 Klein 4B (img2img)",
        "image_field": "image_urls",  # list of URLs
        "supports_strength": False,
        "supports_guidance": False,
        "default_steps": 4,
        "min_steps": 4,
        "max_steps": 8,
        "default_strength": None,
        "default_guidance": None,
    },
}

# Default model when the model parameter is empty or unrecognized
_DEFAULT_MODEL = "flux-dev-i2i"

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def fal_generate_image_png_bytes(
    *,
    api_key: str,
    model: str,
    prompt: str,
    image_png_bytes: bytes,
    resolution: str,
    timeout_sec: int = 120,
) -> bytes:
    """Generate an image using the FAL API (supports multiple models).

    Args:
        api_key: FAL API key for authentication.
        model: Model key — one of "flux-dev-i2i", "flux2-klein".
               Falls back to flux-dev-i2i if unrecognized.
        prompt: Text prompt describing the desired image.
        image_png_bytes: Base/reference image PNG bytes used as style input.
        resolution: Target resolution string (e.g. "1920x1080", "1080x1920").
        timeout_sec: Maximum time to wait for generation (default 120s).

    Returns:
        Raw PNG image bytes.

    Raises:
        RuntimeError: If API key is missing, API returns error, or request times out.
    """
    key = str(api_key or "").strip()
    if not key:
        raise RuntimeError("FAL IMG API key is not configured")

    p = str(prompt or "").strip()
    if not p:
        raise RuntimeError("Prompt is empty")

    # Resolve model config
    model_key = str(model or "").strip().lower()
    if model_key not in _FAL_MODELS:
        model_key = _DEFAULT_MODEL
    cfg = _FAL_MODELS[model_key]

    width, height = _parse_resolution(resolution)

    # Build image data URI from PNG bytes
    image_data_uri = ""
    if image_png_bytes:
        b64 = base64.b64encode(image_png_bytes).decode("ascii")
        image_data_uri = f"data:image/png;base64,{b64}"

    # --- Build payload based on model ---
    payload_dict = _build_payload(cfg, p, width, height, image_data_uri)

    submit_payload = json.dumps(payload_dict).encode("utf-8")

    submit_response = _submit_queue_request(
        url=cfg["endpoint"],
        payload=submit_payload,
        api_key=key,
        timeout_sec=timeout_sec,
    )

    status_url = str(submit_response.get("status_url", "") or "").strip()
    response_url = str(submit_response.get("response_url", "") or "").strip()

    if not status_url or not response_url:
        raise RuntimeError(
            "FAL queue submission did not return expected status_url/response_url"
        )

    # --- Poll until COMPLETED or timeout ---
    _poll_until_completed(
        status_url=status_url,
        api_key=key,
        timeout_sec=timeout_sec,
    )

    # --- Fetch result and download image ---
    result = _fetch_result(
        response_url=response_url,
        api_key=key,
        timeout_sec=timeout_sec,
    )

    images = result.get("images")
    if not isinstance(images, list) or not images:
        raise RuntimeError("FAL response contains no images")

    image_url = str(images[0].get("url", "") or "").strip()
    if not image_url:
        raise RuntimeError("FAL response image entry has no URL")

    # --- Download image with retry ---
    png_bytes = _download_image_with_retry(
        url=image_url,
        api_key=key,
        timeout_sec=timeout_sec,
    )

    # Validate PNG magic bytes
    if not png_bytes or not png_bytes.startswith(_PNG_MAGIC):
        raise RuntimeError("FAL returned invalid image data (not a valid PNG)")

    return png_bytes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_payload(
    cfg: dict[str, Any],
    prompt: str,
    width: int,
    height: int,
    image_data_uri: str,
) -> dict[str, Any]:
    """Build the API payload based on model configuration."""
    payload: dict[str, Any] = {
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "num_inference_steps": cfg["default_steps"],
        "output_format": "png",
        "num_images": 1,
        "enable_safety_checker": False,
    }

    if cfg.get("supports_strength") and cfg.get("default_strength") is not None:
        payload["strength"] = cfg["default_strength"]

    if cfg.get("supports_guidance") and cfg.get("default_guidance") is not None:
        payload["guidance_scale"] = cfg["default_guidance"]

    # Attach image reference in the model-specific field
    if image_data_uri:
        image_field = cfg.get("image_field", "image_url")
        if image_field == "image_urls":
            payload["image_urls"] = [image_data_uri]
        else:
            payload["image_url"] = image_data_uri

    return payload


def _parse_resolution(resolution: str) -> tuple[int, int]:
    """Parse a resolution string like '1920x1080' into (width, height)."""
    res = str(resolution or "").strip()
    if not res:
        return 1920, 1080  # sensible default
    parts = res.lower().split("x")
    if len(parts) != 2:
        return 1920, 1080
    try:
        w = int(parts[0].strip())
        h = int(parts[1].strip())
        if w <= 0 or h <= 0:
            return 1920, 1080
        return w, h
    except (ValueError, TypeError):
        return 1920, 1080


def _submit_queue_request(
    *,
    url: str,
    payload: bytes,
    api_key: str,
    timeout_sec: int,
) -> dict:
    """Submit a queue request to FAL with retry on 5xx (up to 2 attempts)."""
    max_attempts = 2
    last_status = 0
    last_detail = ""

    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Key {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
                raise RuntimeError(
                    f"FAL queue submission returned unexpected response format"
                )
        except urllib.error.HTTPError as exc:
            last_status = int(getattr(exc, "code", 0) or 0)
            last_detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
            if 500 <= last_status <= 599 and attempt < max_attempts:
                time.sleep(0.8 * attempt)
                continue
            raise RuntimeError(
                f"FAL queue submission failed (HTTP {last_status}): {_preview(last_detail)}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                time.sleep(0.8 * attempt)
                continue
            raise RuntimeError(
                f"FAL queue submission failed: {exc}"
            ) from exc

    raise RuntimeError(
        f"FAL queue submission failed after {max_attempts} attempts (HTTP {last_status}): {_preview(last_detail)}"
    )


def _poll_until_completed(
    *,
    status_url: str,
    api_key: str,
    timeout_sec: int,
) -> None:
    """Poll the FAL status URL until status is COMPLETED or timeout."""
    deadline = time.time() + timeout_sec
    poll_interval = 1.0

    while True:
        if time.time() >= deadline:
            raise RuntimeError(
                f"FAL image generation timed out after {timeout_sec}s"
            )

        try:
            req = urllib.request.Request(
                status_url,
                headers={
                    "Authorization": f"Key {api_key}",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=min(30, max(5, int(deadline - time.time())))) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                status = str(parsed.get("status", "") or "").strip().upper()

                if status == "COMPLETED":
                    return
                if status in ("FAILED", "ERROR"):
                    error_detail = str(parsed.get("error", "") or "").strip()
                    raise RuntimeError(
                        f"FAL generation failed: {error_detail or 'unknown error'}"
                    )
        except urllib.error.HTTPError as exc:
            code = int(getattr(exc, "code", 0) or 0)
            if 500 <= code <= 599:
                # Transient server error during polling, continue
                pass
            else:
                detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
                raise RuntimeError(
                    f"FAL status poll failed (HTTP {code}): {_preview(detail)}"
                ) from exc
        except (urllib.error.URLError, OSError):
            # Transient network error during polling, continue
            pass
        except RuntimeError:
            raise
        except Exception:
            pass

        time.sleep(min(poll_interval, max(0.5, deadline - time.time())))
        poll_interval = min(poll_interval * 1.2, 5.0)


def _fetch_result(
    *,
    response_url: str,
    api_key: str,
    timeout_sec: int,
) -> dict:
    """Fetch the generation result from the response URL."""
    try:
        req = urllib.request.Request(
            response_url,
            headers={
                "Authorization": f"Key {api_key}",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            raise RuntimeError("FAL result response is not a JSON object")
    except urllib.error.HTTPError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        raise RuntimeError(
            f"FAL result fetch failed (HTTP {code}): {_preview(detail)}"
        ) from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"FAL result fetch failed: {exc}") from exc


def _download_image_with_retry(
    *,
    url: str,
    api_key: str,
    timeout_sec: int,
) -> bytes:
    """Download image bytes from URL with retry (3 retries with exponential backoff on 5xx)."""
    max_attempts = 3
    last_status = 0
    last_detail = ""

    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Key {api_key}",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_status = int(getattr(exc, "code", 0) or 0)
            last_detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
            if 500 <= last_status <= 599 and attempt < max_attempts:
                time.sleep(1.0 * (2 ** (attempt - 1)))  # exponential backoff: 1s, 2s
                continue
            raise RuntimeError(
                f"FAL image download failed (HTTP {last_status}): {_preview(last_detail)}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                time.sleep(1.0 * (2 ** (attempt - 1)))
                continue
            raise RuntimeError(
                f"FAL image download failed: {exc}"
            ) from exc

    raise RuntimeError(
        f"FAL image download failed after {max_attempts} attempts (HTTP {last_status}): {_preview(last_detail)}"
    )


def _preview(text: str, limit: int = 220) -> str:
    """Return a truncated preview of error text."""
    s = str(text or "").strip()
    if not s:
        return ""
    return s[:limit]
