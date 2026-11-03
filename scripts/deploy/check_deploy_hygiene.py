#!/usr/bin/env python3
"""Block deploy scripts that write source straight into the production checkout.

Background: production used to be whatever `tar -xzf` / `sftp.put` dropped into
`/opt/camxora/repo`. Dozens of one-shot ``*production*.py`` scripts still do
that, so any agent could resurrect one and silently revert newer code. New
deploys must go through the verified-source pipeline instead:

    build_source_bundle()  (packages one commit + .deploy-manifest.json)
    enforce_deploy_gate()  (commit must be merged to origin/main)

Usage::

    python scripts/deploy/check_deploy_hygiene.py                    # report
    python scripts/deploy/check_deploy_hygiene.py --strict           # fail on any
    python scripts/deploy/check_deploy_hygiene.py --changed-only BASE

``--changed-only`` is what CI runs: it fails only for scripts added/modified by
the PR, so pre-existing one-shot hotfix scripts do not freeze the repo while
they are retired.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "scripts" / "deploy"
REMOTE_REPO = "/opt/camxora/repo"

# Paths inside the checkout that are runtime state, not deployed source.
RUNTIME_MARKERS = (
    "/.env",
    "/.deployed.json",
    "/.deploy-manifest",
    "/.deploy.lock",
    "/uploads/",
    "/dist/",
    "/.next/",
    "/image_output_cache/",
    "/marketplace_storage/",
    "/platform_api/.venv/",
    "/node_modules/",
)

VERIFIED_MARKERS = (
    "build_source_bundle(",
    "build_source_tarball(",
    "enforce_deploy_gate(",
)

# Pre-existing one-shot scripts that still patch the checkout directly. They are
# tolerated in --strict (so the check stays actionable) but never in
# --changed-only: editing one of these must go through the verified pipeline.
KNOWN_LEGACY_UNVERIFIED: dict[str, str] = {
    "_remote_patch_playlist_add.py": "one-shot 2026-08 playlist patch, already applied",
    "hotfix_api_v2_url_prefix_sandbox.py": "sandbox-only one-shot URL prefix patch",
    "hotfix_ios_hls_playback_production.py": "one-shot 2026-09 iOS playback patch, already applied",
    "hotfix_package_plaintext_lock_production.py": "one-shot packaging patch, already applied",
    "hotfix_package_plaintext_lock_sandbox.py": "sandbox-only packaging patch, already applied",
}

# Human-readable reasons, matched per line. Keep these narrow: only *writes*,
# never reads (many ops scripts legitimately inspect the checkout).
WRITE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\bsftp\.put\([^\n]*" + re.escape(REMOTE_REPO), re.I),
        "uploads a file into the production checkout with sftp.put",
    ),
    (
        re.compile(r"\bsftp\.file\(\s*[\"']" + re.escape(REMOTE_REPO) + r"[^\"']*[\"']\s*,\s*[\"'][wa]"),
        "opens a production checkout file for writing with sftp.file",
    ),
    (
        re.compile(r"\btar\s+-x[^\n]*" + re.escape(REMOTE_REPO), re.I),
        "extracts a tarball into the production checkout",
    ),
    (
        re.compile(r"\b(?:cp|mv|install)\s+[^\n]*\s" + re.escape(REMOTE_REPO) + r"/", re.I),
        "copies/moves a file into the production checkout",
    ),
    (
        re.compile(r"\b(?:cat|tee)\s+[^\n]*>\s*" + re.escape(REMOTE_REPO) + r"/", re.I),
        "writes a file into the production checkout with a shell redirect",
    ),
    (
        re.compile(
            r"\bopen\(\s*[\"']" + re.escape(REMOTE_REPO) + r"[^\"']*[\"']\s*,\s*[\"'][wa]"
        ),
        "opens a production checkout file for writing",
    ),
)

# pathlib writes span two statements (``p = Path(...)`` then ``p.write_text``),
# so they are matched against the whole file, not one line.
PATHLIB_WRITE = re.compile(
    r"\bPath\(\s*[\"']" + re.escape(REMOTE_REPO) + r"[^\"']*[\"']\s*\)"
    r"[\s\S]{0,240}?\.(?:write_text|write_bytes|unlink|rename|replace)\("
)

# `cd /opt/camxora/repo` followed by an extract, in the same script.
CD_THEN_EXTRACT = re.compile(
    r"cd\s+" + re.escape(REMOTE_REPO) + r"[\s\S]{0,400}?\btar\s+-x", re.I
)


@dataclass(frozen=True)
class Finding:
    path: Path
    reason: str
    line: int
    verified: bool


def _is_runtime_path(line: str) -> bool:
    return any(marker in line for marker in RUNTIME_MARKERS)


def is_verified_source(text: str) -> bool:
    return any(marker in text for marker in VERIFIED_MARKERS)


def scan_text(path: Path, text: str) -> list[Finding]:
    """Return write findings for one script (empty when it writes no source)."""
    verified = is_verified_source(text)
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if REMOTE_REPO not in line or _is_runtime_path(line):
            continue
        for pattern, reason in WRITE_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(path, reason, lineno, verified))
                break
    if CD_THEN_EXTRACT.search(text):
        findings.append(
            Finding(path, "extracts a tarball in-place inside the production checkout", 0, verified)
        )
    for match in PATHLIB_WRITE.finditer(text):
        snippet = match.group(0)
        if _is_runtime_path(snippet):
            continue
        line = text.count("\n", 0, match.start()) + 1
        findings.append(
            Finding(path, "edits a production checkout file with pathlib", line, verified)
        )
    return findings


def scan_paths(paths: Iterable[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_text(path, text))
    return findings


def default_targets() -> list[Path]:
    """Deploy scripts + remote shell scripts (skip tests and this checker)."""
    targets: list[Path] = []
    for pattern in ("*.py", "*.sh"):
        for path in DEPLOY_DIR.glob(pattern):
            if path.name.startswith("test_") or path.name == Path(__file__).name:
                continue
            targets.append(path)
    return targets


def changed_targets(base: str) -> list[Path]:
    """Deploy scripts modified since ``base`` (git diff, ACMR)."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"git diff failed: {proc.stderr.strip()}")
    changed = []
    for rel in proc.stdout.splitlines():
        rel = rel.strip()
        if not rel.startswith("scripts/deploy/"):
            continue
        path = REPO_ROOT / rel
        if path.suffix not in {".py", ".sh"} or not path.is_file():
            continue
        if path.name.startswith("test_") or path.name == Path(__file__).name:
            continue
        changed.append(path)
    return changed


def render(findings: Sequence[Finding], *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                [
                    {
                        "path": f.path.relative_to(REPO_ROOT).as_posix(),
                        "line": f.line,
                        "reason": f.reason,
                        "verified": f.verified,
                    }
                    for f in findings
                ],
                indent=2,
            )
        )
        return
    for finding in findings:
        where = f"{finding.path.relative_to(REPO_ROOT).as_posix()}:{finding.line}"
        state = "verified" if finding.verified else "UNVERIFIED"
        print(f"{state:10} {where}  {finding.reason}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail on every unverified writer")
    parser.add_argument(
        "--changed-only",
        metavar="BASE",
        help="only inspect deploy scripts changed since BASE (CI mode)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    targets = changed_targets(args.changed_only) if args.changed_only else default_targets()
    if not targets:
        print("deploy-hygiene: no deploy scripts to check")
        return 0

    findings = scan_paths(targets)
    unverified = [f for f in findings if not f.verified]
    allowlisted = (
        []
        if args.changed_only
        else [f for f in unverified if f.path.name in KNOWN_LEGACY_UNVERIFIED]
    )
    blocking = [f for f in unverified if f not in allowlisted]
    render(findings, as_json=args.json)

    if not findings:
        print(f"deploy-hygiene: {len(targets)} script(s) checked, no direct source writes")
        return 0

    verified = [f for f in findings if f.verified]
    print(
        f"deploy-hygiene: {len(verified)} verified source write(s), "
        f"{len(unverified)} unverified ({len(allowlisted)} known legacy)"
    )
    for finding in allowlisted:
        print(
            f"  legacy: {finding.path.name} — "
            f"{KNOWN_LEGACY_UNVERIFIED[finding.path.name]}"
        )
    if args.strict and blocking:
        print(
            "\nRefusing: these scripts write source into the production checkout "
            "without the verified-source pipeline.\n"
            "Route them through build_source_bundle()/enforce_deploy_gate(), or run "
            "them as DB/ops-only scripts that never touch deployed files."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
