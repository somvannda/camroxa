"""Deploy source packaging: commit archives, manifests, verification, pruning.

The point of these tests is the incident that kept repeating: a deploy shipped
a stale working tree (or a file that only existed on the server) and reverted
newer code. Packaging now comes from one commit and is verified by manifest.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


def _load(name: str):
    path = Path(__file__).resolve().parents[2] / "scripts" / "deploy" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"deploy_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    git("config", "commit.gpgsign", "false")

    files = {
        "platform_api/app.py": "print('v1')\r\n",
        "platform_api/tests/test_app.py": "def test_x(): pass\n",
        "platform_api/node_modules/pkg/index.js": "module.exports = 1\n",
        "shared/util.py": "VALUE = 1\n",
        "scripts/deploy/platform-healthcheck.sh": "#!/bin/sh\necho ok\n",
        "docs/readme.md": "not deployed\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="")
    git("add", "-A")
    git("commit", "-qm", "initial")
    return root


def _build(repo: Path, module, tmp_path: Path, commit: str = "HEAD") -> tuple[Path, dict]:
    archive = tmp_path / "src.tar.gz"
    manifest = module.build_archive_from_commit(
        repo,
        module.resolve_source_commit(repo, commit),
        archive,
        roots=("platform_api", "shared"),
        files=("scripts/deploy/platform-healthcheck.sh",),
        ref=commit,
    )
    return archive, manifest


def test_archive_ships_only_committed_deployable_files(repo: Path, tmp_path: Path) -> None:
    module = _load("release_source")
    (repo / "platform_api" / "untracked.py").write_text("UNTRACKED = True\n", encoding="utf-8")

    archive, manifest = _build(repo, module, tmp_path)
    names = set(manifest["files"])

    assert "platform_api/app.py" in names
    assert "shared/util.py" in names
    assert "scripts/deploy/platform-healthcheck.sh" in names
    # Untracked, skipped-dir and out-of-scope files never ship.
    assert "platform_api/untracked.py" not in names
    assert not any("node_modules" in name for name in names)
    assert not any("/tests/" in name for name in names)
    assert "docs/readme.md" not in names

    assert module.verify_archive(archive) == []


def test_archive_content_tracks_the_commit_not_the_worktree(repo: Path, tmp_path: Path) -> None:
    module = _load("release_source")
    first_commit = module.resolve_source_commit(repo, "HEAD")

    # Dirty the worktree *after* committing: a commit build must ignore it.
    (repo / "platform_api" / "app.py").write_text("print('dirty')\n", encoding="utf-8")
    archive, manifest = _build(repo, module, tmp_path, first_commit)
    with tarfile.open(archive, "r:gz") as tar:
        shipped = tar.extractfile("platform_api/app.py").read()
    assert b"dirty" not in shipped
    assert b"v1" in shipped

    # A newer commit must change what ships.
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "v2"], cwd=repo, check=True)
    second_commit = module.resolve_source_commit(repo, "HEAD")
    assert second_commit != first_commit
    archive2, _ = _build(repo, module, tmp_path / "second", second_commit)
    assert module.read_manifest(archive2)["commit"] == second_commit


def test_manifest_normalizes_text_line_endings(repo: Path, tmp_path: Path) -> None:
    module = _load("release_source")
    archive, _ = _build(repo, module, tmp_path)
    with tarfile.open(archive, "r:gz") as tar:
        data = tar.extractfile("platform_api/app.py").read()
    assert b"\r\n" not in data


def test_verify_tree_and_archive_detect_drift(repo: Path, tmp_path: Path) -> None:
    module = _load("release_source")
    deploy = _load("verify_release_manifest")
    archive, manifest = _build(repo, module, tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert deploy.verify_tree(repo, manifest) == []
    assert deploy.main(["--repo", str(repo), "--manifest", str(manifest_path)]) == 0

    (repo / "shared" / "util.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert deploy.verify_tree(repo, manifest)
    assert deploy.main(["--repo", str(repo), "--manifest", str(manifest_path)]) == 1
    (repo / "shared" / "util.py").unlink()
    assert any("missing deployed file" in p for p in deploy.verify_tree(repo, manifest))


def test_stale_files_are_pruned_but_runtime_files_survive(repo: Path, tmp_path: Path) -> None:
    module = _load("release_source")
    deploy = _load("verify_release_manifest")

    previous = {"files": {"platform_api/old_module.py": "x", "uploads/keep.bin": "y"}}
    current = {"files": {"platform_api/app.py": "z"}}
    stale = deploy.stale_paths(previous, current, scope=("platform_api",))
    assert stale == ["platform_api/old_module.py"]

    (repo / "platform_api" / "old_module.py").write_text("OLD = 1\n", encoding="utf-8")
    # Not in either manifest → never pruned.
    runtime = repo / "platform_api" / "uploads" / "keep.bin"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_bytes(b"keep")

    removed = deploy.prune_tree(repo, stale)
    assert removed == ["platform_api/old_module.py"]
    assert not (repo / "platform_api" / "old_module.py").exists()
    assert runtime.exists()


def test_require_merged_refuses_a_tagged_feature_branch() -> None:
    module = _load("deploy_guards")

    class _Proc:
        def __init__(self, stdout: str = "", returncode: int = 0) -> None:
            self.stdout, self.stderr, self.returncode = stdout, "", returncode

    def runner(args, cwd=None, capture_output=None, text=None):
        cmd = " ".join(args)
        if "rev-parse --short" in cmd:
            return _Proc("abc1234\n")
        if "rev-parse HEAD" in cmd:
            return _Proc("a" * 40 + "\n")
        if "--abbrev-ref" in cmd:
            return _Proc("feat/revert\n")
        if "tag --points-at" in cmd:
            return _Proc("v9-rc\n")
        if "status --porcelain" in cmd:
            return _Proc("")
        if "merge-base --is-ancestor" in cmd:
            return _Proc("", 1)  # not merged
        return _Proc("")

    state = module.collect_repo_state(Path("."), runner=runner)
    # Old behaviour: a tag excused an unmerged HEAD (that shipped a branch to prod).
    assert module.deploy_gate_violations(state, is_merged=False) == []
    # Production rule: tags do not excuse it.
    assert module.deploy_gate_violations(state, is_merged=False, require_merged=True)
