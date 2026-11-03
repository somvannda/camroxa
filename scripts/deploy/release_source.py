#!/usr/bin/env python3
"""Build a deployable source archive from an immutable git commit.

Why this exists
---------------
Every past "the deploy reverted my fix" incident had the same shape: the
deploy packaged **whatever files happened to be in the working tree of the
worktree the script was launched from**, then `tar -xzf`'d them over
`/opt/camxora/repo`. That means:

* deploying from an old branch/worktree ships old code and silently reverts
  newer commits,
* files that only existed on the server (a late hotfix) vanish,
* a file deleted upstream stays on the server forever (tar never deletes),
  and can shadow the new module,
* nobody can answer "which commit is live?" afterwards.

This module packages the tree of **one commit** with `git archive` (so only
committed content ships, exactly as recorded in git), writes a
``.deploy-manifest.json`` of every shipped file (sha256), and lets the server
verify that what landed on disk is exactly that manifest.

The manifest is the contract: any file whose bytes differ, any file the
manifest expects but that is missing, fails the deploy. Files that the previous
deploy shipped but this one does not are pruned, so retired modules cannot
linger and shadow the new code.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_SOURCE_REF = "origin/main"
SOURCE_REF_ENV = "CAMXORA_DEPLOY_SOURCE_REF"
SOURCE_MODE_ENV = "CAMXORA_DEPLOY_SOURCE"
MANIFEST_NAME = ".deploy-manifest.json"
MANIFEST_SCHEMA = 1

# Never ship build output, local state, secrets or tests.
SKIP_NAMES = frozenset(
    {
        "node_modules",
        ".venv",
        "__pycache__",
        ".git",
        ".next",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".dbg",
        "uploads",
        "tests",
        ".env",
        "image_output_cache",
        "marketplace_storage",
    }
)

# Shipped with LF endings regardless of how a Windows checkout stores them.
TEXT_SUFFIXES = {
    ".py",
    ".sh",
    ".sql",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".yml",
    ".yaml",
    ".conf",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".css",
    ".scss",
    ".html",
    ".xml",
    ".svg",
    ".example",
}


class ReleaseSourceError(RuntimeError):
    """Raised when a deploy cannot be produced from an immutable source."""


@dataclass(frozen=True)
class SourceBundle:
    """A deployable archive plus the provenance needed to verify it later."""

    path: Path
    commit: str
    ref: str
    mode: str
    dirty: bool
    files: int
    manifest: dict

    @property
    def short(self) -> str:
        return self.commit[:8]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )


def resolve_source_ref(repo_root: Path, ref: str | None = None) -> str:
    """Return the ref a deploy should package, honouring the env override."""
    return (ref or os.environ.get(SOURCE_REF_ENV, "").strip()) or _default_source_ref(repo_root)


def resolve_source_commit(repo_root: Path, ref: str | None = None) -> str:
    """Resolve ``ref`` (default: env override, else origin/main, else HEAD)."""
    wanted = resolve_source_ref(repo_root, ref)
    proc = _git(repo_root, "rev-parse", "--verify", f"{wanted}^{{commit}}")
    if proc.returncode != 0:
        raise ReleaseSourceError(
            f"Cannot resolve deploy source '{wanted}' in {repo_root}. "
            "Fetch it first (git fetch origin) or pass a valid ref."
        )
    return proc.stdout.decode().strip()


def _default_source_ref(repo_root: Path) -> str:
    # Callers that must ship the tip of main pass DEFAULT_SOURCE_REF explicitly.
    # Defaulting to HEAD keeps sandbox/WIP deploys working while still packaging
    # committed content (never the working tree).
    return "HEAD"


def is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    if not ancestor or not descendant:
        return False
    return _git(repo_root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def commit_subject(repo_root: Path, commit: str) -> str:
    proc = _git(repo_root, "log", "-1", "--format=%s", commit)
    return proc.stdout.decode("utf-8", "replace").strip()


def commit_timestamp(repo_root: Path, commit: str) -> str:
    proc = _git(repo_root, "log", "-1", "--format=%cI", commit)
    return proc.stdout.decode().strip()


def repo_root_default() -> Path:
    return Path(__file__).resolve().parents[2]


def fetch_origin(repo_root: Path | None = None) -> tuple[bool, str]:
    """Refresh refs so ``origin/main`` is the tip, not a stale local copy."""
    root = repo_root or repo_root_default()
    proc = _git(root, "fetch", "--prune", "origin")
    if proc.returncode != 0:
        return False, proc.stderr.decode("utf-8", "replace").strip() or "git fetch failed"
    head = _git(root, "rev-parse", "--short", DEFAULT_SOURCE_REF)
    return True, head.stdout.decode().strip() or DEFAULT_SOURCE_REF


# ---------------------------------------------------------------------------
# Archive construction
# ---------------------------------------------------------------------------


def _archive_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES and b"\r\n" in data:
        return data.replace(b"\r\n", b"\n")
    return data


def _skipped(name: str) -> bool:
    name = name.replace("\\", "/")
    parts = Path(name).parts
    if any(part in SKIP_NAMES for part in parts):
        return True
    # Generated packaging metadata is tracked in git (despite *.egg-info/ in
    # .gitignore), and `pip install -e .` rewrites it right after extraction.
    # Shipping it would make every post-deploy verification fail on hashes that
    # the deploy itself changed.
    if any(part.endswith(".egg-info") for part in parts):
        return True
    return name.endswith((".pyc", ".pyo", ".log"))


def _manifest_doc(
    *,
    commit: str,
    ref: str,
    mode: str,
    dirty: bool,
    files: dict[str, str],
    repo_root: Path | None = None,
) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "commit": commit,
        "ref": ref,
        "mode": mode,
        "dirty": dirty,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "files": dict(sorted(files.items())),
    }


def build_archive_from_commit(
    repo_root: Path,
    commit: str,
    archive_path: Path,
    *,
    roots: Sequence[str],
    files: Sequence[str] = (),
    ref: str = "",
) -> dict:
    """Write an archive of exactly ``commit``'s ``roots``/``files`` + manifest.

    Only committed content is packaged, so untracked or deleted-but-checked-out
    files can never leak into a deploy.
    """
    spec = [*roots, *files]
    proc = _git(repo_root, "archive", "--format=tar", commit, "--", *spec)
    if proc.returncode != 0:
        raise ReleaseSourceError(
            f"git archive failed for {commit}: {proc.stderr.decode('utf-8', 'replace').strip()}"
        )

    hashes: dict[str, str] = {}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as src, tarfile.open(
        fileobj=buffer, mode="w:gz"
    ) as dst:
        for member in src:
            if not member.isfile():
                continue
            name = member.name.replace("\\", "/")
            if _skipped(name):
                continue
            handle = src.extractfile(member)
            if handle is None:  # pragma: no cover - defensive
                continue
            data = handle.read()
            if Path(name).suffix.lower() in TEXT_SUFFIXES and b"\r\n" in data:
                data = data.replace(b"\r\n", b"\n")
            member.size = len(data)
            member.mtime = int(time.time())
            dst.addfile(member, io.BytesIO(data))
            hashes[name] = hashlib.sha256(data).hexdigest()

        manifest = _manifest_doc(
            commit=commit,
            ref=ref,
            mode="commit",
            dirty=False,
            files=hashes,
            repo_root=repo_root,
        )
        _write_manifest_member(dst, manifest)

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(buffer.getvalue())
    return manifest


def build_archive_from_worktree(
    repo_root: Path,
    commit: str,
    archive_path: Path,
    *,
    roots: Sequence[str],
    files: Sequence[str] = (),
    ref: str = "",
) -> dict:
    """Escape hatch: package the working tree (uncommitted changes included)."""
    hashes: dict[str, str] = {}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as dst:
        for root in [*roots, *files]:
            src = repo_root / root
            if not src.exists():
                raise ReleaseSourceError(f"Missing deploy path: {src}")
            candidates: list[Path] = []
            if src.is_file():
                candidates = [src]
            else:
                for dirpath, dirnames, filenames in os.walk(src):
                    # Prune before descending so skipped trees are never walked.
                    dirnames[:] = sorted(
                        d
                        for d in dirnames
                        if d not in SKIP_NAMES and not d.endswith(".egg-info")
                    )
                    candidates.extend(
                        Path(dirpath) / filename for filename in sorted(filenames)
                    )
            for path in candidates:
                arcname = path.relative_to(repo_root).as_posix()
                if _skipped(arcname):
                    continue
                data = _archive_bytes(path)
                info = tarinfo_for(path, arcname, len(data))
                dst.addfile(info, io.BytesIO(data))
                hashes[arcname] = hashlib.sha256(data).hexdigest()

        manifest = _manifest_doc(
            commit=commit,
            ref=ref,
            mode="worktree",
            dirty=True,
            files=hashes,
            repo_root=repo_root,
        )
        _write_manifest_member(dst, manifest)

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(buffer.getvalue())
    return manifest


def _prune_dirnames(dirnames: list[str]) -> bool:
    dirnames[:] = sorted(d for d in dirnames if d not in SKIP_NAMES)
    return False


def tarinfo_for(path: Path, arcname: str, size: int) -> tarfile.TarInfo:
    """Build a deterministic tar member for ``path``."""
    stat = path.stat()
    info = tarfile.TarInfo(arcname)
    info.size = size
    info.mode = 0o644
    info.mtime = int(stat.st_mtime)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _write_manifest_member(tar: tarfile.TarFile, manifest: dict) -> None:
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    info = tarfile.TarInfo(MANIFEST_NAME)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = int(time.time())
    info.uid = 0
    info.gid = 0
    tar.addfile(info, io.BytesIO(payload))


# ---------------------------------------------------------------------------
# Verification (used by tests and by the server-side script)
# ---------------------------------------------------------------------------


def read_manifest(archive_path: Path) -> dict:
    with tarfile.open(archive_path, "r:gz") as tar:
        try:
            handle = tar.extractfile(MANIFEST_NAME)
        except KeyError as exc:  # pragma: no cover - defensive
            raise ReleaseSourceError(f"{archive_path} has no {MANIFEST_NAME}") from exc
        if handle is None:  # pragma: no cover - defensive
            raise ReleaseSourceError(f"{archive_path} has no readable {MANIFEST_NAME}")
        return json.loads(handle.read().decode("utf-8"))


def verify_archive(archive_path: Path) -> list[str]:
    """Return mismatches between an archive and the manifest inside it."""
    manifest = read_manifest(archive_path)
    expected: dict[str, str] = manifest.get("files", {})
    problems: list[str] = []
    seen: set[str] = set()
    with tarfile.open(archive_path, "r:gz") as tar:
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
            digest = hashlib.sha256(handle.read()).hexdigest()
            if digest != expected[member.name]:
                problems.append(f"hash mismatch in archive: {member.name}")
    for missing in sorted(set(expected) - seen):
        problems.append(f"missing file in archive: {missing}")
    return problems


def verify_tree(repo_root: Path, manifest: dict, *, scope: Sequence[str] = ()) -> list[str]:
    """Return missing/mismatched files on disk against ``manifest``."""
    expected: dict[str, str] = manifest.get("files", {})
    problems: list[str] = []
    for rel, digest in sorted(expected.items()):
        if scope and not _in_scope(rel, scope):
            continue
        path = repo_root / rel
        if not path.is_file():
            problems.append(f"missing deployed file: {rel}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            problems.append(f"deployed file does not match the deploy source: {rel}")
    return problems


def stale_paths(
    previous: dict,
    current: dict,
    *,
    scope: Sequence[str] = (),
) -> list[str]:
    """Files the previous deploy shipped that this one does not → must be removed."""
    prev = set(previous.get("files", {}))
    cur = set(current.get("files", {}))
    return sorted(
        rel
        for rel in prev - cur
        if not scope or _in_scope(rel, scope)
    )


def prune_tree(repo_root: Path, relative_paths: Iterable[str]) -> list[str]:
    """Delete stale files and any directory they leave empty. Returns removed paths."""
    removed: list[str] = []
    touched_dirs: set[Path] = set()
    for rel in relative_paths:
        path = repo_root / rel
        if not path.is_file():
            continue
        path.unlink()
        removed.append(rel)
        touched_dirs.add(path.parent)
    for directory in sorted(touched_dirs, key=lambda p: len(p.parts), reverse=True):
        current = directory
        while current != repo_root and current.is_dir():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
    return removed


def _in_scope(rel: str, scope: Sequence[str]) -> bool:
    if not scope:
        return True
    top = rel.split("/", 1)[0]
    return top in scope
