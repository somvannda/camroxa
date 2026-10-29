#!/usr/bin/env python3
"""Probe Camxora's musicapi for platform_api contract compatibility.

Purpose: confirm the endpoints the backend actually calls return the response
shapes its parsers expect, and confirm multi-account task ownership (record-info
is scoped to the account that created the task). The old reseller is retired;
this probe targets ``musicapi.camxora.com``.

Read-only by default: it only calls the free `/api/v1/generate/credit` and
`/api/v1/generate/record-info` endpoints. Credit-spending calls (generate, WAV,
timestamped lyrics, recovery) require `--spend`.

Examples
--------
    # Read-only: credit shape + which pool key owns an existing task
    python scripts/deploy/probe_musicapi_compat.py \
        --base-url https://musicapi.camxora.com \
        --key "$MUSICAPI_KEY_1" --key "$MUSICAPI_KEY_2" \
        --task-id a1b2c3d4e5f6

    # Full E2E (spends credits): instrumental generate + WAV + lyrics + recovery
    python scripts/deploy/probe_musicapi_compat.py --spend \
        --base-url https://musicapi.camxora.com --key "$MUSICAPI_KEY" \
        --audio-id <clip-id>

Environment fallbacks: PLATFORM_SUNO_API_BASE_URL, MUSICAPI_PROBE_KEYS
(comma-separated), PLATFORM_SUNO_TIMEOUT_SECONDS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Make the repo's platform_api importable when run as a loose script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx

DEFAULT_BASE_URL = "https://musicapi.camxora.com"
DEFAULT_TIMEOUT = 30.0


def _print(label: str, payload: Any) -> None:
    print(f"\n=== {label} ===")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:4000])
    else:
        print(payload)


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def probe_credit(client: httpx.Client, base_url: str, key: str, index: int) -> None:
    try:
        resp = client.get(f"{base_url}/api/v1/generate/credit", headers=_headers(key))
        body = resp.json()
    except Exception as exc:  # noqa: BLE001 - probe reports, never raises
        _print(f"credit [key {index}]", f"ERROR {exc}")
        return
    # platform_api._normalize_suno accepts a bare int OR data.credits.
    data = body.get("data") if isinstance(body, dict) else None
    shape = "bare-int" if isinstance(data, (int, float)) else type(data).__name__
    _print(f"credit [key {index}] HTTP {resp.status_code} shape={shape}", body)


def probe_record_info(
    client: httpx.Client, base_url: str, key: str, index: int, task_id: str
) -> None:
    try:
        resp = client.get(
            f"{base_url}/api/v1/generate/record-info",
            params={"taskId": task_id},
            headers=_headers(key),
        )
    except Exception as exc:  # noqa: BLE001
        _print(f"record-info [key {index}]", f"ERROR {exc}")
        return
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = resp.text[:500]
    data = body.get("data") if isinstance(body, dict) else {}
    status = data.get("status") if isinstance(data, dict) else None
    response = data.get("response") if isinstance(data, dict) else {}
    tracks = response.get("sunoData") if isinstance(response, dict) else None
    parsed: Any
    try:
        from platform_api.clients.suno_client import parse_suno_generate_poll

        parsed = parse_suno_generate_poll(body).state
    except Exception as exc:  # noqa: BLE001
        parsed = f"parse-error: {exc}"
    _print(
        f"record-info [key {index}] HTTP {resp.status_code} status={status} "
        f"tracks={len(tracks) if isinstance(tracks, list) else 'n/a'} parsed={parsed}",
        {
            "keys": sorted(tracks[0].keys()) if isinstance(tracks, list) and tracks else [],
            "has_sunoData": isinstance(tracks, list),
            "has_response_data": isinstance(response, dict)
            and isinstance(response.get("data"), list),
        },
    )
    if resp.status_code in (401, 403):
        print("  -> this key does NOT own the task (expected for other accounts)")


def probe_generate_instrumental(
    client: httpx.Client, base_url: str, key: str
) -> str | None:
    """POST /api/v1/generate with custom-mode instrumental + empty lyrics."""
    payload = {
        "model": "V6",
        "title": "Compat Probe Instrumental",
        "prompt": "[Instrumental]",
        "style": "calm ambient piano",
        "instrumental": True,
        "customMode": True,
    }
    resp = client.post(f"{base_url}/api/v1/generate", json=payload, headers=_headers(key))
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = resp.text[:500]
    _print(f"generate instrumental HTTP {resp.status_code}", body)
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict):
            return str(data.get("taskId") or "") or None
    return None


def poll_until_success(
    client: httpx.Client, base_url: str, key: str, task_id: str, *, attempts: int = 40
) -> dict[str, Any] | None:
    for _ in range(attempts):
        time.sleep(3.0)
        resp = client.get(
            f"{base_url}/api/v1/generate/record-info",
            params={"taskId": task_id},
            headers=_headers(key),
        )
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            continue
        status = str((body.get("data") or {}).get("status") or "").upper()
        if status in {"SUCCESS", "COMPLETE", "COMPLETED"}:
            _print("generate poll SUCCESS", body)
            return body
        if "FAIL" in status:
            _print("generate poll FAILED", body)
            return body
    _print("generate poll TIMEOUT", task_id)
    return None


def probe_timestamped_lyrics(
    client: httpx.Client, base_url: str, key: str, task_id: str, audio_id: str
) -> None:
    resp = client.post(
        f"{base_url}/api/v1/generate/get-timestamped-lyrics",
        json={"taskId": task_id, "audioId": audio_id},
        headers=_headers(key),
    )
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = resp.text[:500]
    aligned = None
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict):
            aligned = data.get("alignedWords")
    _print(
        f"get-timestamped-lyrics HTTP {resp.status_code} "
        f"has_alignedWords={isinstance(aligned, list)} (platform_api expects sync alignedWords)",
        body,
    )


def probe_wav(
    client: httpx.Client, base_url: str, key: str, task_id: str, audio_id: str
) -> None:
    resp = client.post(
        f"{base_url}/api/v1/wav/generate",
        json={"taskId": task_id, "audioId": audio_id},
        headers=_headers(key),
    )
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = resp.text[:500]
    _print(f"wav/generate HTTP {resp.status_code}", body)
    data = body.get("data") if isinstance(body, dict) else {}
    wav_task = data.get("taskId") if isinstance(data, dict) else None
    if not wav_task:
        return
    for _ in range(40):
        time.sleep(3.0)
        poll = client.get(
            f"{base_url}/api/v1/wav/record-info",
            params={"taskId": wav_task},
            headers=_headers(key),
        )
        try:
            poll_body = poll.json()
        except Exception:  # noqa: BLE001
            continue
        from platform_api.clients.suno_client import parse_suno_wav_poll

        status, url, _error = parse_suno_wav_poll(poll_body)
        if status != "pending":
            _print(f"wav/record-info parsed status={status} url={bool(url)}", poll_body)
            return
    _print("wav/record-info TIMEOUT", wav_task)


def probe_recovery(
    client: httpx.Client, base_url: str, key: str, task_id: str, audio_id: str
) -> None:
    resp = client.post(
        f"{base_url}/api/v1/suno/recovery",
        json={"sunoTaskId": task_id, "taskId": task_id, "audioId": audio_id},
        headers=_headers(key),
    )
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = resp.text[:500]
    _print(f"suno/recovery HTTP {resp.status_code}", body)


def _first_audio_id(body: Any) -> str:
    """Pull the first clip id from a record-info success payload."""
    data = body.get("data") if isinstance(body, dict) else {}
    response = data.get("response") if isinstance(data, dict) else {}
    tracks = None
    if isinstance(response, dict):
        tracks = response.get("sunoData") or response.get("data")
    if isinstance(tracks, list):
        for item in tracks:
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]:
                return item["id"]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PLATFORM_SUNO_API_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--key", action="append", default=[], help="API key (repeatable)")
    parser.add_argument("--task-id", default="", help="Existing taskId to read/submit against")
    parser.add_argument("--audio-id", default="", help="Existing clip id for WAV/lyrics")
    parser.add_argument(
        "--spend",
        action="store_true",
        help="Enable credit-spending probes (generate/wav/timestamped/recovery)",
    )
    args = parser.parse_args()

    keys = list(args.key)
    if not keys:
        env_keys = os.environ.get("MUSICAPI_PROBE_KEYS", "")
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    base_url = args.base_url.rstrip("/")
    timeout = float(os.environ.get("PLATFORM_SUNO_TIMEOUT_SECONDS", DEFAULT_TIMEOUT))

    print(f"base_url={base_url} keys={len(keys)} spend={args.spend}")
    if not keys:
        print("No keys provided. Pass --key or set MUSICAPI_PROBE_KEYS.")
        return 2

    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for index, key in enumerate(keys, start=1):
            probe_credit(client, base_url, key, index)
        if args.task_id:
            for index, key in enumerate(keys, start=1):
                probe_record_info(client, base_url, key, index, args.task_id)

        if not args.spend:
            print("\nRead-only probes complete. Re-run with --spend for credit-spending checks.")
            return 0

        key = keys[0]
        task_id = args.task_id
        audio_id = args.audio_id
        if not audio_id:
            task_id = probe_generate_instrumental(client, base_url, key) or task_id
            body = poll_until_success(client, base_url, key, task_id) if task_id else None
            audio_id = _first_audio_id(body)
            print(f"\nresolved taskId={task_id} audioId={audio_id}")
        if audio_id:
            probe_timestamped_lyrics(client, base_url, key, task_id, audio_id)
            probe_wav(client, base_url, key, task_id, audio_id)
            probe_recovery(client, base_url, key, task_id, audio_id)
        else:
            print("\nNo audioId resolved; skipping WAV/timestamped/recovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
