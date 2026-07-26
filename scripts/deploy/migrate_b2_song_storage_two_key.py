#!/usr/bin/env python3
"""Copy B2 objects using separate source + destination credentials.

Env:
  B2_SRC_KEY_ID / B2_SRC_APPLICATION_KEY / B2_SRC_BUCKET
  B2_DST_KEY_ID / B2_DST_APPLICATION_KEY / B2_DST_BUCKET
  B2_ENDPOINT (shared)
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def make_client(key_id: str, app_key: str, endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint.rstrip("/"),
        aws_access_key_id=key_id,
        aws_secret_access_key=app_key,
        config=Config(signature_version="s3v4", retries={"max_attempts": 8, "mode": "standard"}),
        region_name="us-east-005",
    )


def list_keys(s3, bucket: str) -> list[dict]:
    keys: list[dict] = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for item in resp.get("Contents") or []:
            keys.append({"Key": item["Key"], "Size": int(item.get("Size") or 0)})
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def transfer_one(
    src_s3,
    dst_s3,
    src_bucket: str,
    dst_bucket: str,
    key: str,
    work_dir: Path,
) -> tuple[str, str]:
    local = work_dir / key.replace("/", "__")
    try:
        local.parent.mkdir(parents=True, exist_ok=True)
        src_s3.download_file(src_bucket, key, str(local))
        dst_s3.upload_file(str(local), dst_bucket, key)
        return key, "ok"
    except ClientError as exc:
        return key, f"error:{exc}"
    except Exception as exc:  # noqa: BLE001
        return key, f"error:{exc}"
    finally:
        try:
            local.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Copy at most N objects (0=all)")
    args = parser.parse_args()

    endpoint = os.environ.get("B2_ENDPOINT", "https://s3.us-east-005.backblazeb2.com").strip()
    src_id = os.environ["B2_SRC_KEY_ID"].strip()
    src_key = os.environ["B2_SRC_APPLICATION_KEY"].strip()
    src_bucket = os.environ.get("B2_SRC_BUCKET", "camroxa-song-storage").strip()
    dst_id = os.environ["B2_DST_KEY_ID"].strip()
    dst_key = os.environ["B2_DST_APPLICATION_KEY"].strip()
    dst_bucket = os.environ.get("B2_DST_BUCKET", "productions-camxora-song").strip()

    src_s3 = make_client(src_id, src_key, endpoint)
    dst_s3 = make_client(dst_id, dst_key, endpoint)

    print(f"Listing source {src_bucket} …")
    src_keys = list_keys(src_s3, src_bucket)
    print(f"Source objects: {len(src_keys)} bytes={sum(k['Size'] for k in src_keys)}")

    print(f"Listing dest {dst_bucket} …")
    dst_existing = {k["Key"] for k in list_keys(dst_s3, dst_bucket)}
    print(f"Dest existing: {len(dst_existing)}")

    pending = [k for k in src_keys if k["Key"] not in dst_existing]
    if args.limit > 0:
        pending = pending[: args.limit]
    print(f"To copy: {len(pending)}")
    if args.dry_run:
        for item in pending[:15]:
            print(f"  would copy {item['Key']} ({item['Size']})")
        return 0

    ok = 0
    failed: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="b2mig_") as tmp:
        work = Path(tmp)
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = [
                pool.submit(transfer_one, src_s3, dst_s3, src_bucket, dst_bucket, item["Key"], work)
                for item in pending
            ]
            for i, fut in enumerate(as_completed(futs), start=1):
                key, status = fut.result()
                if status == "ok":
                    ok += 1
                else:
                    failed.append((key, status))
                if i % 25 == 0 or i == len(futs):
                    print(f"  progress {i}/{len(futs)} ok={ok} failed={len(failed)}")

    print(f"Done. copied={ok} failed={len(failed)}")
    for key, status in failed[:40]:
        print(f"  FAIL {key}: {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
