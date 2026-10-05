"""Deploy guards: git-state gate, deployed marker, runtime invariants."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "deploy"
        / "deploy_guards.py"
    )
    spec = importlib.util.spec_from_file_location("deploy_guards", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Required so @dataclass can resolve string annotations (PEP 563) by module name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def test_parse_porcelain_keeps_only_changes() -> None:
    module = _load()
    assert module.parse_porcelain(" M a.py\n?? b.txt\n\n") == (" M a.py", "?? b.txt")
    assert module.parse_porcelain("") == ()


def test_parse_branch_detached() -> None:
    module = _load()
    assert module.parse_branch("main\n") == "main"
    assert module.parse_branch("HEAD\n") == ""
    assert module.parse_branch("  \n") == ""


def test_parse_tags_sorted() -> None:
    module = _load()
    assert module.parse_tags("v2\nv1\n") == ("v1", "v2")
    assert module.parse_tags("") == ()


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


class _Proc:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _fake_git(
    *,
    commit: str = "a" * 40,
    short: str = "aaaaaaa",
    branch: str = "main",
    tags: str = "",
    porcelain: str = "",
    ancestor_rc: int = 0,
):
    def run(args, cwd=None, capture_output=None, text=None):
        cmd = " ".join(args)
        if "rev-parse --short" in cmd:
            return _Proc(short + "\n")
        if "rev-parse HEAD" in cmd:
            return _Proc(commit + "\n")
        if "--abbrev-ref" in cmd:
            return _Proc(branch + "\n")
        if "tag --points-at" in cmd:
            return _Proc(tags)
        if "status --porcelain" in cmd:
            return _Proc(porcelain)
        if "merge-base --is-ancestor" in cmd:
            return _Proc("", ancestor_rc)
        return _Proc("")

    return run


def test_state_clean_merged_passes_but_dirty_and_unmerged_fail() -> None:
    module = _load()
    state = module.collect_repo_state(Path("."), runner=_fake_git())
    assert state.dirty is False
    assert module.deploy_gate_violations(state, is_merged=True) == []

    dirty = module.collect_repo_state(
        Path("."), runner=_fake_git(porcelain=" M x.py\n")
    )
    assert dirty.dirty is True
    assert len(module.deploy_gate_violations(dirty, is_merged=True)) == 1

    unmerged = module.collect_repo_state(Path("."), runner=_fake_git())
    assert len(module.deploy_gate_violations(unmerged, is_merged=False)) == 1

    # a tagged HEAD is deployable even when unmerged
    tagged = module.collect_repo_state(Path("."), runner=_fake_git(tags="v1\n"))
    assert module.deploy_gate_violations(tagged, is_merged=False) == []

    # escape hatches silence both
    assert (
        module.deploy_gate_violations(
            dirty, is_merged=False, allow_dirty=True, allow_unmerged=True
        )
        == []
    )


def test_enforce_deploy_gate_raises_and_env_override(monkeypatch) -> None:
    module = _load()
    gate = module.enforce_deploy_gate(Path("."), runner=_fake_git())
    assert gate.merged is True

    try:
        module.enforce_deploy_gate(
            Path("."), runner=_fake_git(porcelain="?? new.py\n")
        )
    except SystemExit:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected SystemExit for dirty worktree")

    monkeypatch.setenv(module.ALLOW_DIRTY_ENV, "1")
    gate2 = module.enforce_deploy_gate(
        Path("."), runner=_fake_git(porcelain="?? new.py\n")
    )
    assert gate2.state.dirty is True


def test_is_ancestor_false_without_refs() -> None:
    module = _load()
    assert module.is_ancestor(Path("."), "", "main", runner=_fake_git()) is False


# ---------------------------------------------------------------------------
# Marker
# ---------------------------------------------------------------------------


def test_build_marker_payload() -> None:
    module = _load()
    state = module.RepoState(
        commit="b" * 40, short="bbbbbbb", branch="release/1", tags=("v9",)
    )
    gate = module.DeployGate(state=state, base_ref="origin/main", merged=True)
    marker = module.build_marker(gate, target="production", script="sync.py", invariants="ok")
    assert marker["commit"] == "b" * 40
    assert marker["tag"] == "v9"
    assert marker["guards"] == {"clean_worktree": True, "deployable_ref": True}
    assert marker["invariants"] == "ok"
    assert marker["merged_to_base"] is True
    assert json.loads(json.dumps(marker))["target"] == "production"


def test_deployed_marker_path() -> None:
    module = _load()
    assert module.deployed_marker_path("/opt/camxora/repo/") == "/opt/camxora/repo/.deployed.json"


class _FakeSftp:
    def __init__(self) -> None:
        self.data: bytes | None = None
        self.mode: int | None = None
        self.path: str | None = None

    def file(self, path: str, _mode: str):
        self.path = path
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def write(self, data: bytes) -> None:
        self.data = data

    def chmod(self, _path: str, mode: int) -> None:
        self.mode = mode

    def close(self) -> None:
        return None


class _FakeClient:
    def __init__(self) -> None:
        self.sftp = _FakeSftp()
        self.commands: list[str] = []

    def open_sftp(self):
        return self.sftp

    def exec_command(self, cmd: str):
        self.commands.append(cmd)
        return (None, None, None)


def test_write_remote_marker() -> None:
    module = _load()
    client = _FakeClient()
    path = module.write_remote_marker(
        client, {"commit": "c"}, remote_repo="/opt/camxora/repo"
    )
    assert path == "/opt/camxora/repo/.deployed.json"
    assert client.sftp.path == path
    assert client.sftp.mode == 0o644
    assert json.loads(client.sftp.data.decode())["commit"] == "c"
    assert client.commands and client.commands[0].startswith("chown ")


# ---------------------------------------------------------------------------
# Runtime invariants
# ---------------------------------------------------------------------------


def test_invariant_script_covers_critical_paths() -> None:
    module = _load()
    script = module.build_invariant_script()
    assert "platform_api/services/suno_audio_resolver.py" in script
    assert "_DASHED_UUID_RE" in script
    assert "RECOVERY_AUDIO_ENABLED" in script
    assert "platform_api/services/ai_routing_service.py" in script
    assert "active_provider_is_musicapi" in script
    assert "_recover_download_url" in script
    assert "exit $fail" in script


def test_run_invariants_ok_and_failure() -> None:
    module = _load()
    ok, out = module.run_invariants(
        object(), check_runner=lambda _client, _script: (0, "INVARIANT OK x")
    )
    assert ok is True and "INVARIANT OK" in out

    bad_ok, _ = module.run_invariants(
        object(), check_runner=lambda _client, _script: (1, "INVARIANT FAIL")
    )
    assert bad_ok is False


def test_enforce_invariants_raises_on_failure() -> None:
    module = _load()
    assert (
        module.enforce_invariants(
            object(), check_runner=lambda _c, _s: (0, "INVARIANT OK")
        )
        == "ok"
    )
    try:
        module.enforce_invariants(
            object(), check_runner=lambda _c, _s: (1, "INVARIANT FAIL")
        )
    except SystemExit:
        return
    raise AssertionError("expected SystemExit when invariants fail")


def test_post_deploy_record_writes_marker_after_verify() -> None:
    module = _load()
    state = module.RepoState(commit="d" * 40, short="ddddddd", branch="main")
    gate = module.DeployGate(state=state, base_ref="origin/main", merged=True)
    client = _FakeClient()
    marker = module.post_deploy_record(
        client,
        gate,
        target="production",
        script="sync.py",
        check_runner=lambda _c, _s: (0, "INVARIANT OK"),
    )
    assert marker["invariants"] == "ok"
    assert client.sftp.data is not None
