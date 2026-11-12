"""Run the platform background worker with the platform API env file.

`uvicorn --env-file` only applies to the API process; the worker needs the same settings
(database, Redis, provider keys) or generation jobs stay `queued` forever. This wrapper
loads the env file with python-dotenv (which does not override exported variables) and
then runs `platform_api.worker` as `__main__`.
"""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys

from dotenv import load_dotenv

repo = Path(__file__).resolve().parents[2]
env_file = Path(os.environ.get("PLATFORM_ENV_FILE", repo / "platform_api" / ".env"))
load_dotenv(env_file)

# Running a script does not put the repo root on sys.path, and `platform_api` must be
# importable from there (same reason the README says not to `cd platform_api`).
sys.path.insert(0, str(repo))

runpy.run_module("platform_api.worker", run_name="__main__")
