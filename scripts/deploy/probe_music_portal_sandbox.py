#!/usr/bin/env python3
"""Diagnose music portal on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    remote = r"""
import subprocess, os

html = subprocess.check_output(["curl", "-s", "http://127.0.0.1:3102/"], text=True)
for needle in ("Sandbox Stream Test", "No published tracks", "Recently added", "Good evening"):
    print(f"html contains {needle!r}:", needle in html)

page_js = "/opt/camxora/repo/music_web/.next/server/app/page.js"
if os.path.isfile(page_js):
    data = open(page_js, "rb").read().decode("utf-8", errors="replace")
    print("page.js has localhost:8000:", "localhost:8000" in data)
    print("page.js has api.sandbox:", "api.sandbox.camxora.com" in data)

chunk = "/opt/camxora/repo/music_web/.next/server/chunks/ssr/music_web_src_components_track-row_tsx_0dgskwz._.js"
print("track-row chunk exists:", os.path.isfile(chunk))

env_prod = "/opt/camxora/repo/music_web/.env.production"
print(".env.production exists:", os.path.isfile(env_prod))
if os.path.isfile(env_prod):
    print(open(env_prod).read())
"""
    path = "/tmp/probe_music_portal.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(remote)
    sftp.close()
    _, stdout, stderr = client.exec_command(f"python3 {path}")
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
