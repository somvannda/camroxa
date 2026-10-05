#!/usr/bin/env python3
"""Upload sample-pack ZIPs to existing sandbox catalog packs."""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
API_BASE = "https://api.sandbox.camxora.com/api/v1"
PREVIEW_DIR = REPO_ROOT / "camxora_python" / "resources" / "_ico_preview"
THUMBNAIL_ZIP = REPO_ROOT / ".dbg" / "newth-download" / "NewTH.zip"
PAYLOAD_PATH = Path(__file__).resolve().parent / "_upload_sample_packs_payload.json"


def _write_payload() -> None:
    payload = {
        "email": os.environ.get("CAMXORA_ADMIN_EMAIL", "duke@camxora.com"),
        "password": os.environ["CAMXORA_ADMIN_PASSWORD"],
    }
    PAYLOAD_PATH.write_text(json.dumps(payload), encoding="utf-8")


def _load_credentials() -> tuple[str, str]:
    if not PAYLOAD_PATH.exists():
        _write_payload()
    payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    return str(payload["email"]).strip().lower(), str(payload["password"])


def _https_json(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    body = None if data is None else json.dumps(data).encode()
    req_headers = {"Content-Type": "application/json", "X-Portal-Context": "admin"}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _login() -> str:
    email, password = _load_credentials()
    status, body = _https_json("POST", f"{API_BASE}/auth/login", data={"email": email, "password": password})
    print(f"login: {status}")
    if status != 200:
        raise SystemExit(f"Login failed: {body[:300]}")
    token = json.loads(body).get("access_token")
    if not token:
        raise SystemExit("Login response missing access_token")
    return str(token)


def _list_packs(token: str) -> list[dict]:
    status, body = _https_json("GET", f"{API_BASE}/admin/image-sample-packs", token=token)
    if status != 200:
        raise SystemExit(f"List packs failed ({status}): {body[:300]}")
    return list(json.loads(body).get("items") or [])


def _build_background_zip() -> bytes:
    images = sorted(PREVIEW_DIR.glob("*.png"))
    if not images:
        raise SystemExit(f"No preview PNGs found in {PREVIEW_DIR}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for image in images:
            zf.write(image, arcname=f"background/{image.name}")
    return buffer.getvalue()


def _build_thumbnail_zip() -> bytes:
    if THUMBNAIL_ZIP.is_file() and THUMBNAIL_ZIP.stat().st_size <= 9 * 1024 * 1024:
        return THUMBNAIL_ZIP.read_bytes()
    images = sorted(PREVIEW_DIR.glob("*.png"))
    if not images:
        raise SystemExit(f"No preview PNGs found for thumbnail fallback in {PREVIEW_DIR}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for image in images:
            zf.write(image, arcname=f"thumbnail/{image.name}")
    return buffer.getvalue()


def _multipart_upload(token: str, pack_id: str, *, category: str, name: str, zip_bytes: bytes) -> dict:
    boundary = "----camxoraSamplePackBoundary"
    body = io.BytesIO()
    parts = [
        ("file", "sample-pack.zip", "application/zip", zip_bytes),
        ("category", None, None, category.encode("utf-8")),
        ("name", None, None, name.encode("utf-8")),
        ("is_active", None, None, b"true"),
        ("sort_order", None, None, b"0"),
    ]
    for field, filename, content_type, content in parts:
        body.write(f"--{boundary}\r\n".encode())
        if filename:
            body.write(
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
            )
            body.write(f"Content-Type: {content_type}\r\n\r\n".encode())
        else:
            body.write(f'Content-Disposition: form-data; name="{field}"\r\n\r\n'.encode())
        body.write(content)
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        f"{API_BASE}/admin/image-sample-packs/{pack_id}/upload",
        data=body.getvalue(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Portal-Context": "admin",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            print(f"upload {category} ({name}): {resp.status} asset_count={payload.get('asset_count')}")
            return payload
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Upload failed for {pack_id} ({exc.code}): {detail[:400]}") from exc


def _run_probe() -> None:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote = (
        "sudo -u postgres psql -d camxora_platform -t -A -F'|' -c "
        "\"SELECT category, name, COALESCE(asset_count,0), COALESCE(storage_path,'') "
        "FROM image_sample_packs ORDER BY category, name;\""
    )
    _, stdout, stderr = client.exec_command(remote)
    print("\n=== post-upload probe ===")
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()


def main() -> int:
    token = _login()
    packs = _list_packs(token)
    if not packs:
        raise SystemExit("No image sample packs found on sandbox.")

    background_zip = _build_background_zip()
    thumbnail_zip = _build_thumbnail_zip()
    print(f"background zip bytes: {len(background_zip)}")
    print(f"thumbnail zip bytes: {len(thumbnail_zip)}")

    uploaded = 0
    for pack in packs:
        category = str(pack.get("category") or "").strip().lower()
        pack_id = str(pack.get("id") or "")
        name = str(pack.get("name") or "Sample Pack")
        if not pack_id:
            continue
        zip_bytes = thumbnail_zip if category == "thumbnail" else background_zip
        _multipart_upload(token, pack_id, category=category or "background", name=name, zip_bytes=zip_bytes)
        uploaded += 1

    print(f"uploaded {uploaded} pack(s)")
    _run_probe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
