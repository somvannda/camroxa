#!/usr/bin/env python3
"""List logo channel_prompts on sandbox and recent onboarding draft context."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio, asyncpg, os, json
async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    sql = (
        "SELECT id, name, category, genre, match_key, is_active, content "
        "FROM channel_prompts WHERE category = $1 "
        "ORDER BY match_key NULLS LAST, genre, name"
    )
    rows=await conn.fetch(sql, "logo")
    print("LOGO_PROMPTS_COUNT", len(rows))
    for r in rows:
        print("PROMPT_START")
        print("name:", r["name"])
        print("genre:", r["genre"] or "")
        print("match_key:", r["match_key"] or "")
        print("active:", r["is_active"])
        print("content:")
        print(r["content"])
        print("PROMPT_END")

    draft_sql = (
        "SELECT u.email, d.payload FROM onboarding_drafts d "
        "JOIN users u ON u.id = d.user_id WHERE u.email = $1 "
        "ORDER BY d.updated_at DESC LIMIT 1"
    )
    draft=await conn.fetchrow(draft_sql, "somvannda@gmail.com")
    if draft:
        payload = draft["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        print("ONBOARDING_DRAFT_EMAIL", draft["email"])
        print("ONBOARDING_DRAFT", json.dumps(payload, indent=2)[:4000])
    else:
        print("ONBOARDING_DRAFT", "none")

    await conn.close()
asyncio.run(main())
PY'
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err, file=sys.stderr)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
