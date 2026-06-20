from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request


def _json_post(url: str, *, api_key: str, payload: dict, timeout_sec: int) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid Suno lyrics response")
    return parsed


def _json_get(url: str, *, api_key: str, timeout_sec: int) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid Suno lyrics response")
    return parsed


def submit_generate_lyrics(
    *,
    api_base_url: str,
    api_key: str,
    prompt: str,
    callback_url: str,
    timeout_sec: int = 30,
) -> str:
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.sunoapi.org"
    url = f"{base}/api/v1/lyrics"
    payload = {
        "prompt": str(prompt or "").strip(),
        "callBackUrl": str(callback_url or "").strip(),
    }
    try:
        parsed = _json_post(url, api_key=api_key, payload=payload, timeout_sec=int(timeout_sec))
    except urllib.error.HTTPError as exc:
        preview = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        status = int(getattr(exc, "code", 0) or 0)
        if status in (401, 403):
            raise RuntimeError(f"Suno lyrics forbidden/unauthorized (HTTP {status}). Check Suno API key/permissions/credits. Details: {preview[:400]}") from exc
        raise RuntimeError(f"Suno lyrics API error {status}: {preview[:400]}") from exc
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    code = int(parsed.get("code", 0) or 0)
    if code != 200:
        raise RuntimeError(str(parsed.get("msg", "")).strip() or f"Suno lyrics request failed (code {code})")
    task_id = ""
    data = parsed.get("data")
    if isinstance(data, dict):
        task_id = str(data.get("taskId", "")).strip()
    if not task_id:
        raise RuntimeError("Suno lyrics request returned empty taskId")
    return task_id


def poll_lyrics_record(
    *,
    api_base_url: str,
    api_key: str,
    task_id: str,
    timeout_sec: int = 30,
) -> dict:
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.sunoapi.org"
    qs = urllib.parse.urlencode({"taskId": str(task_id or "").strip()})
    url = f"{base}/api/v1/lyrics/record-info?{qs}"
    try:
        return _json_get(url, api_key=api_key, timeout_sec=int(timeout_sec))
    except urllib.error.HTTPError as exc:
        preview = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        raise RuntimeError(f"Suno lyrics API error {int(getattr(exc, 'code', 0) or 0)}: {preview[:400]}") from exc
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def generate_lyrics_blocking(
    *,
    api_base_url: str,
    api_key: str,
    prompt: str,
    callback_url: str,
    timeout_sec: int = 30,
    poll_timeout_sec: int = 30,
    max_wait_sec: int = 120,
    poll_interval_sec: float = 2.0,
) -> tuple[str, str]:
    task_id = submit_generate_lyrics(
        api_base_url=api_base_url,
        api_key=api_key,
        prompt=prompt,
        callback_url=callback_url,
        timeout_sec=timeout_sec,
    )
    started = time.monotonic()
    last_status = ""
    while True:
        if time.monotonic() - started > float(max_wait_sec):
            raise RuntimeError(f"Suno lyrics timeout (status={last_status or 'PENDING'})")
        parsed = poll_lyrics_record(api_base_url=api_base_url, api_key=api_key, task_id=task_id, timeout_sec=poll_timeout_sec)
        code = int(parsed.get("code", 0) or 0)
        if code != 200:
            raise RuntimeError(str(parsed.get("msg", "")).strip() or f"Suno lyrics poll failed (code {code})")
        data = parsed.get("data") if isinstance(parsed.get("data"), dict) else {}
        status = str((data or {}).get("status", "")).strip().upper()
        last_status = status
        if status and status not in {"PENDING"}:
            if status != "SUCCESS":
                err = str((data or {}).get("errorMessage", "")).strip()
                raise RuntimeError(err or f"Suno lyrics failed (status={status})")
            resp = (data or {}).get("response") if isinstance((data or {}).get("response"), dict) else {}
            variants = resp.get("data") if isinstance(resp.get("data"), list) else []
            for v in variants:
                if not isinstance(v, dict):
                    continue
                text = str(v.get("text", "")).strip()
                title = str(v.get("title", "")).strip()
                v_status = str(v.get("status", "")).strip().lower()
                if text and (not v_status or v_status == "complete"):
                    return text, title
            raise RuntimeError("Suno lyrics returned no completed variants")
        time.sleep(float(poll_interval_sec))
