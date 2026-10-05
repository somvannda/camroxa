#!/usr/bin/env python3
"""Pre/post deploy guards: clean worktree, deployable ref, deployed-SHA marker,
and runtime invariants.

Motivated by an incident where several agents deployed production from different
worktrees within the same hour — including one deploy whose source lived in no
commit — so nobody could answer "what is actually live?" or guarantee that a
sibling's fix had not been silently clobbered.

These guards run locally (git state) and over SSH (deployed marker + runtime
invariants) and are wired into the platform_api production deploy scripts.

Escape hatches (for genuine hotfixes) — set to ``1`` to opt out:

    CAMXORA_ALLOW_DIRTY_DEPLOY=1     allow an uncommitted worktree
    CAMXORA_ALLOW_UNMERGED_DEPLOY=1  allow a HEAD that is not tagged and not on the base ref
    CAMXORA_DEPLOY_BASE_REF=...      base ref to check ancestry against (default origin/main)
    CAMXORA_DEPLOY_ACTOR=...         name recorded as the deployer in the marker
"""

from __future__ import annotations

import getpass
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_REF = "origin/main"
DEFAULT_REMOTE_REPO = "/opt/camxora/repo"
MARKER_FILENAME = ".deployed.json"

ALLOW_DIRTY_ENV = "CAMXORA_ALLOW_DIRTY_DEPLOY"
ALLOW_UNMERGED_ENV = "CAMXORA_ALLOW_UNMERGED_DEPLOY"
BASE_REF_ENV = "CAMXORA_DEPLOY_BASE_REF"
ACTOR_ENV = "CAMXORA_DEPLOY_ACTOR"

GitRunner = Callable[..., Any]
CheckRunner = Callable[..., Any]


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-tested without a real repo)
# ---------------------------------------------------------------------------


def parse_porcelain(text: str) -> tuple[str, ...]:
    """Return the non-empty ``git status --porcelain`` entries."""
    return tuple(line for line in text.splitlines() if line.strip())


def parse_branch(text: str) -> str:
    """Normalise ``git rev-parse --abbrev-ref HEAD`` (``HEAD`` -> detached '')."""
    branch = text.strip()
    return "" if branch in {"", "HEAD"} else branch


def parse_tags(text: str) -> tuple[str, ...]:
    """Return tags pointing at HEAD in stable order."""
    return tuple(sorted(line.strip() for line in text.splitlines() if line.strip()))


# ---------------------------------------------------------------------------
# Git state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepoState:
    commit: str
    short: str
    branch: str
    tags: tuple[str, ...] = ()
    dirty_files: tuple[str, ...] = ()

    @property
    def dirty(self) -> bool:
        return bool(self.dirty_files)

    @property
    def tagged(self) -> bool:
        return bool(self.tags)


@dataclass(frozen=True)
class DeployGate:
    """Result of a passing pre-deploy gate."""

    state: RepoState
    base_ref: str
    merged: bool
    allow_dirty: bool = False
    allow_unmerged: bool = False


def _git(
    repo_root: Path,
    *args: str,
    runner: GitRunner | None = None,
) -> subprocess.CompletedProcess[str]:
    run = runner or subprocess.run
    return run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def collect_repo_state(
    repo_root: Path = REPO_ROOT,
    *,
    runner: GitRunner | None = None,
) -> RepoState:
    """Read commit/branch/tags/dirty state for ``repo_root``."""
    commit = _git(repo_root, "rev-parse", "HEAD", runner=runner).stdout.strip()
    short = _git(repo_root, "rev-parse", "--short", "HEAD", runner=runner).stdout.strip()
    branch = parse_branch(
        _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD", runner=runner).stdout
    )
    tags = parse_tags(_git(repo_root, "tag", "--points-at", "HEAD", runner=runner).stdout)
    dirty = parse_porcelain(
        _git(repo_root, "status", "--porcelain", runner=runner).stdout
    )
    return RepoState(
        commit=commit,
        short=short,
        branch=branch,
        tags=tags,
        dirty_files=dirty,
    )


def is_ancestor(
    repo_root: Path,
    ancestor: str,
    descendant: str,
    *,
    runner: GitRunner | None = None,
) -> bool:
    """True when ``ancestor`` is an ancestor of (or equal to) ``descendant``."""
    if not ancestor or not descendant:
        return False
    proc = _git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        runner=runner,
    )
    return getattr(proc, "returncode", 1) == 0


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def deploy_gate_violations(
    state: RepoState,
    *,
    is_merged: bool,
    allow_dirty: bool = False,
    allow_unmerged: bool = False,
) -> list[str]:
    """Return human-readable reasons the given state may not be deployed."""
    violations: list[str] = []
    if state.dirty and not allow_dirty:
        shown = ", ".join(state.dirty_files[:5])
        more = "" if len(state.dirty_files) <= 5 else f" (+{len(state.dirty_files) - 5} more)"
        violations.append(
            f"worktree has {len(state.dirty_files)} uncommitted change(s): {shown}{more}"
        )
    if not state.tagged and not is_merged and not allow_unmerged:
        violations.append(
            "HEAD is not tagged and is not merged to the base ref — commit/merge it "
            "(or tag a release) so what is live is reproducible"
        )
    return violations


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _env_base_ref() -> str:
    return os.environ.get(BASE_REF_ENV, "").strip() or DEFAULT_BASE_REF


def enforce_deploy_gate(
    repo_root: Path = REPO_ROOT,
    *,
    base_ref: str | None = None,
    allow_dirty: bool = False,
    allow_unmerged: bool = False,
    runner: GitRunner | None = None,
) -> DeployGate:
    """Validate this worktree can be deployed. Raises ``SystemExit`` otherwise."""
    base_ref = base_ref or _env_base_ref()
    allow_dirty = allow_dirty or _env_flag(ALLOW_DIRTY_ENV)
    allow_unmerged = allow_unmerged or _env_flag(ALLOW_UNMERGED_ENV)

    state = collect_repo_state(repo_root, runner=runner)
    merged = is_ancestor(repo_root, state.commit, base_ref, runner=runner)

    violations = deploy_gate_violations(
        state,
        is_merged=merged,
        allow_dirty=allow_dirty,
        allow_unmerged=allow_unmerged,
    )
    if violations:
        detail = "\n  - ".join(violations)
        raise SystemExit(
            "Refusing deploy — deploy guards failed:\n  - "
            + detail
            + "\n\nCommit/merge your work (or set CAMXORA_ALLOW_DIRTY_DEPLOY=1 / "
            "CAMXORA_ALLOW_UNMERGED_DEPLOY=1 for a deliberate hotfix)."
        )

    print(
        f"[deploy-guard] worktree clean; HEAD {state.short}"
        f"{' (' + state.tags[0] + ')' if state.tagged else ''}"
        f" merged to {base_ref}: {merged}"
    )
    return DeployGate(
        state=state,
        base_ref=base_ref,
        merged=merged,
        allow_dirty=allow_dirty,
        allow_unmerged=allow_unmerged,
    )


# ---------------------------------------------------------------------------
# Deployed marker (written on the server so "what is live" is answerable)
# ---------------------------------------------------------------------------


def deployed_marker_path(remote_repo: str = DEFAULT_REMOTE_REPO) -> str:
    return f"{str(remote_repo).rstrip('/')}/{MARKER_FILENAME}"


def build_marker(
    gate: DeployGate,
    *,
    target: str,
    script: str,
    invariants: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the JSON payload recorded as ``.deployed.json`` on the server."""
    state = gate.state
    payload: dict[str, Any] = {
        "schema": 1,
        "target": target,
        "commit": state.commit,
        "short": state.short,
        "branch": state.branch,
        "tag": state.tags[0] if state.tags else None,
        "base_ref": gate.base_ref,
        "merged_to_base": gate.merged,
        "dirty": state.dirty,
        "guards": {
            "clean_worktree": not state.dirty,
            "deployable_ref": gate.merged or state.tagged,
        },
        "invariants": invariants,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "deployed_by": os.environ.get(ACTOR_ENV, "").strip()
        or (getpass.getuser() or "unknown"),
        "script": script,
    }
    if extra:
        payload.update(extra)
    return payload


def write_remote_marker(
    client: Any,
    marker: dict[str, Any],
    *,
    remote_repo: str = DEFAULT_REMOTE_REPO,
    owner: str = "camxora",
) -> str:
    """Write the deployed marker on the server and return its remote path."""
    path = deployed_marker_path(remote_repo)
    data = (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8")
    sftp = client.open_sftp()
    try:
        with sftp.file(path, "wb") as handle:
            handle.write(data)
        sftp.chmod(path, 0o644)
    finally:
        sftp.close()
    client.exec_command(f"chown {shlex.quote(owner)} {shlex.quote(path)}")
    return path


# ---------------------------------------------------------------------------
# Runtime invariants (critical paths that must survive every deploy)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Invariant:
    name: str
    path: str
    needles: tuple[str, ...] = ()


# Our AI-routing / recovery work. A deploy that loses any of these is rejected.
INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        "recovery-guard",
        "platform_api/services/suno_audio_resolver.py",
        ("_DASHED_UUID_RE", "RECOVERY_AUDIO_ENABLED"),
    ),
    Invariant("ai-routing-service", "platform_api/services/ai_routing_service.py"),
    Invariant(
        "musicapi-provider-switch",
        "platform_api/clients/suno_client.py",
        ("active_provider_is_musicapi",),
    ),
    Invariant(
        "batch-recovery-guard",
        "platform_api/services/batch_service.py",
        ("_recover_download_url",),
    ),
)

_CHECK_FN = r"""
check_file() {
  name="$1"; rel="$2"; shift 2
  f="$REPO/$rel"
  if [ ! -f "$f" ]; then
    echo "INVARIANT FAIL  $name  (missing $rel)"
    fail=1
    return
  fi
  for needle in "$@"; do
    if ! grep -qF -- "$needle" "$f"; then
      echo "INVARIANT FAIL  $name  (needle not found: $needle)"
      fail=1
      return
    fi
  done
  echo "INVARIANT OK    $name"
}
""".strip()


def build_invariant_script(
    remote_repo: str = DEFAULT_REMOTE_REPO,
    invariants: Sequence[Invariant] = INVARIANTS,
) -> str:
    """Bash script (read-only) that checks every runtime invariant on the server."""
    lines = ["set -u", f"REPO={shlex.quote(str(remote_repo))}", "fail=0", _CHECK_FN]
    for inv in invariants:
        args = " ".join(shlex.quote(part) for part in (inv.name, inv.path, *inv.needles))
        lines.append(f"check_file {args}")
    lines.append('if [ "$fail" -ne 0 ]; then echo "INVARIANTS_FAILED"; fi')
    lines.append("exit $fail")
    return "\n".join(lines) + "\n"


def _exec_script(client: Any, script: str) -> tuple[int, str]:
    """Run ``script`` on the server via ``bash -s``; return (exit_code, output)."""
    stdin, stdout, _stderr = client.exec_command("bash -s")
    stdin.write(script)
    try:
        stdin.channel.shutdown_write()
    except Exception:  # pragma: no cover - channel may already be closed
        pass
    out = stdout.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out


def run_invariants(
    client: Any,
    remote_repo: str = DEFAULT_REMOTE_REPO,
    *,
    invariants: Sequence[Invariant] = INVARIANTS,
    check_runner: CheckRunner | None = None,
) -> tuple[bool, str]:
    """Run the invariant checks; return (all_ok, combined_output)."""
    script = build_invariant_script(remote_repo, invariants)
    run = check_runner or _exec_script
    code, out = run(client, script)
    return code == 0, out


def enforce_invariants(
    client: Any,
    remote_repo: str = DEFAULT_REMOTE_REPO,
    *,
    invariants: Sequence[Invariant] = INVARIANTS,
    check_runner: CheckRunner | None = None,
) -> str:
    """Run invariants and raise ``SystemExit`` when any critical path is missing."""
    ok, out = run_invariants(
        client, remote_repo, invariants=invariants, check_runner=check_runner
    )
    print(out.strip() or "[deploy-guard] no invariant output")
    if not ok:
        raise SystemExit(
            "Refusing to finish deploy: runtime invariants failed (a critical path was "
            "removed or reverted). Inspect the INVARIANT FAIL lines above."
        )
    return "ok"


# ---------------------------------------------------------------------------
# Combined post-deploy step
# ---------------------------------------------------------------------------


def post_deploy_record(
    client: Any,
    gate: DeployGate,
    *,
    target: str,
    script: str,
    remote_repo: str = DEFAULT_REMOTE_REPO,
    invariants: Sequence[Invariant] = INVARIANTS,
    verify_invariants: bool = True,
    check_runner: CheckRunner | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify runtime invariants, then write the deployed-SHA marker."""
    status = "skipped"
    if verify_invariants:
        status = enforce_invariants(
            client, remote_repo, invariants=invariants, check_runner=check_runner
        )
    marker = build_marker(
        gate, target=target, script=script, invariants=status, extra=extra
    )
    path = write_remote_marker(client, marker, remote_repo=remote_repo)
    print(f"[deploy-guard] wrote {path} (commit {marker['short']})")
    return marker
