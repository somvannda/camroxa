#!/usr/bin/env python3
"""Verify sandbox sample-pack assets and optional rotation probe."""

from __future__ import annotations

import json
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

API_BASE = "https://api.sandbox.camxora.com/api/v1"
PAYLOAD_PATH = Path(__file__).resolve().parent / "_upload_sample_packs_payload.json"

REMOTE_ROTATION_PROBE = textwrap.dedent(
    '''
import asyncio
import os
import sys

sys.path.insert(0, "/opt/camxora/repo")

from platform_api.services.image_sample_rotation import ImageKind, ImageSampleRotationService


async def main() -> None:
    import asyncpg

    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    try:
        service = ImageSampleRotationService(pool)
        for kind in (ImageKind.BACKGROUND, ImageKind.THUMBNAIL):
            candidates = await service.build_candidates({}, kind)
            print(f"{kind.value}_candidates", len(candidates))
            if candidates:
                print(f"{kind.value}_sample", candidates[0])
    finally:
        await pool.close()


asyncio.run(main())
'''
)


def _load_credentials() -> tuple[str, str]:
    payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    return str(payload["email"]).strip().lower(), str(payload["password"])


def _https_json(method: str, url: str, *, data: dict | None = None, token: str | None = None) -> tuple[int, str]:
    body = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json", "X-Portal-Context": "admin"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _probe_asset_counts() -> tuple[int, list[tuple[str, str, int, str]]]:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote = (
        "sudo -u postgres psql -d camxora_platform -t -A -F'|' -c "
        "\"SELECT category, name, COALESCE(asset_count,0), COALESCE(storage_path,'') "
        "FROM image_sample_packs ORDER BY category, name;\" && "
        "sudo -u postgres psql -d camxora_platform -t -A -c "
        "\"SELECT COUNT(1) FROM image_sample_pack_assets;\""
    )
    _, stdout, stderr = client.exec_command(remote)
    output = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    total_assets = 0
    packs: list[tuple[str, str, int, str]] = []
    for line in lines:
        if "|" in line:
            category, name, count_raw, storage_path = line.split("|", 3)
            packs.append((category, name, int(count_raw or 0), storage_path))
        elif line.isdigit():
            total_assets = int(line)
    return total_assets, packs


def _probe_rotation() -> None:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote_script = "/tmp/camxora_sample_rotation_probe.py"
    sftp = client.open_sftp()
    with sftp.file(remote_script, "w") as remote_file:
        remote_file.write(REMOTE_ROTATION_PROBE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc "
        f"\"set -a && source /opt/camxora/repo/platform_api/.env && set +a && "
        f"PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {remote_script}\""
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    print("\n=== rotation probe ===")
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()


def main() -> int:
    if not PAYLOAD_PATH.exists():
        raise SystemExit(f"Missing payload file: {PAYLOAD_PATH}. Run upload_sample_packs_sandbox.py first.")

    email, password = _load_credentials()
    status, body = _https_json("POST", f"{API_BASE}/auth/login", data={"email": email, "password": password})
    print(f"login: {status}")
    if status != 200:
        print(body[:300])
        return 1

    status, body = _https_json("GET", f"{API_BASE}/admin/image-sample-packs", token=json.loads(body)["access_token"])
    print(f"admin packs: {status}")
    if status == 200:
        items = json.loads(body).get("items") or []
        for item in items:
            print(
                f"  {item.get('category')} | {item.get('name')} | assets={item.get('asset_count', 0)} | "
                f"path={item.get('storage_path') or '-'}"
            )

    total_assets, packs = _probe_asset_counts()
    print(f"\nDB asset rows: {total_assets}")
    for category, name, count, storage_path in packs:
        print(f"  {category} | {name} | asset_count={count} | {storage_path}")

    if total_assets <= 0:
        print("VERIFY_FAIL: no VPS sample-pack assets indexed")
        return 1

    _probe_rotation()
    print("VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
