#!/usr/bin/env python3
"""Verify deployed source against ``.deploy-manifest.json`` and prune stale files.

Runs on the VPS right after the source archive is extracted, and locally to
self-check an archive before upload. Stdlib only: the server may not have the
deploy virtualenv on PATH.

Modes
-----
Verify a tree::

    python3 verify_release_manifest.py --repo /opt/camxora/repo \
        --manifest /opt/camxora/repo/.deploy-manifest.json \
        [--scope platform_api] [--prev-manifest /opt/camxora/repo.bak.X/.deploy-manifest.json]

Verify an archive::

    python3 verify_release_manifest.py --archive /tmp/camxora-src.tar.gz

Exit codes: 0 = verified, 1 = mismatch/missing file, 2 = bad invocation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from typing import Iterable, Sequence

MANIFEST_NAME = ".deploy-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _in_scope(rel: str, scope: Sequence[str]) -> bool:
    if not scope:
        return True
    return rel.split("/", 1)[0] in scope


def verify_tree(
    repo: Path,
    manifest: dict,
    *,
    scope: Sequence[str] = (),
    limit: int = 25,
) -> list[str]:
    """Return missing/mismatched files under ``repo``."""
    problems: list[str] = []
    for rel, digest in sorted(manifest.get("files", {}).items()):
        if not _in_scope(rel, scope):
            continue
        path = repo / rel
        if not path.is_file():
            problems.append(f"missing deployed file: {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"deployed file does not match the deploy source: {rel}")
        if len(problems) >= limit:
            problems.append("... (truncated)")
            break
    return problems


def stale_paths(previous: dict, current: dict, *, scope: Sequence[str] = ()) -> list[str]:
    prev = set(previous.get("files", {}))
    cur = set(current.get("files", {}))
    return sorted(rel for rel in prev - cur if _in_scope(rel, scope))


def prune_tree(repo: Path, relative_paths: Iterable[str]) -> list[str]:
    removed: list[str] = []
    touched: set[Path] = set()
    for rel in relative_paths:
        path = repo / rel
        if not path.is_file():
            continue
        path.unlink()
        removed.append(rel)
        touched.add(path.parent)
    for directory in sorted(touched, key=lambda p: len(p.parts), reverse=True):
        current = directory
        while current != repo and current.is_dir():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
    return removed


def _manifest_from_archive(archive: Path) -> dict:
    with tarfile.open(archive, "r:gz") as tar:
        handle = tar.extractfile(MANIFEST_NAME)
        if handle is None:
            raise SystemExit(f"{archive} has no {MANIFEST_NAME}; rebuild the source bundle")
        return json.loads(handle.read().decode("utf-8"))


def verify_archive(archive: Path) -> list[str]:
    manifest = _manifest_from_archive(archive)
    expected: dict[str, str] = manifest.get("files", {})
    problems: list[str] = []
    seen: set[str] = set()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if not member.isfile() or member.name == MANIFEST_NAME:
                continue
            seen.add(member.name)
            if member.name not in expected:
                problems.append(f"unexpected file in archive: {member.name}")
                continue
            handle = tar.extractfile(member)
            if handle is None:  # pragma: no cover - defensive
                problems.append(f"unreadable file in archive: {member.name}")
                continue
            if hashlib.sha256(handle.read()).hexdigest() != expected[member.name]:
                problems.append(f"hash mismatch in archive: {member.name}")
    problems.extend(f"missing file in archive: {rel}" for rel in sorted(set(expected) - seen))
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="Deployed checkout root")
    parser.add_argument("--manifest", help="Manifest path (default: <repo>/.deploy-manifest.json)")
    parser.add_argument("--prev-manifest", help="Previous deploy's manifest, to prune stale files")
    parser.add_argument("--scope", nargs="*", default=[], help="Only these top-level dirs")
    parser.add_argument("--archive", help="Verify an archive instead of a tree")
    args = parser.parse_args(argv)

    if args.archive:
        problems = verify_archive(Path(args.archive))
        if problems:
            print("ARCHIVE_VERIFY_FAILED")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("ARCHIVE_VERIFY_OK")
        return 0

    if not args.repo:
        parser.error("--repo or --archive is required")

    repo = Path(args.repo)
    manifest_path = Path(args.manifest) if args.manifest else repo / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"MANIFEST_MISSING {manifest_path}")
        return 1
    manifest = load_manifest(manifest_path)
    scope = tuple(args.scope)

    problems = verify_tree(repo, manifest, scope=scope)
    if problems:
        print("DEPLOY_VERIFY_FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"DEPLOY_VERIFY_OK commit={manifest.get('commit', '?')[:8]} files={manifest.get('file_count')}")

    if args.prev_manifest:
        prev_path = Path(args.prev_manifest)
        if prev_path.is_file():
            removed = prune_tree(repo, stale_paths(load_manifest(prev_path), manifest, scope=scope))
            if removed:
                print(f"PRUNED_STALE_FILES {len(removed)}")
                for rel in removed:
                    print(f"  - {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
