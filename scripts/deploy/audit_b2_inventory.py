#!/usr/bin/env python3
"""Read-only Backblaze B2 inventory across ALL buckets in the account.

Runs on the production host (where boto3 + the encrypted credentials live).
Prints a compact JSON report:

  - every bucket with total objects / bytes
  - per-bucket bytes + objects by artifact kind
  - hidden (overwritten) versions + incomplete multipart uploads
  - for the DB-configured streaming bucket: full detail
    (by prefix, largest, content duplicates by ETag, unreferenced vs DB)

Nothing is written to B2. Safe to run anytime.

Env knobs (passed through to the remote host):
  B2_AUDIT_BUCKETS        comma-separated bucket names to probe
  B2_AUDIT_SKIP_VERSIONS  "1" to skip the (slower) version/multipart scan
  B2_AUDIT_FULL           "1" to include per-prefix / duplicate / orphan detail
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r'''
set +e
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
import asyncio
import collections
import heapq
import json
import os
import sys

import asyncpg

SUNO_KEY_COLS = [
    "b2_storage_key_ok", "b2_storage_key_alt",
    "packaged_storage_key_ok", "packaged_storage_key_ok_b",
    "packaged_storage_key_alt", "packaged_storage_key_alt_b",
    "encrypted_original_key_ok", "encrypted_original_key_alt",
    "b2_wav_storage_key_ok", "b2_wav_storage_key_alt",
    "b2_lrc_storage_key_ok", "b2_lrc_storage_key_alt",
    "b2_srt_storage_key_ok", "b2_srt_storage_key_alt",
]
SUNO_HLS_COLS = ["hls_storage_prefix_ok", "hls_storage_prefix_alt"]
TRACK_KEY_COLS = [
    "storage_key", "packaged_storage_key", "packaged_storage_key_b",
    "encrypted_original_storage_key",
]
TRACK_HLS_COLS = ["hls_storage_prefix"]


def classify(key: str) -> str:
    k = key.lower()
    if ".hls/" in k:
        if k.endswith(".m3u8"):
            return "hls_m3u8"
        if k.endswith(".ts"):
            return "hls_ts"
        return "hls_other"
    if k.endswith(".b.cxa"):
        return "pkg_b_cxa"
    if k.endswith(".cxa"):
        return "pkg_a_cxa"
    if k.endswith(".cxo"):
        return "enc_original_cxo"
    if k.endswith(".mp3"):
        return "mp3"
    if k.endswith(".wav"):
        return "wav"
    if k.endswith(".lrc"):
        return "lrc"
    if k.endswith(".srt"):
        return "srt"
    if k.endswith(".json"):
        return "json"
    if k.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return "image"
    return "other"


async def load_referenced(pool):
    exact: set[str] = set()
    hls: set[str] = set()

    cols = {
        r["column_name"]
        for r in await pool.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'suno_tasks'"
        )
    }
    want = [c for c in (SUNO_KEY_COLS + SUNO_HLS_COLS) if c in cols]
    if want:
        rows = await pool.fetch(f"SELECT {', '.join(want)} FROM suno_tasks")
        for r in rows:
            for c in want:
                v = r[c]
                if v is None:
                    continue
                v = str(v).strip()
                if not v:
                    continue
                (hls if c in SUNO_HLS_COLS else exact).add(v)

    tcols = {
        r["column_name"]
        for r in await pool.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'stream_tracks'"
        )
    }
    twant = [c for c in (TRACK_KEY_COLS + TRACK_HLS_COLS) if c in tcols]
    if twant:
        rows = await pool.fetch(f"SELECT {', '.join(twant)} FROM stream_tracks")
        for r in rows:
            for c in twant:
                v = r[c]
                if v is None:
                    continue
                v = str(v).strip()
                if not v:
                    continue
                (hls if c in TRACK_HLS_COLS else exact).add(v)
    return exact, hls


def top_items(d, n=20):
    items = sorted(d.items(), key=lambda kv: kv[1][1], reverse=True)[:n]
    return [
        {"name": k, "objects": v[0], "bytes": v[1], "gb": round(v[1] / 1024**3, 3)}
        for k, v in items
    ]


def enumerate_bucket(s3, name, *, detail, orphans, exact, hls):
    total_count = 0
    total_bytes = 0
    kind_stats = collections.defaultdict(lambda: [0, 0])
    prefix_stats = collections.defaultdict(lambda: [0, 0])
    unreferenced = collections.defaultdict(lambda: [0, 0])
    etag_groups = {}
    largest = []

    token = None
    pages = 0
    while True:
        kwargs = {"Bucket": name, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for item in resp.get("Contents") or []:
            key = item["Key"]
            size = int(item.get("Size") or 0)
            total_count += 1
            total_bytes += size

            kind = classify(key)
            kind_stats[kind][0] += 1
            kind_stats[kind][1] += size

            if detail:
                pref = key.split("/", 1)[0] if "/" in key else "(root)"
                prefix_stats[pref][0] += 1
                prefix_stats[pref][1] += size

                if orphans:
                    if key in exact:
                        pass
                    else:
                        parent = key.rsplit("/", 1)[0] if "/" in key else ""
                        if parent in hls:
                            pass
                        else:
                            unreferenced[kind][0] += 1
                            unreferenced[kind][1] += size

                etag = str(item.get("ETag") or "").strip('"')
                if etag and size > 0 and "-" not in etag:
                    g = etag_groups.get((etag, size))
                    if g is None:
                        etag_groups[(etag, size)] = [1, key]
                    else:
                        g[0] += 1

                if len(largest) < 30:
                    heapq.heappush(largest, (size, key))
                elif size > largest[0][0]:
                    heapq.heapreplace(largest, (size, key))

        pages += 1
        if pages % 100 == 0:
            print(f"  [{name}] pages={pages} objects={total_count}", file=sys.stderr, flush=True)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")

    out = {
        "bucket": name,
        "total_objects": total_count,
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / 1024**3, 2),
        "by_kind": top_items(kind_stats, n=20),
    }

    if detail:
        dup_groups = [(v[0], size, v[1]) for (_e, size), v in etag_groups.items() if v[0] > 1]
        dup_groups.sort(key=lambda t: (t[0] - 1) * t[1], reverse=True)
        out.update({
            "by_prefix": top_items(prefix_stats, n=30),
            "largest": [
                {"key": k, "mb": round(s / 1024**2, 2)}
                for s, k in sorted(largest, reverse=True)[:20]
            ],
            "duplicate_etag_groups": len(dup_groups),
            "duplicate_objects": sum(c for c, _s, _k in dup_groups),
            "duplicate_redundant_bytes": sum((c - 1) * s for c, s, _k in dup_groups),
            "duplicate_redundant_gb": round(
                sum((c - 1) * s for c, s, _k in dup_groups) / 1024**3, 2
            ),
            "duplicate_examples": [
                {"copies": c, "mb": round(s / 1024**2, 2), "key": k}
                for c, s, k in dup_groups[:15]
            ],
            "unreferenced_by_kind": top_items(unreferenced, n=20),
            "unreferenced_total_objects": sum(v[0] for v in unreferenced.values()),
            "unreferenced_total_gb": round(
                sum(v[1] for v in unreferenced.values()) / 1024**3, 2
            ),
        })
    return out


def enumerate_versions(s3, name):
    """Count ALL versions (incl. hidden, overwritten ones) + delete markers.

    B2 keeps every overwritten object as a hidden version that is still billed
    but never shown by list_objects_v2. This is the #1 cause of "my bucket is
    way bigger than what I see".
    """
    total_versions = 0
    total_bytes = 0
    latest_versions = 0
    latest_bytes = 0
    hidden_versions = 0
    hidden_bytes = 0
    delete_markers = 0
    kind_all = collections.defaultdict(lambda: [0, 0])
    kind_hidden = collections.defaultdict(lambda: [0, 0])

    key_marker = None
    version_marker = None
    pages = 0
    while True:
        kwargs = {"Bucket": name, "MaxKeys": 1000}
        if key_marker:
            kwargs["KeyMarker"] = key_marker
            kwargs["VersionIdMarker"] = version_marker
        resp = s3.list_object_versions(**kwargs)
        for item in resp.get("Versions") or []:
            key = item["Key"]
            size = int(item.get("Size") or 0)
            total_versions += 1
            total_bytes += size
            kind = classify(key)
            kind_all[kind][0] += 1
            kind_all[kind][1] += size
            if item.get("IsLatest"):
                latest_versions += 1
                latest_bytes += size
            else:
                hidden_versions += 1
                hidden_bytes += size
                kind_hidden[kind][0] += 1
                kind_hidden[kind][1] += size
        delete_markers += len(resp.get("DeleteMarkers") or [])
        pages += 1
        if pages % 100 == 0:
            print(
                f"  [versions {name}] pages={pages} versions={total_versions}",
                file=sys.stderr,
                flush=True,
            )
        if not resp.get("IsTruncated"):
            break
        key_marker = resp.get("NextKeyMarker")
        version_marker = resp.get("NextVersionIdMarker")
        if not key_marker:
            break

    return {
        "bucket": name,
        "all_versions": total_versions,
        "all_versions_bytes": total_bytes,
        "all_versions_gb": round(total_bytes / 1024**3, 2),
        "latest_versions": latest_versions,
        "latest_bytes": latest_bytes,
        "latest_gb": round(latest_bytes / 1024**3, 2),
        "hidden_versions": hidden_versions,
        "hidden_bytes": hidden_bytes,
        "hidden_gb": round(hidden_bytes / 1024**3, 2),
        "delete_markers": delete_markers,
        "hidden_by_kind": top_items(kind_hidden, n=20),
    }


def enumerate_multipart(s3, name):
    """Incomplete multipart uploads are billed by B2 but invisible in listings."""
    total = 0
    try:
        key_marker = None
        upload_marker = None
        while True:
            kwargs = {"Bucket": name, "MaxUploads": 1000}
            if key_marker:
                kwargs["KeyMarker"] = key_marker
                kwargs["UploadIdMarker"] = upload_marker
            resp = s3.list_multipart_uploads(**kwargs)
            total += len(resp.get("Uploads") or [])
            if not resp.get("IsTruncated"):
                break
            key_marker = resp.get("NextKeyMarker")
            upload_marker = resp.get("NextUploadIdMarker")
            if not key_marker:
                break
    except Exception as exc:  # noqa: BLE001
        return {"bucket": name, "error": f"{type(exc).__name__}: {exc}"}
    return {"bucket": name, "incomplete_multipart_uploads": total}


async def main():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)

    from platform_api.services.streaming_config_service import resolve_streaming_storage_config
    cfg = await resolve_streaming_storage_config(pool)
    if not cfg.configured:
        print(json.dumps({"error": "storage not configured"}))
        return

    exact, hls = await load_referenced(pool)
    await pool.close()

    import boto3
    from botocore.config import Config

    audit_key_id = os.environ.get("B2_AUDIT_KEY_ID", "").strip() or cfg.key_id
    audit_secret = os.environ.get("B2_AUDIT_APPLICATION_KEY", "").strip() or cfg.application_key

    def make_client(region: str):
        return boto3.client(
            "s3",
            endpoint_url=f"https://s3.{region}.backblazeb2.com",
            aws_access_key_id=audit_key_id,
            aws_secret_access_key=audit_secret,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 10, "mode": "standard"},
            ),
        )

    clients = {r: make_client(r) for r in (cfg.region, "us-east-005", "us-west-004")}

    skip_versions = os.environ.get("B2_AUDIT_SKIP_VERSIONS") == "1"
    full_detail = os.environ.get("B2_AUDIT_FULL") == "1"

    # Prefer explicit bucket list; otherwise probe the defaults. With an
    # account-level key we can auto-discover every bucket via ListBuckets.
    candidates = [
        b.strip()
        for b in os.environ.get("B2_AUDIT_BUCKETS", "").split(",")
        if b.strip()
    ]
    discovered: list[str] = []
    if not candidates:
        for client in clients.values():
            try:
                resp = client.list_buckets()
            except Exception:  # noqa: BLE001
                continue
            discovered = [b["Name"] for b in resp.get("Buckets") or []]
            break
    if not candidates:
        candidates = discovered or [
            "productions-camxora-song",
            "camxora-media",
            "camroxa-song-storage",
        ]

    report = {
        "endpoint": cfg.endpoint,
        "db_configured_bucket": cfg.bucket,
        "credential": "account-level" if audit_key_id != cfg.key_id else "bucket-scoped (db)",
        "discovered_buckets": discovered,
        "candidate_buckets": candidates,
        "db_referenced_keys": len(exact),
        "db_referenced_hls_prefixes": len(hls),
        "buckets": [],
    }
    grand_bytes = 0
    grand_objects = 0
    grand_all_bytes = 0
    for name in candidates:
        info = None
        last_exc = None
        for region, client in clients.items():
            try:
                info = enumerate_bucket(
                    client,
                    name,
                    detail=full_detail,
                    orphans=(full_detail and name == cfg.bucket),
                    exact=exact,
                    hls=hls,
                )
                info["region"] = region
                if not skip_versions:
                    try:
                        info["versions"] = enumerate_versions(client, name)
                    except Exception as exc:  # noqa: BLE001
                        info["versions"] = {"error": f"{type(exc).__name__}: {exc}"}
                    try:
                        info["multipart"] = enumerate_multipart(client, name)
                    except Exception as exc:  # noqa: BLE001
                        info["multipart"] = {"error": f"{type(exc).__name__}: {exc}"}
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                info = None
        if info is None:
            report["buckets"].append(
                {"bucket": name, "error": f"{type(last_exc).__name__}: {last_exc}"}
            )
            continue
        report["buckets"].append(info)
        grand_bytes += info["total_bytes"]
        grand_objects += info["total_objects"]
        grand_all_bytes += (info.get("versions") or {}).get("all_versions_bytes", 0)
    report["grand_total_bytes"] = grand_bytes
    report["grand_total_gb"] = round(grand_bytes / 1024**3, 2)
    report["grand_total_objects"] = grand_objects
    report["grand_total_all_versions_bytes"] = grand_all_bytes
    report["grand_total_all_versions_gb"] = round(grand_all_bytes / 1024**3, 2)

    print("B2_INVENTORY_JSON_START")
    print(json.dumps(report, indent=2))
    print("B2_INVENTORY_JSON_END")


asyncio.run(main())
PYEOF
echo B2_INVENTORY_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        passthrough = {
            "B2_AUDIT_BUCKETS": None,
            "B2_AUDIT_SKIP_VERSIONS": None,
            "B2_AUDIT_FULL": None,
            # Optional account-level key (else the DB-configured scoped key is used).
            "B2_AUDIT_KEY_ID": "B2_AUDIT_KEY_ID",
            "B2_AUDIT_APPLICATION_KEY": "B2_AUDIT_APPLICATION_KEY",
        }
        exports = ""
        for key, secret_key in passthrough.items():
            val = os.environ.get(key) or (secrets.get(secret_key) if secret_key else None)
            if val:
                exports += f"export {key}={shlex.quote(val)}\n"
        _, stdout, stderr = client.exec_command(exports + REMOTE_CMD, get_pty=False, timeout=7200)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
