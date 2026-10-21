#!/usr/bin/env python3
"""Deploy CamXora via SSH.

Secrets are split by environment (never commit either file):
  .deploy/secrets.sandbox.env      — sandbox only (default for load_secrets)
  .deploy/secrets.production.env — production only (explicit load)

Legacy .deploy/secrets.env is still read as a fallback for sandbox until migrated.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / ".deploy"
SECRETS_SANDBOX_PATH = DEPLOY_DIR / "secrets.sandbox.env"
SECRETS_PRODUCTION_PATH = DEPLOY_DIR / "secrets.production.env"
SECRETS_LEGACY_PATH = DEPLOY_DIR / "secrets.env"
SECRETS_PATH = SECRETS_LEGACY_PATH  # backward-compat alias
EXAMPLE_SANDBOX_PATH = DEPLOY_DIR / "secrets.sandbox.env.example"
EXAMPLE_PRODUCTION_PATH = DEPLOY_DIR / "secrets.production.env.example"
EXAMPLE_PATH = DEPLOY_DIR / "secrets.env.example"
REMOTE_SCRIPT = Path(__file__).resolve().parent / "camxora-sandbox-remote.sh"
DEPLOY_KEY = DEPLOY_DIR / "camxora_deploy_ed25519"
KNOWN_HOSTS_PATH = DEPLOY_DIR / "known_hosts"
# Emergency escape hatch for a host whose key is not yet pinned. Never set this
# for routine deploys.
_INSECURE_HOST_KEY = os.environ.get("DEPLOY_INSECURE_IGNORE_HOST_KEY", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
VENV_DIR = Path(__file__).resolve().parent / ".venv"
DEPLOY_DIRS = ("platform_api", "admin_portal", "website", "user_portal", "music_web", "shared")
# Single files the systemd timers execute by absolute path. They live outside
# DEPLOY_DIRS, so without this the healthcheck units start with status 127
# ("No such file or directory") after every tarball deploy.
DEPLOY_FILES = (
    "scripts/deploy/platform-healthcheck.sh",
    "scripts/deploy/musicapi-healthcheck.sh",
)
SKIP_NAMES = {
    "node_modules",
    ".venv",
    "__pycache__",
    ".git",
    ".next",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    ".dbg",
    "uploads",
    "tests",
    ".env",
}

DeployEnv = Literal["sandbox", "production"]

CANONICAL_SANDBOX_HOST = "46.250.235.83"
CANONICAL_PRODUCTION_HOST = "82.197.71.248"

_ENV_META_KEY = "_CAMXORA_DEPLOY_ENV"


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def secrets_path_for(env: DeployEnv) -> Path:
    return SECRETS_SANDBOX_PATH if env == "sandbox" else SECRETS_PRODUCTION_PATH


def example_path_for(env: DeployEnv) -> Path:
    return EXAMPLE_SANDBOX_PATH if env == "sandbox" else EXAMPLE_PRODUCTION_PATH


def _peer_host(env: DeployEnv) -> str:
    peer_env: DeployEnv = "production" if env == "sandbox" else "sandbox"
    peer_path = secrets_path_for(peer_env)
    if not peer_path.is_file():
        return CANONICAL_PRODUCTION_HOST if env == "sandbox" else CANONICAL_SANDBOX_HOST
    peer = parse_env_file(peer_path)
    if peer_env == "sandbox":
        return (
            peer.get("SANDBOX_VPS_HOST")
            or peer.get("VPS_HOST")
            or CANONICAL_SANDBOX_HOST
        ).strip()
    return (
        peer.get("PRODUCTION_VPS_HOST")
        or peer.get("VPS_HOST")
        or CANONICAL_PRODUCTION_HOST
    ).strip()


def load_secrets(env: DeployEnv = "sandbox") -> dict[str, str]:
    """Load secrets for one environment. Default is sandbox (safe for most scripts)."""
    path = secrets_path_for(env)
    if path.is_file():
        data = parse_env_file(path)
        data[_ENV_META_KEY] = env
        return data

    if env == "sandbox" and SECRETS_LEGACY_PATH.is_file():
        print(
            f"WARN: {path.name} missing; falling back to legacy {SECRETS_LEGACY_PATH.name}. "
            f"Run: python scripts/deploy/split_secrets_env.py",
            file=sys.stderr,
        )
        data = parse_env_file(SECRETS_LEGACY_PATH)
        data[_ENV_META_KEY] = env
        return data

    print(f"Missing {path}")
    print(f"Copy {example_path_for(env)} -> {path} and fill in credentials.")
    sys.exit(1)


def load_sandbox_secrets() -> dict[str, str]:
    return load_secrets("sandbox")


def load_production_secrets() -> dict[str, str]:
    return load_secrets("production")


def resolve_sandbox_ssh(secrets: dict[str, str] | None = None) -> tuple[str, str, str | None]:
    """Return (host, user, password) for the sandbox VPS only."""
    secrets = secrets if secrets is not None else load_sandbox_secrets()
    host = (
        secrets.get("SANDBOX_VPS_HOST")
        or secrets.get("VPS_HOST")
        or ""
    ).strip()
    user = (
        secrets.get("SANDBOX_VPS_USER")
        or secrets.get("VPS_USER")
        or "root"
    ).strip()
    password = (
        secrets.get("SANDBOX_VPS_PASSWORD")
        or secrets.get("VPS_PASSWORD")
        or None
    )
    if not host:
        raise RuntimeError(
            f"VPS_HOST required in {SECRETS_SANDBOX_PATH} (sandbox host {CANONICAL_SANDBOX_HOST})"
        )
    forbidden = {
        CANONICAL_PRODUCTION_HOST,
        _peer_host("sandbox"),
        (secrets.get("PRODUCTION_VPS_HOST") or "").strip(),
    }
    forbidden.discard("")
    if host in forbidden:
        raise RuntimeError(
            f"Refusing sandbox SSH to {host}: that looks like production. "
            f"Use {SECRETS_SANDBOX_PATH} with VPS_HOST={CANONICAL_SANDBOX_HOST}"
        )
    return host, user, password


def resolve_production_ssh(secrets: dict[str, str] | None = None) -> tuple[str, str, str | None]:
    """Return (host, user, password) for the production VPS only."""
    secrets = secrets if secrets is not None else load_production_secrets()
    host = (
        secrets.get("PRODUCTION_VPS_HOST")
        or secrets.get("VPS_HOST")
        or ""
    ).strip()
    user = (
        secrets.get("PRODUCTION_VPS_USER")
        or secrets.get("VPS_USER")
        or "root"
    ).strip()
    password = (
        secrets.get("PRODUCTION_VPS_PASSWORD")
        or secrets.get("VPS_PASSWORD")
        or None
    )
    if not host:
        raise RuntimeError(
            f"VPS_HOST required in {SECRETS_PRODUCTION_PATH} "
            f"(production host {CANONICAL_PRODUCTION_HOST})"
        )
    forbidden = {
        CANONICAL_SANDBOX_HOST,
        _peer_host("production"),
        (secrets.get("SANDBOX_VPS_HOST") or "").strip(),
    }
    forbidden.discard("")
    if host in forbidden:
        raise RuntimeError(
            f"Refusing production SSH to {host}: that looks like sandbox. "
            f"Use {SECRETS_PRODUCTION_PATH} with VPS_HOST={CANONICAL_PRODUCTION_HOST}"
        )
    return host, user, password


def ensure_paramiko():
    if str(VENV_DIR) not in sys.path:
        site = VENV_DIR / "Lib" / "site-packages"
        if site.is_dir():
            sys.path.insert(0, str(site))
    try:
        import paramiko  # noqa: F401
        return
    except ImportError:
        pass
    print("Installing deploy dependencies (paramiko)...")
    VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    pip = VENV_DIR / "Scripts" / "pip.exe"
    if not pip.is_file():
        pip = VENV_DIR / "bin" / "pip"
    subprocess.check_call([str(pip), "install", "-q", "-r", str(Path(__file__).parent / "requirements.txt")])
    site = VENV_DIR / "Lib" / "site-packages"
    if site.is_dir():
        sys.path.insert(0, str(site))


def ensure_deploy_key() -> Path:
    pub = DEPLOY_KEY.with_suffix("")
    pub_path = Path(str(DEPLOY_KEY) + ".pub")
    if DEPLOY_KEY.is_file():
        return DEPLOY_KEY
    print("Generating deploy SSH key...")
    (REPO_ROOT / ".deploy").mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-f",
            str(DEPLOY_KEY),
            "-N",
            "",
            "-C",
            "camxora-deploy",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return DEPLOY_KEY


def _prepare_host_keys(client, allow_unknown: bool = False) -> None:
    """Verify the server host key against known_hosts.

    System known_hosts is loaded first, then the repo-local
    ``.deploy/known_hosts``. Unknown hosts are rejected unless ``allow_unknown``
    (password bootstrap, trust-on-first-use) or the explicit
    ``DEPLOY_INSECURE_IGNORE_HOST_KEY`` escape hatch is set.
    """
    import paramiko

    client.load_system_host_keys()
    if KNOWN_HOSTS_PATH.is_file():
        try:
            client.load_host_keys(str(KNOWN_HOSTS_PATH))
        except OSError:
            pass
    if allow_unknown or _INSECURE_HOST_KEY:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())


def bootstrap_pubkey(host: str, user: str, password: str, key_path: Path) -> None:
    import paramiko

    pub_path = Path(f"{key_path}.pub")
    pub = pub_path.read_text(encoding="utf-8").strip()
    print(f"Bootstrapping SSH key for {user}@{host}...")
    client = paramiko.SSHClient()
    # Trust-on-first-use is acceptable here because we are about to install a key
    # over password auth; the key is then pinned for every later connection.
    _prepare_host_keys(client, allow_unknown=True)
    client.connect(hostname=host, username=user, password=password, timeout=30)
    try:
        KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        client.save_host_keys(str(KNOWN_HOSTS_PATH))
    except OSError:
        pass
    cmd = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        f"grep -qxF '{pub}' ~/.ssh/authorized_keys 2>/dev/null || "
        f"echo '{pub}' >> ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys"
    )
    _, stdout, stderr = client.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    if exit_code != 0:
        raise RuntimeError(f"Bootstrap failed: {stderr.read().decode()}")


def ssh_connect(host: str, user: str, key_path: Path, password: str | None = None):
    import paramiko

    client = paramiko.SSHClient()
    _prepare_host_keys(client)
    pkey = paramiko.Ed25519Key.from_private_key_file(str(key_path))
    try:
        client.connect(hostname=host, username=user, pkey=pkey, timeout=30)
        return client
    except paramiko.AuthenticationException:
        if not password:
            raise
        bootstrap_pubkey(host, user, password, key_path)
        _prepare_host_keys(client)
        client.connect(hostname=host, username=user, pkey=pkey, timeout=30)
        return client


# After a full platform_api tarball extract, delete revision files that are
# not in the archive. `tar -xzf` overwrites but never removes leftovers, which
# is how a retired 084_* file can become a second Alembic head and hang API
# startup. Refuse to prune if the archive has no versions/*.py.
PRUNE_LEFTOVER_ALEMBIC_REMOTE = r"""
python3 - <<'PY'
from pathlib import Path
import tarfile
import sys

keep = set()
with tarfile.open("/tmp/camxora-src.tar.gz") as tar:
    for member in tar.getmembers():
        name = member.name.replace("\\", "/")
        prefix = "platform_api/migrations/versions/"
        if member.isfile() and name.startswith(prefix) and name.endswith(".py"):
            keep.add(Path(name).name)
if not keep:
    print("REFUSING to prune Alembic versions: tarball has no versions/*.py")
    sys.exit(1)
remote = Path("/opt/camxora/repo/platform_api/migrations/versions")
removed = []
for path in sorted(remote.glob("*.py")):
    if path.name not in keep:
        path.unlink()
        removed.append(path.name)
if removed:
    print("PRUNED leftover Alembic files: " + ", ".join(removed))
else:
    print("No leftover Alembic files to prune")
PY
"""


def tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = Path(tarinfo.name).parts
    if any(part in SKIP_NAMES for part in parts):
        return None
    if tarinfo.name.endswith((".pyc", ".pyo", ".log")):
        return None
    return tarinfo


def build_source_tarball() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="camxora-deploy-"))
    archive = tmp / "camxora-src.tar.gz"
    print("Packaging local source for upload...")
    with tarfile.open(archive, "w:gz") as tar:
        for name in DEPLOY_DIRS:
            src = REPO_ROOT / name
            if not src.is_dir():
                raise FileNotFoundError(f"Missing deploy directory: {src}")
            tar.add(src, arcname=name, filter=tar_filter, recursive=True)
        for name in DEPLOY_FILES:
            src = REPO_ROOT / name
            if not src.is_file():
                raise FileNotFoundError(f"Missing deploy file: {src}")
            tar.add(src, arcname=name)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"Source archive ready ({size_mb:.1f} MB)")
    return archive


def upload_source(client) -> None:
    archive = build_source_tarball()
    remote_path = "/tmp/camxora-src.tar.gz"
    sftp = client.open_sftp()
    uploaded = 0
    total = archive.stat().st_size

    def progress(sent: int, _total: int) -> None:
        nonlocal uploaded
        uploaded = sent
        if total:
            pct = min(100, int(sent * 100 / total))
            print(f"\rUploading source... {pct}%", end="", flush=True)

    print(f"Uploading to {remote_path}...")
    sftp.put(str(archive), remote_path, callback=progress)
    print()
    sftp.close()


def upload_and_run(client, secrets: dict[str, str]) -> int:
    upload_source(client)

    remote_path = "/tmp/camxora-sandbox-remote.sh"
    script_bytes = REMOTE_SCRIPT.read_bytes().replace(b"\r\n", b"\n")
    sftp = client.open_sftp()
    with sftp.file(remote_path, "wb") as remote_file:
        remote_file.write(script_bytes)
    sftp.chmod(remote_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)

    nginx_conf = Path(__file__).resolve().parent / "nginx-camxora-sandbox.conf"
    if nginx_conf.is_file():
        sftp.put(str(nginx_conf), "/tmp/nginx-camxora-sandbox.conf")

    sftp.close()

    env_keys = [
        "SYNC_FROM_LOCAL",
        "GIT_REPO",
        "GIT_BRANCH",
        "GITHUB_TOKEN",
        "ADMIN_EMAIL",
        "CERTBOT_EMAIL",
        "DB_PASSWORD",
        "PLATFORM_JWT_SECRET",
        "PLATFORM_ENCRYPTION_MASTER_KEY",
        "PLATFORM_SUNO_CALLBACK_HMAC_SECRET",
        "EDGE_VERIFY_SECRET",
        "PLATFORM_CUTLUY_SECRET_KEY",
        "PLATFORM_CUTLUY_PAYMENT_LINK_ID",
        "PLATFORM_CUTLUY_WEBHOOK_SECRET",
        "PLATFORM_CHMABA_API_KEY",
        "PLATFORM_CHMABA_STORE_ID",
        "PLATFORM_CHMABA_WEBHOOK_SECRET",
        "API_WORKERS",
    ]
    exports = ["export SYNC_FROM_LOCAL='1'"]
    for key in env_keys:
        val = secrets.get(key, "")
        if val:
            safe = val.replace("'", "'\\''")
            exports.append(f"export {key}='{safe}'")
    export_block = " && ".join(exports) if exports else "true"

    cmd = f"{export_block} && bash {remote_path}"
    print("Running remote install (this may take 15–30 minutes)...")
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport unavailable")
    channel = transport.open_session()
    channel.get_pty()
    channel.exec_command(cmd)

    while True:
        if channel.recv_ready():
            chunk = channel.recv(4096).decode(errors="replace")
            sys.stdout.buffer.write(chunk.encode(sys.stdout.encoding or "utf-8", errors="replace"))
            sys.stdout.flush()
        if channel.recv_stderr_ready():
            chunk = channel.recv_stderr(4096).decode(errors="replace")
            sys.stderr.buffer.write(chunk.encode(sys.stderr.encoding or "utf-8", errors="replace"))
            sys.stderr.flush()
        if channel.exit_status_ready():
            while channel.recv_ready():
                chunk = channel.recv(4096).decode(errors="replace")
                sys.stdout.buffer.write(chunk.encode(sys.stdout.encoding or "utf-8", errors="replace"))
            while channel.recv_stderr_ready():
                chunk = channel.recv_stderr(4096).decode(errors="replace")
                sys.stderr.buffer.write(chunk.encode(sys.stderr.encoding or "utf-8", errors="replace"))
            return channel.recv_exit_status()
        import time

        time.sleep(0.2)


def main() -> int:
    ensure_paramiko()
    secrets = load_secrets()
    host = secrets.get("VPS_HOST", "")
    user = secrets.get("VPS_USER", "root")
    password = secrets.get("VPS_PASSWORD") or None
    custom_key = secrets.get("VPS_SSH_KEY") or None

    if not host:
        print("VPS_HOST is required in secrets.env")
        return 1

    key_path = Path(custom_key) if custom_key else ensure_deploy_key()
    if not REMOTE_SCRIPT.is_file():
        print(f"Missing {REMOTE_SCRIPT}")
        return 1

    client = ssh_connect(host, user, key_path, password)
    try:
        code = upload_and_run(client, secrets)
    finally:
        client.close()

    if code == 0:
        print("\nDeploy finished successfully.")
        print(f"  API:    https://api.sandbox.camxora.com/health")
        print(f"  Portal: https://app.sandbox.camxora.com")
        print(f"  Admin:  https://admin.sandbox.camxora.com")
        print(f"  Site:   https://sandbox.camxora.com")
        print(f"  Music:  https://music.sandbox.camxora.com")
    else:
        print(f"\nDeploy failed with exit code {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
