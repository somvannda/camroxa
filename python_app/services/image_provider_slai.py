from __future__ import annotations

import base64
import io
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from typing import Any

from PIL import Image


_SLAI_IMAGE_ENDPOINTS = (
    "https://api-img.slai.shop/v1/images/generations",
    "https://api.slai.shop/v1/images/generations",
)


def _slai_debug_event(hypothesis_id: str, location: str, msg: str, data: dict | None = None) -> None:
    try:
        dbg_url = os.environ.get("DEBUG_SERVER_URL") or "http://127.0.0.1:7777/event"
        dbg_session = os.environ.get("DEBUG_SESSION_ID") or "suno-path-image-retry"
        dbg_env = __import__("pathlib").Path(__file__).resolve().parents[2] / ".dbg" / "suno-path-image-retry.env"
        if dbg_env.exists():
            for dbg_line in dbg_env.read_text(encoding="utf-8", errors="ignore").splitlines():
                dbg_line = str(dbg_line or "").strip()
                if dbg_line.startswith("DEBUG_SERVER_URL="):
                    dbg_url = dbg_line.split("=", 1)[1].strip() or dbg_url
                elif dbg_line.startswith("DEBUG_SESSION_ID="):
                    dbg_session = dbg_line.split("=", 1)[1].strip() or dbg_session
        payload = {"sessionId": dbg_session, "runId": "pre-fix", "hypothesisId": hypothesis_id, "location": location, "msg": msg, "data": data or {}}
        urllib.request.urlopen(urllib.request.Request(dbg_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"), timeout=2).read(1)
    except Exception:
        pass


def slai_generate_image_png_bytes(
    *,
    api_key: str,
    model: str,
    prompt: str,
    image_png_bytes: bytes,
    resolution: str,
    timeout_sec: int = 120,
) -> bytes:
    key = str(api_key or "").strip()
    if not key:
        raise RuntimeError("SLAI IMG API key is not configured")
    m = str(model or "").strip() or "cgpt-web/gpt-5.5-pro"
    p = str(prompt or "").strip()
    if not p:
        raise RuntimeError("Prompt is empty")
    if not image_png_bytes:
        raise RuntimeError("Base image is missing")
    # Limit image size to prevent "Maximum call stack size exceeded" errors
    # Max ~4MB PNG for reliable base64 upload (~5.3MB after encoding)
    MAX_IMAGE_BYTES = 4 * 1024 * 1024
    if len(image_png_bytes) > MAX_IMAGE_BYTES:
        # Resize/recompress the image to fit within limits
        from PIL import Image as _PILImage
        _img = _PILImage.open(io.BytesIO(image_png_bytes)).convert("RGBA")
        # Reduce dimensions proportionally until it fits
        for _quality_scale in (0.75, 0.5, 0.4, 0.3):
            _new_w = max(100, int(_img.width * _quality_scale))
            _new_h = max(100, int(_img.height * _quality_scale))
            _resized = _img.resize((_new_w, _new_h), _PILImage.Resampling.LANCZOS)
            _buf = io.BytesIO()
            _resized.save(_buf, format="PNG", optimize=True)
            if _buf.tell() <= MAX_IMAGE_BYTES:
                image_png_bytes = _buf.getvalue()
                break
        else:
            # Last resort: use the smallest resize
            _buf = io.BytesIO()
            _resized.save(_buf, format="PNG", optimize=True)
            image_png_bytes = _buf.getvalue()
    res = str(resolution or "").strip()
    aspect_ratio = "9:16" if res == "1080x1920" else "16:9"
    image_url = f"data:image/png;base64,{base64.b64encode(image_png_bytes).decode('ascii')}"
    raw = ""
    last_status = 0
    last_url = str(_SLAI_IMAGE_ENDPOINTS[0])
    last_err = ""
    ok = False
    ctx = ssl.create_default_context()
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    except Exception:
        pass
    for endpoint in _SLAI_IMAGE_ENDPOINTS:
        last_url = endpoint
        # Strictly follow SLAI-IMG.json documented contract: application/json
        body = json.dumps({
            "model": m,
            "prompt": p,
            "image_url": image_url,
            "aspect_ratio": aspect_ratio,
        }).encode("utf-8")
        content_type = "application/json"
        attempts = 0
        max_attempts = 2
        while attempts < max_attempts:
            attempts += 1
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=body,
                    headers={
                        "Content-Type": content_type,
                        "Authorization": f"Bearer {key}",
                        "Connection": "close",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=int(timeout_sec or 120), context=ctx) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    ok = True
                    break
            except urllib.error.HTTPError as exc:
                last_status = int(getattr(exc, "code", 0) or 0)
                raw = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
                msg = _slai_image_error_message(last_status, raw)
                if last_status in (404, 405):
                    break
                if _is_retryable_http_error(last_status, msg) and attempts < max_attempts:
                    time.sleep(0.8 * attempts)
                    continue
                if _is_retryable_http_error(last_status, msg):
                    last_err = msg
                    break
                raise RuntimeError(f"{msg} (HTTP {last_status} · {endpoint})") from exc
            except Exception as exc:
                last_err = str(exc)
                if attempts < max_attempts:
                    time.sleep(0.6 * attempts)
                    continue
                break
        if ok:
            break

    if not ok:
        if last_status:
            raise RuntimeError(f"{_slai_image_error_message(last_status, raw)} (endpoint: {last_url})")
        raise RuntimeError(f"{last_err or 'SLAI request failed'} (endpoint: {last_url})")

    png_bytes = _extract_png_bytes_from_slai_response(raw)
    url = _extract_url_from_slai_response(raw)
    png_bytes_valid = _is_valid_image_bytes(png_bytes)
    placeholder_info = _extract_slai_placeholder_info(raw)
    is_text_response = bool(placeholder_info.get("is_text_response"))
    is_pending_task = bool(placeholder_info.get("is_pending_task"))
    cache_id = str(placeholder_info.get("cache_id", "") or "").strip()
    # #region debug-point slai-response-shape
    try:
        _slai_debug_event(
            "D",
            "image_provider_slai.slai_generate_image_png_bytes:response_shape",
            "[DEBUG] inspected SLAI provider response shape",
            {
                "hasB64Json": bool(png_bytes),
                "b64ImageValid": png_bytes_valid,
                "hasFallbackUrl": bool(url),
                "fallbackUrlHost": (url.split("/")[2][:80] if "://" in url else ""),
                "isTextResponse": is_text_response,
                "isPendingTask": is_pending_task,
                "hasCacheId": bool(cache_id),
            },
        )
    except Exception:
        pass
    # #endregion
    if png_bytes_valid:
        return png_bytes

    if png_bytes and not png_bytes_valid:
        # #region debug-point slai-invalid-b64-image
        try:
            _slai_debug_event(
                "D",
                "image_provider_slai.slai_generate_image_png_bytes:invalid_b64_image",
                "[DEBUG] SLAI b64_json decoded but is not a valid image; evaluating fallback URL",
                {
                    "decodedBytes": len(png_bytes),
                    "hasFallbackUrl": bool(url),
                    "placeholderDetected": placeholder_detected,
                    "hasCacheId": bool(cache_id),
                },
            )
        except Exception:
            pass
        # #endregion

    if url:
        # #region debug-point slai-fallback-after-b64-invalid
        try:
            _slai_debug_event(
                "D",
                "image_provider_slai.slai_generate_image_png_bytes:fallback_after_b64_invalid",
                "[DEBUG] using SLAI fallback URL after missing/invalid b64 image bytes",
                {"b64Present": bool(png_bytes), "b64ImageValid": png_bytes_valid},
            )
        except Exception:
            pass
        # #endregion
        return _download_slai_fallback_image_bytes(
            url=url,
            api_key=key,
            timeout_sec=int(timeout_sec or 120),
            context=ctx,
        )

    is_text_response = bool(placeholder_info.get("is_text_response"))
    is_pending_task = bool(placeholder_info.get("is_pending_task"))
    
    if is_text_response:
        raise RuntimeError(
            "SLAI returned a text response instead of an image. The model may not support this request, "
            "the prompt is invalid, or the API key lacks permissions. "
            f"Response preview: {_preview_error_text(raw)}"
        )

    if is_pending_task and cache_id:
        # #region debug-point slai-pending-task-detected
        try:
            _slai_debug_event(
                "E",
                "image_provider_slai.slai_generate_image_png_bytes:pending_task_detected",
                "[DEBUG] detected genuinely pending SLAI async task; starting retrieval polling",
                {
                    "cacheId": cache_id[:120],
                    "status": str(placeholder_info.get("status", "") or "")[:120],
                },
            )
        except Exception:
            pass
        # #endregion
        try:
            retrieved_bytes, retrieved_url = _retrieve_slai_cached_result(
                cache_id=cache_id,
                api_key=key,
                timeout_sec=int(timeout_sec or 120),
                context=ctx,
                endpoint_hint=last_url,
            )
            if _is_valid_image_bytes(retrieved_bytes):
                return retrieved_bytes
            if retrieved_url:
                return _download_slai_fallback_image_bytes(
                    url=retrieved_url,
                    api_key=key,
                    timeout_sec=int(timeout_sec or 120),
                    context=ctx,
                )
            raise RuntimeError("retrieval completed without final image bytes or URL")
        except Exception as exc:
            raise RuntimeError(
                f"SLAI pending task retrieval failed (cache_id={cache_id[:80]}): {exc}. Initial response preview: {_preview_error_text(raw)}"
            ) from exc

    raise RuntimeError(
        f"SLAI image generation returned no image bytes (expected b64_json; no usable fallback URL returned). Response preview: {_preview_error_text(raw)}"
    )


def _encode_multipart_form(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----mgBoundary{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for k, v in (fields or {}).items():
        name = str(k or "").strip()
        if not name:
            continue
        value = str(v or "")
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        lines.append(value.encode("utf-8"))
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(lines), f"multipart/form-data; boundary={boundary}"


def _parse_slai_response(raw: str) -> dict:
    try:
        parsed = json.loads(str(raw or ""))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_slai_data_row(parsed: dict) -> dict:
    data = parsed.get("data")
    row = data[0] if isinstance(data, list) and data else None
    return row if isinstance(row, dict) else {}


def _extract_slai_b64_string_from_payload(parsed: dict) -> str:
    row = _extract_slai_data_row(parsed)
    b64 = str(row.get("b64_json", "") or "").strip()
    if not b64:
        b64 = str(parsed.get("b64_json", "") or "").strip()
    return b64


def _extract_png_bytes_from_slai_response(raw: str) -> bytes:
    return _extract_png_bytes_from_slai_payload(_parse_slai_response(raw))


def _extract_png_bytes_from_slai_payload(parsed: dict) -> bytes:
    if not isinstance(parsed, dict) or not parsed:
        return b""
    b64 = _extract_slai_b64_string_from_payload(parsed)
    if not b64:
        return b""
    try:
        return base64.b64decode(b64)
    except Exception:
        return b""


def _extract_url_from_slai_response(raw: str) -> str:
    return _extract_url_from_slai_payload(_parse_slai_response(raw))


def _extract_url_from_slai_payload(parsed: dict) -> str:
    if not isinstance(parsed, dict) or not parsed:
        return ""
    row = _extract_slai_data_row(parsed)
    url = str(row.get("url", "") or "").strip()
    if not url:
        url = str(parsed.get("url", "") or "").strip()
    return url if _looks_like_url(url) else ""


def _extract_output_url_from_slai_payload(parsed: dict) -> str:
    if not isinstance(parsed, dict) or not parsed:
        return ""
    for key in ("outputs", "result", "data"):
        url = _find_first_url(parsed.get(key))
        if url:
            return url
    return _find_first_url(parsed)


def _find_first_url(value) -> str:
    if isinstance(value, str):
        s = str(value or "").strip()
        return s if _looks_like_url(s) else ""
    if isinstance(value, dict):
        for key in ("url", "output_url", "download_url", "presigned_url", "result_url", "image_url", "file_url"):
            s = str(value.get(key, "") or "").strip()
            if _looks_like_url(s):
                return s
        for nested in value.values():
            s = _find_first_url(nested)
            if s:
                return s
    if isinstance(value, list):
        for nested in value:
            s = _find_first_url(nested)
            if s:
                return s
    return ""


def _looks_like_url(value: str) -> bool:
    s = str(value or "").strip().lower()
    return s.startswith("https://") or s.startswith("http://")


def _extract_slai_placeholder_info(raw: str) -> dict:
    parsed = _parse_slai_response(raw)
    row = _extract_slai_data_row(parsed)
    b64 = _extract_slai_b64_string_from_payload(parsed)
    decoded = b""
    placeholder_text = ""
    if b64:
        try:
            decoded = base64.b64decode(b64)
        except Exception:
            decoded = b""
        if decoded:
            try:
                placeholder_text = decoded.decode("utf-8", errors="replace").strip()
            except Exception:
                placeholder_text = ""
    cache_id = str(row.get("cache_id") or parsed.get("cache_id") or row.get("task_id") or parsed.get("task_id") or row.get("taskId") or parsed.get("taskId") or "").strip()
    cache_expires_at = str(row.get("cache_expires_at") or parsed.get("cache_expires_at") or "").strip()
    status = str(row.get("status") or parsed.get("status") or "").strip().lower()
    
    # Detect if the model returned a text response instead of an image
    is_text_response = bool(placeholder_text.lower().startswith("data:text/plain") or placeholder_text.lower().startswith("text/plain"))
    # Detect if it's a genuinely pending async task (not just a cached text reply)
    is_pending_task = bool(cache_id and not is_text_response and status in ("pending", "processing", "queued", "running"))
    
    return {
        "is_text_response": is_text_response,
        "is_pending_task": is_pending_task,
        "cache_id": cache_id,
        "cache_expires_at": cache_expires_at,
        "placeholder_text": placeholder_text,
        "status": status,
    }


def _retrieve_slai_cached_result(*, cache_id: str, api_key: str, timeout_sec: int, context: Any, endpoint_hint: str) -> tuple[bytes, str]:
    safe_cache_id = str(cache_id or "").strip()
    if not safe_cache_id:
        raise RuntimeError("missing cache_id for SLAI placeholder retrieval")
    candidates = _slai_retrieval_candidates(endpoint_hint=endpoint_hint, cache_id=safe_cache_id)
    if not candidates:
        raise RuntimeError("no retrieval endpoint candidates available")
    last_error = ""
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        # #region debug-point slai-placeholder-retrieve-attempt
        try:
            _slai_debug_event(
                "E",
                "image_provider_slai._retrieve_slai_cached_result:attempt_start",
                "[DEBUG] starting SLAI placeholder retrieval attempt",
                {"attempt": attempt, "maxAttempts": max_attempts, "candidateCount": len(candidates), "cacheId": safe_cache_id[:120]},
            )
        except Exception:
            pass
        # #endregion
        for candidate in candidates:
            try:
                raw = _slai_request_json(
                    url=str(candidate.get("url", "") or ""),
                    method=str(candidate.get("method", "GET") or "GET"),
                    api_key=api_key,
                    timeout_sec=timeout_sec,
                    context=context,
                    json_body=(candidate.get("json_body") if isinstance(candidate.get("json_body"), dict) else None),
                )
                parsed = _parse_slai_response(raw)
                direct_bytes = _extract_png_bytes_from_slai_payload(parsed)
                if _is_valid_image_bytes(direct_bytes):
                    # #region debug-point slai-placeholder-retrieve-bytes
                    try:
                        _slai_debug_event(
                            "E",
                            "image_provider_slai._retrieve_slai_cached_result:bytes_ready",
                            "[DEBUG] SLAI placeholder retrieval returned final image bytes",
                            {"attempt": attempt, "candidate": str(candidate.get("label", "") or "")[:120], "bytes": len(direct_bytes)},
                        )
                    except Exception:
                        pass
                    # #endregion
                    return direct_bytes, ""
                final_url = _extract_url_from_slai_payload(parsed) or _extract_output_url_from_slai_payload(parsed)
                if final_url:
                    # #region debug-point slai-placeholder-retrieve-url
                    try:
                        _slai_debug_event(
                            "E",
                            "image_provider_slai._retrieve_slai_cached_result:url_ready",
                            "[DEBUG] SLAI placeholder retrieval returned final image URL",
                            {"attempt": attempt, "candidate": str(candidate.get("label", "") or "")[:120], "urlHost": final_url.split('/')[2][:120] if '://' in final_url else ""},
                        )
                    except Exception:
                        pass
                    # #endregion
                    return b"", final_url
                placeholder_info = _extract_slai_placeholder_info(raw)
                status = _extract_slai_status_text(parsed)
                last_error = f"candidate {candidate.get('label', 'unknown')} did not return final image yet ({status or 'pending'})"
                # #region debug-point slai-placeholder-retrieve-pending
                try:
                    _slai_debug_event(
                        "E",
                        "image_provider_slai._retrieve_slai_cached_result:pending",
                        "[DEBUG] SLAI placeholder retrieval attempt returned no final image yet",
                        {
                            "attempt": attempt,
                            "candidate": str(candidate.get("label", "") or "")[:120],
                            "status": status[:120],
                            "stillPlaceholder": bool(placeholder_info.get("is_placeholder")),
                            "responsePreview": _preview_error_text(raw, limit=140),
                        },
                    )
                except Exception:
                    pass
                # #endregion
            except urllib.error.HTTPError as exc:
                status = int(getattr(exc, "code", 0) or 0)
                detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
                if status in (404, 405):
                    last_error = f"candidate {candidate.get('label', 'unknown')} unsupported (HTTP {status})"
                    continue
                last_error = f"candidate {candidate.get('label', 'unknown')} failed (HTTP {status}): {_preview_error_text(detail) or str(exc)}"
            except Exception as exc:
                last_error = f"candidate {candidate.get('label', 'unknown')} failed: {exc}"
        if attempt < max_attempts:
            time.sleep(min(2.5, 0.75 * attempt))
    raise RuntimeError(last_error or "placeholder retrieval exhausted without final image")


def _slai_retrieval_candidates(*, endpoint_hint: str, cache_id: str) -> list[dict[str, object]]:
    safe_cache_id = urllib.parse.quote(str(cache_id or "").strip(), safe="")
    roots: list[str] = []
    # STRICT DOMAIN ENFORCEMENT: Only use .shop domains as documented in SLAI-IMG.json
    for endpoint in (endpoint_hint, *_SLAI_IMAGE_ENDPOINTS):
        s = str(endpoint or "").strip()
        if not s:
            continue
        parts = urllib.parse.urlsplit(s)
        if not parts.scheme or not parts.netloc:
            continue
        # Ensure we only use .shop domains to prevent getaddrinfo failures
        if ".shop" in parts.netloc:
            root = f"{parts.scheme}://{parts.netloc}"
            if root not in roots:
                roots.append(root)
    
    candidates: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for root in roots:
        for method, url, body, label in (
            ("POST", f"{root}/beam/task", {"action": "retrieve", "task_id": cache_id}, f"{root}/beam/task"),
            ("GET", f"{root}/v1/images/generations/{safe_cache_id}", None, f"{root}/v1/images/generations/{{id}}"),
            ("GET", f"{root}/v1/images/generations/{safe_cache_id}/status", None, f"{root}/v1/images/generations/{{id}}/status"),
            ("GET", f"{root}/v1/images/generations/{safe_cache_id}/result", None, f"{root}/v1/images/generations/{{id}}/result"),
        ):
            key = (method, url)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"method": method, "url": url, "json_body": body, "label": label})
    return candidates


def _slai_request_json(*, url: str, method: str, api_key: str, timeout_sec: int, context: Any, json_body: dict | None = None) -> str:
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Connection": "close",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=str(method or "GET").upper())
    with urllib.request.urlopen(req, timeout=timeout_sec, context=context) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_slai_status_text(parsed: dict) -> str:
    if not isinstance(parsed, dict) or not parsed:
        return ""
    row = _extract_slai_data_row(parsed)
    for source in (row, parsed):
        if not isinstance(source, dict):
            continue
        for key in ("status", "state", "msg", "message", "error_msg"):
            value = str(source.get(key, "") or "").strip()
            if value:
                return value
    return ""


def _is_valid_image_bytes(data: bytes) -> bool:
    blob = bytes(data or b"")
    if not blob:
        return False
    try:
        with Image.open(io.BytesIO(blob)) as img:
            img.verify()
        return True
    except Exception:
        return False


def _extract_image_bytes_from_zip_blob(data: bytes) -> bytes:
    blob = bytes(data or b"")
    if not blob.startswith(b"PK"):
        return b""
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for name in zf.namelist():
                lower = str(name or "").lower()
                if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    extracted = zf.read(name)
                    if _is_valid_image_bytes(extracted):
                        return extracted
    except Exception:
        return b""
    return b""


def _download_slai_fallback_image_bytes(*, url: str, api_key: str, timeout_sec: int, context: Any) -> bytes:
    target_url = str(url or "").strip()
    if not target_url:
        raise RuntimeError("SLAI image fallback URL is empty")
    last_status = 0
    last_detail = ""
    last_error = ""
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        # #region debug-point slai-fallback-attempt-start
        try:
            _slai_debug_event(
                "E",
                "image_provider_slai._download_slai_fallback_image_bytes:attempt_start",
                "[DEBUG] starting SLAI fallback image download attempt",
                {"attempt": attempt, "maxAttempts": max_attempts},
            )
        except Exception:
            pass
        # #endregion
        try:
            req = urllib.request.Request(
                target_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Connection": "close",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec, context=context) as resp:
                img_bytes = resp.read()
                if img_bytes:
                    if _is_valid_image_bytes(img_bytes):
                        # #region debug-point slai-fallback-attempt-success
                        try:
                            _slai_debug_event(
                                "E",
                                "image_provider_slai._download_slai_fallback_image_bytes:attempt_success",
                                "[DEBUG] SLAI fallback image download attempt succeeded",
                                {"attempt": attempt, "status": int(getattr(resp, "status", 200) or 200), "bytes": len(img_bytes)},
                            )
                        except Exception:
                            pass
                        # #endregion
                        return img_bytes
                    extracted = _extract_image_bytes_from_zip_blob(img_bytes)
                    if extracted:
                        # #region debug-point slai-fallback-zip-success
                        try:
                            _slai_debug_event(
                                "E",
                                "image_provider_slai._download_slai_fallback_image_bytes:zip_success",
                                "[DEBUG] SLAI fallback download returned a zip archive; extracted image bytes successfully",
                                {"attempt": attempt, "archiveBytes": len(img_bytes), "imageBytes": len(extracted)},
                            )
                        except Exception:
                            pass
                        # #endregion
                        return extracted
                    last_error = "provider returned non-image bytes from fallback URL"
                else:
                    last_error = "provider returned empty image body from fallback URL"
        except urllib.error.HTTPError as exc:
            last_status = int(getattr(exc, "code", 0) or 0)
            last_detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
            last_error = _preview_error_text(last_detail) or str(exc)
            if not _is_retryable_fallback_status(last_status) or attempt >= max_attempts:
                break
        except Exception as exc:
            last_error = str(exc)
            if attempt >= max_attempts:
                break
        time.sleep(_slai_fallback_retry_delay_sec(attempt, last_status))

    detail = last_error or "fallback URL download failed"
    if last_status:
        raise RuntimeError(
            f"SLAI image fallback URL download failed after retries (HTTP {last_status}): {detail} · URL: {target_url}"
        )
    raise RuntimeError(f"SLAI image fallback URL download failed after retries: {detail} · URL: {target_url}")


def _slai_fallback_retry_delay_sec(attempt: int, status: int) -> float:
    code = int(status or 0)
    if code == 404:
        return 1.0 * max(1, attempt)
    return min(4.0, 0.75 * max(1, attempt))


def _is_retryable_fallback_status(status: int) -> bool:
    code = int(status or 0)
    if code in (404, 408, 409, 425, 429, 500, 502, 503, 504):
        return True
    return False


def _slai_image_error_message(status: int, raw: str) -> str:
    msg = f"SLAI image generation request failed ({int(status or 0) or 'unknown'})"
    try:
        parsed = json.loads(str(raw or ""))
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict) and str(err.get("message", "")).strip():
                return str(err.get("message", "")).strip()
    except Exception:
        pass
    preview = _preview_error_text(raw)
    if preview:
        return preview
    return msg


def _is_retryable_http_error(status: int, message: str) -> bool:
    code = int(status or 0)
    if code in (408, 409, 425, 429, 500, 502, 503, 504):
        return True
    if code == 403:
        s = str(message or "").lower()
        if "turnstile" in s or "sentinel" in s or "blocked the request" in s:
            return True
    return False


def _preview_error_text(raw: str, limit: int = 220) -> str:
    preview = str(raw or "").strip()
    if not preview:
        return ""
    return preview[: int(limit or 220)]
