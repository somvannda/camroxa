from __future__ import annotations

import json
import urllib.error
import urllib.request


def get_remaining_credits(*, api_base_url: str, api_key: str, timeout_sec: int = 20) -> int:
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.sunoapi.org"
    url = f"{base}/api/v1/generate/credit"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Connection": "close",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=int(timeout_sec)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        preview = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        status = int(getattr(exc, "code", 0) or 0)
        detail = preview[:400].strip()
        try:
            parsed_err = json.loads(preview) if preview else None
            if isinstance(parsed_err, dict):
                code = parsed_err.get("code")
                msg = str(parsed_err.get("msg", "")).strip()
                if code is not None or msg:
                    detail = f"code={code} msg={msg}".strip()
                    if str(code) == "1010" and status == 403:
                        detail = (
                            f"{detail}. This usually means the provider blocked the request "
                            f"(key permission/plan restriction, IP/VPN/region block, or bot protection)."
                        )
        except Exception:
            pass
        raise RuntimeError(f"Suno credits API error {status}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Invalid Suno credits response")
    code = int(parsed.get("code", 0) or 0)
    if code != 200:
        raise RuntimeError(str(parsed.get("msg", "")).strip() or f"Suno credits request failed (code {code})")
    data = parsed.get("data")
    try:
        return int(data or 0)
    except Exception as exc:
        raise RuntimeError("Suno credits response missing integer data") from exc
