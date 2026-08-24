#!/usr/bin/env python3
"""Smoke-check web music credit hardening + playback auth on sandbox."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.sandbox.camxora.com"


def http(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def main() -> int:
    ok = True
    checks = [
        ("GET", "/health", None, 200),
        ("GET", "/api/v2/credits/balance", None, 401),
        ("GET", "/api/v1/v2/credits/balance", None, 401),
        ("POST", "/api/v2/credits/consume", {"amount": 1, "reason": "test"}, 404),
        (
            "GET",
            "/api/v1/public/streaming/tracks/00000000-0000-0000-0000-000000000001/play-url",
            None,
            401,
        ),
    ]
    for method, path, body, expected in checks:
        status, snippet = http(method, path, body)
        print(f"{method} {path} -> {status} {snippet[:120]}")
        if status != expected:
            print(f"WARN: expected {expected}")
            ok = False

    music_req = urllib.request.Request("https://music.sandbox.camxora.com/", method="GET")
    try:
        with urllib.request.urlopen(music_req, timeout=20) as resp:
            print(f"GET music portal -> {resp.status}")
            if resp.status != 200:
                ok = False
    except urllib.error.HTTPError as exc:
        print(f"GET music portal -> {exc.code}")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
