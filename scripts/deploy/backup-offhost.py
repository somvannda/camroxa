#!/usr/bin/env python3
"""Upload the newest database dumps to the private Backblaze B2 bucket.

Runs after the nightly local backups (05:00 Asia/Phnom_Penh) and keeps an
off-host copy of both dumps in case the VPS or its disk is lost. Objects are
stored under ``musicapi/`` and ``platform/``, uploaded with SSE-B2, and remote
copies older than ``BACKUP_REMOTE_RETENTION_DAYS`` are deleted.

The credential lives in ``/opt/camxora/.backup-b2.env`` (root 600):

    B2_BACKUP_BUCKET=camxora-db-backup
    B2_BACKUP_BUCKET_ID=...
    B2_BACKUP_KEY_ID=...
    B2_BACKUP_APP_KEY=...

That key is scoped to the backup bucket only. A successful run writes
``/var/lib/camxora-ops-alert/offhost.last`` (epoch seconds); the ops monitor
pages when it is older than 26h.

    python3 scripts/deploy/backup-offhost.py --dry-run
    python3 scripts/deploy/backup-offhost.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(os.environ.get("B2_BACKUP_ENV_FILE", "/opt/camxora/.backup-b2.env"))
MARKER = Path(
    os.environ.get("OFFHOST_MARKER", "/var/lib/camxora-ops-alert/offhost.last")
)
RETENTION_DAYS = int(os.environ.get("BACKUP_REMOTE_RETENTION_DAYS", "14"))
AUTH_URL = "https://api.backblazeb2.com/b2api/v3/b2_authorize_account"

SOURCES = (
    ("musicapi", Path("/opt/camxora/backups/musicapi"), "sunoapi-*.dump"),
    ("platform", Path("/opt/camxora/backups/platform"), "camxora_platform-*.dump"),
)


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    for key in (
        "B2_BACKUP_BUCKET",
        "B2_BACKUP_BUCKET_ID",
        "B2_BACKUP_KEY_ID",
        "B2_BACKUP_APP_KEY",
    ):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def api(url: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", token)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def authorize(env: dict[str, str]) -> tuple[str, str, str]:
    import base64

    basic = base64.b64encode(
        f"{env['B2_BACKUP_KEY_ID']}:{env['B2_BACKUP_APP_KEY']}".encode()
    ).decode()
    req = urllib.request.Request(AUTH_URL, headers={"Authorization": f"Basic {basic}"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.load(response)
    return (
        data["apiInfo"]["storageApi"]["apiUrl"],
        data["authorizationToken"],
        data["accountId"],
    )


def list_remote(api_url: str, token: str, bucket_id: str, prefix: str) -> list[dict]:
    files: list[dict] = []
    start: str | None = None
    while True:
        payload = {"bucketId": bucket_id, "prefix": prefix, "maxFileCount": 1000}
        if start:
            payload["startFileName"] = start
        page = api(f"{api_url}/b2api/v3/b2_list_file_names", token, payload)
        batch = page.get("files", [])
        files.extend(batch)
        start = page.get("nextFileName")
        if not start:
            return files


def upload(api_url: str, token: str, bucket_id: str, name: str, path: Path) -> dict:
    slot = api(f"{api_url}/b2api/v3/b2_get_upload_url", token, {"bucketId": bucket_id})
    data = path.read_bytes()
    sha1 = hashlib.sha1(data).hexdigest()
    req = urllib.request.Request(slot["uploadUrl"], data=data, method="POST")
    req.add_header("Authorization", slot["authorizationToken"])
    req.add_header("X-Bz-File-Name", name)
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("X-Bz-Content-Sha1", sha1)
    req.add_header("X-Bz-Server-Side-Encryption", "AES256")
    with urllib.request.urlopen(req, timeout=1800) as response:
        return json.load(response)


def newest(pattern: str, directory: Path) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = load_env()
    missing = [
        k
        for k in ("B2_BACKUP_BUCKET", "B2_BACKUP_BUCKET_ID", "B2_BACKUP_KEY_ID", "B2_BACKUP_APP_KEY")
        if not env.get(k)
    ]
    if missing:
        print(f"offhost: missing {', '.join(missing)} in {ENV_FILE}", file=sys.stderr)
        return 1

    api_url, token, _account = authorize(env)
    bucket_id = env["B2_BACKUP_BUCKET_ID"]
    now = time.time()
    changed = 0

    for prefix, directory, pattern in SOURCES:
        path = newest(pattern, directory)
        if path is None:
            print(f"offhost: no dump matching {pattern} in {directory}", file=sys.stderr)
            return 1
        name = f"{prefix}/{path.name}"
        remote = list_remote(api_url, token, bucket_id, f"{prefix}/")
        same = next((f for f in remote if f["fileName"] == name and f["contentLength"] == path.stat().st_size), None)
        print(f"offhost: {name} ({path.stat().st_size / 1048576:.0f} MB) "
              f"{'already present' if same else 'uploading'}")
        if not same:
            if args.dry_run:
                print("  (dry run, not uploaded)")
            else:
                result = upload(api_url, token, bucket_id, name, path)
                print(f"  uploaded {result['fileId']} at {result['uploadTimestamp']}")
                changed += 1

        if args.dry_run:
            continue
        cutoff_ms = int((now - RETENTION_DAYS * 86400) * 1000)
        for f in remote:
            if f["fileName"] == name:
                continue
            if f["uploadTimestamp"] < cutoff_ms:
                api(
                    f"{api_url}/b2api/v3/b2_delete_file_version",
                    token,
                    {"fileName": f["fileName"], "fileId": f["fileId"]},
                )
                print(f"  pruned {f['fileName']}")

    if args.dry_run:
        print("offhost: dry run complete")
        return 0

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(str(int(now)), encoding="utf-8")
    print(f"offhost: done ({changed} uploaded), marker {MARKER}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"offhost: B2 error {exc.code}: {exc.read().decode(errors='replace')[:300]}", file=sys.stderr)
        raise SystemExit(1)
