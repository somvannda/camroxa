#!/usr/bin/env python3
"""A/B a custom-mode music request against two Suno-compatible providers.

Purpose: confirm that the same resolved prompt produces the same *style* on
`musicapi` as it does on `sunoapi.org` (the fix in
`fix/musicapi-custom-style-prompt` stopped custom-mode lyrics leaking into
Suno's `gpt_description_prompt`).

It submits the identical custom-mode payload to each provider, polls
`record-info`, and prints a side-by-side result (status, audio URL host, and the
provider-echoed tags) so a human can listen and compare the genre.

Safety:
  * Does nothing unless `--spend` is passed (generation costs credits).
  * Refuses a `camxora.com` (production) base URL unless `--allow-production`.
  * Never prints API keys.

Examples
--------
    python scripts/deploy/ab_music_provider_style.py --spend \\
        --style "aggressive EDM, 128 BPM, festival drop" \\
        --lyrics "[Verse]\\nline one\\n[Chorus]\\nline two" \\
        --title "Style AB" \\
        --sunoapi-url https://sunoapi.org --sunoapi-key "$SUNOAPI_KEY" \\
        --musicapi-url https://musicapi.camxora.com --musicapi-key "$MUSICAPI_KEY"
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import httpx

TERMINAL = {"SUCCESS", "GENERATE_AUDIO_FAILED", "FAILED", "ERROR", "REJECTED"}


def _payload(args: argparse.Namespace) -> dict[str, Any]:
    # platform_api's custom-mode shape: prompt=lyrics, style=genre.
    return {
        "customMode": True,
        "instrumental": False,
        "model": args.model,
        "title": args.title,
        "prompt": args.lyrics,
        "style": args.style,
        "callBackUrl": args.callback_url,
    }


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _task_id(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    data = body.get("data")
    if isinstance(data, dict):
        for key in ("taskId", "task_id", "id"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
    for key in ("taskId", "task_id"):
        value = str(body.get(key) or "").strip()
        if value:
            return value
    return ""


def _audio_host(track: dict[str, Any]) -> str:
    url = str(track.get("audio_url") or track.get("audioUrl") or "").strip()
    if not url:
        return "(empty)"
    return url.split("/")[2] if "//" in url else url


def _run_provider(
    *, label: str, base_url: str, key: str, args: argparse.Namespace
) -> None:
    base = base_url.rstrip("/")
    print(f"\n===== {label} ({base}) =====")
    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client:
        resp = client.post(f"{base}/api/v1/generate", headers=_headers(key), json=_payload(args))
        print(f"submit: http={resp.status_code} body={resp.text[:240]}")
        task_id = _task_id(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {})
        if not task_id:
            print("  no task id — stopping")
            return
        print(f"  task={task_id}")
        deadline = time.monotonic() + args.poll_seconds
        while time.monotonic() < deadline:
            time.sleep(args.poll_interval)
            poll = client.get(
                f"{base}/api/v1/generate/record-info",
                headers=_headers(key),
                params={"taskId": task_id},
            )
            body = poll.json() if poll.headers.get("content-type", "").startswith("application/json") else {}
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            status = str(data.get("status") or "").upper()
            print(f"  poll: http={poll.status_code} status={status}")
            if status in TERMINAL:
                tracks = ((data.get("response") or {}).get("sunoData")) or data.get("data") or []
                for track in tracks if isinstance(tracks, list) else []:
                    if isinstance(track, dict):
                        print(
                            f"    track id={track.get('id')} status={track.get('status')} "
                            f"host={_audio_host(track)} tags={track.get('tags')!r}"
                        )
                return
        print("  timed out waiting for a terminal status")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style", required=True, help="Genre/style sent as Suno tags.")
    parser.add_argument("--lyrics", required=True, help="Lyrics sent as the custom-mode prompt.")
    parser.add_argument("--title", default="Style AB")
    parser.add_argument("--model", default="V6")
    parser.add_argument("--callback-url", default="https://localhost/health")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--poll-seconds", type=float, default=300.0)
    parser.add_argument("--poll-interval", type=float, default=8.0)
    parser.add_argument("--spend", action="store_true", help="Actually submit (costs credits).")
    parser.add_argument("--allow-production", action="store_true", help="Allow a camxora.com production host.")
    parser.add_argument("--sunoapi-url", default="")
    parser.add_argument("--sunoapi-key", default="")
    parser.add_argument("--musicapi-url", default="")
    parser.add_argument("--musicapi-key", default="")
    args = parser.parse_args()

    targets = [
        ("sunoapi.org", args.sunoapi_url, args.sunoapi_key),
        ("musicapi", args.musicapi_url, args.musicapi_key),
    ]
    targets = [(name, url, key) for name, url, key in targets if url and key]
    if not targets:
        print("Provide at least one --<provider>-url and --<provider>-key.")
        return 2

    if not args.allow_production:
        prod = [name for name, url, _ in targets if "camxora.com" in url.lower()]
        if prod:
            print(f"Refusing production host(s) {prod} without --allow-production.")
            return 2

    if not args.spend:
        print("Dry run (no --spend). Would submit the same payload to:")
        for name, url, _ in targets:
            print(f"  - {name}: {url}")
        return 0

    for name, url, key in targets:
        try:
            _run_provider(label=name, base_url=url, key=key, args=args)
        except Exception as exc:  # noqa: BLE001 - report and continue to the other provider
            print(f"  ERROR talking to {name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
