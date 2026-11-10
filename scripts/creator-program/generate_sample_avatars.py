#!/usr/bin/env python3
"""Generate sample creator avatars with the SLAI image API.

This is a local, developer-only tool for the Creator Program docs. It:

1. Reads ``platform_api/.env`` (or ``--env-file``) for the database DSN,
   encryption master key, and SLAI base URL.
2. Selects an active SLAI key from ``api_key_entries`` and decrypts it in memory.
3. Calls SLAI ``/v1/images/generations`` for each sample creator.
4. Saves the image to ``docs/creator-program/sample-creators/avatars/<handle>.png``
   and records prompt/hash metadata in ``manifest.json``.

Secrets are never printed or written. The script is safe to keep in the repo.

Usage:
    python scripts/creator-program/generate_sample_avatars.py --check
    python scripts/creator-program/generate_sample_avatars.py
    python scripts/creator-program/generate_sample_avatars.py --only sokha,vannak
    python scripts/creator-program/generate_sample_avatars.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import asyncpg
import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "docs" / "creator-program" / "sample-creators"
AVATAR_DIR = SAMPLE_DIR / "avatars"
CREATORS_FILE = SAMPLE_DIR / "creators.json"
MANIFEST_FILE = SAMPLE_DIR / "manifest.json"

DEFAULT_MODEL = "cx/gpt-image-2.5"
MAX_POLL_SECONDS = 180
POLL_INTERVAL_SECONDS = 5.0
REQUEST_DELAY_SECONDS = 6.0


def load_env_file(path: Path) -> dict[str, str]:
    """Minimal .env parser: KEY=VALUE, ignores comments and blank lines."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def find_env_file(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"Env file not found: {path}")
        return path

    candidates = [
        REPO_ROOT / "platform_api" / ".env",
        REPO_ROOT.parent.parent / "Camxora" / "platform_api" / ".env",
        Path(r"G:\Developments\Projects\Camxora\platform_api\.env"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "Could not find platform_api/.env. Pass --env-file or set the "
        "PLATFORM_DATABASE_URL / PLATFORM_ENCRYPTION_MASTER_KEY env vars."
    )


def normalize_dsn(dsn: str) -> str:
    return (
        dsn.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def build_config(env_file: Path) -> dict[str, str]:
    file_values = load_env_file(env_file)
    config = dict(file_values)
    for key in (
        "PLATFORM_DATABASE_URL",
        "PLATFORM_ENCRYPTION_MASTER_KEY",
        "PLATFORM_SLAI_API_BASE_URL",
    ):
        if os.environ.get(key):
            config[key] = os.environ[key]
    missing = [
        key
        for key in ("PLATFORM_DATABASE_URL", "PLATFORM_ENCRYPTION_MASTER_KEY", "PLATFORM_SLAI_API_BASE_URL")
        if not config.get(key)
    ]
    if missing:
        raise SystemExit(f"Missing required config keys: {', '.join(missing)}")
    return config


async def find_slai_key(dsn: str, master_key: str) -> str:
    from platform_api.services.key_encryption import KeyEncryption

    encryption = KeyEncryption(master_key)
    conn = await asyncpg.connect(normalize_dsn(dsn))
    try:
        rows = await conn.fetch(
            """
            SELECT id, label, encrypted_key_value
            FROM api_key_entries
            WHERE provider = 'slai' AND status = 'active'
            ORDER BY priority ASC, last_used_at ASC NULLS FIRST
            """
        )
    finally:
        await conn.close()

    if not rows:
        raise SystemExit("No active SLAI keys in api_key_entries.")

    for row in rows:
        try:
            return encryption.decrypt(bytes(row["encrypted_key_value"]))
        except Exception:
            continue
    raise SystemExit("Found SLAI keys but none could be decrypted with the configured master key.")


def image_url(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            url = str(first.get("url") or "").strip()
            if url.startswith("http"):
                return url
    return None


def cache_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            value = str(first.get("cache_id") or "").strip()
            if value:
                return value
    value = str(payload.get("cache_id") or "").strip()
    return value or None


async def generate_one(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    prompt: str,
    model: str,
) -> str:
    payload = {
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "response_format": "url",
        "n": 1,
        "model": model,
    }
    response = await client.post(
        f"{base_url.rstrip('/')}/v1/images/generations",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    response.raise_for_status()
    body = response.json()

    url = image_url(body)
    if url:
        return url

    pending = cache_id(body)
    if not pending:
        raise RuntimeError(f"Unexpected SLAI response: {json.dumps(body)[:400]}")

    poll_url = f"{base_url.rstrip('/')}/v1/images/generations/{pending}"
    elapsed = 0.0
    while elapsed < MAX_POLL_SECONDS:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS
        poll = await client.get(poll_url, headers={"Authorization": f"Bearer {api_key}"})
        if poll.status_code == 200:
            body = poll.json()
            url = image_url(body)
            if url:
                return url
        elif poll.status_code not in (202, 404):
            poll.raise_for_status()

    raise RuntimeError(f"SLAI did not finish within {MAX_POLL_SECONDS}s (cache_id={pending}).")


async def download_image(client: httpx.AsyncClient, url: str, destination: Path) -> str:
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise RuntimeError(f"Expected an image, got {content_type!r}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return hashlib.sha256(response.content).hexdigest()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    env_file = find_env_file(args.env_file)
    config = build_config(env_file)
    base_url = config["PLATFORM_SLAI_API_BASE_URL"]
    model = args.model or DEFAULT_MODEL

    if args.check:
        conn = await asyncpg.connect(normalize_dsn(config["PLATFORM_DATABASE_URL"]))
        try:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM api_key_entries WHERE provider = 'slai' AND status = 'active'"
            )
        finally:
            await conn.close()
        print(f"env_file={env_file}")
        print(f"slai_base_url={base_url}")
        print(f"active_slai_keys={count}")
        print(f"creators_file={CREATORS_FILE} (exists={CREATORS_FILE.exists()})")
        return 0

    if not CREATORS_FILE.exists():
        raise SystemExit(f"Missing {CREATORS_FILE}")

    creators = load_json(CREATORS_FILE, [])
    if not isinstance(creators, list) or not creators:
        raise SystemExit("creators.json must be a non-empty list.")

    selected = set(args.only.split(",")) if args.only else None
    targets = [c for c in creators if not selected or c["handle"] in selected]
    if not targets:
        raise SystemExit("No creators matched --only.")

    api_key = await find_slai_key(config["PLATFORM_DATABASE_URL"], config["PLATFORM_ENCRYPTION_MASTER_KEY"])
    manifest = load_json(MANIFEST_FILE, {"model": model, "generated": {}})
    generated = manifest.setdefault("generated", {})

    timeout = httpx.Timeout(connect=15.0, read=180.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for index, creator in enumerate(targets):
            handle = creator["handle"]
            destination = AVATAR_DIR / f"{handle}.png"
            if destination.exists() and not args.force:
                print(f"skip {handle} (exists; use --force)")
                continue

            prompt = creator["avatar_prompt"]
            print(f"generate {handle} ({creator['genres'][0]}) ...", flush=True)
            try:
                url = await generate_one(
                    client, base_url=base_url, api_key=api_key, prompt=prompt, model=model
                )
                digest = await download_image(client, url, destination)
                generated[handle] = {
                    "file": f"avatars/{handle}.png",
                    "prompt": prompt,
                    "model": model,
                    "sha256": digest,
                    "source_url": url,
                    "creator": creator["display_name"],
                }
                save_json(MANIFEST_FILE, manifest)
                print(f"  saved {destination.relative_to(REPO_ROOT)} ({digest[:12]}…)")
            except Exception as exc:  # keep going; report at the end
                print(f"  FAILED {handle}: {exc}", file=sys.stderr)

            if index < len(targets) - 1:
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

    save_json(MANIFEST_FILE, manifest)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to platform_api/.env")
    parser.add_argument("--only", help="Comma-separated handles")
    parser.add_argument("--force", action="store_true", help="Regenerate existing avatars")
    parser.add_argument("--check", action="store_true", help="Print config/DB status without generating")
    parser.add_argument("--model", help=f"SLAI model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
