"""Read-only: why somvannda@gmail.com cannot complete Suno MP3 download on prod."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
EMAIL = "somvannda@gmail.com"

REMOTE_CMD = r'''
set +e
EMAIL='somvannda@gmail.com'
echo "=== [1] user + access ==="
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo .venv/bin/python - "$EMAIL" <<'PYEOF'
import asyncio, os, sys, urllib.parse
import asyncpg

EMAIL = sys.argv[1].strip().lower()

def load_env(path):
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return out

def host_of(url):
    url = (url or "").strip()
    if not url:
        return ""
    try:
        p = urllib.parse.urlparse(url)
        path = (p.path or "")[:48]
        return f"{p.scheme}://{p.netloc}{path}"
    except Exception:
        return url[:60]

async def main():
    env = load_env("/opt/camxora/repo/platform_api/.env")
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not dsn:
        print("NO_DSN"); return
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    user = await pool.fetchrow(
        "SELECT id, email, status, email_confirmed, created_at, token_version "
        "FROM users WHERE lower(email)=$1",
        EMAIL,
    )
    if not user:
        print("NO_USER", EMAIL)
        await pool.close()
        return
    uid = user["id"]
    print("USER", dict(user))
    print("USER_ID", str(uid))

    print("\n== licenses ==")
    try:
        rows = await pool.fetch(
            "SELECT id, plan_id, status, expires_at, created_at "
            "FROM licenses WHERE user_id=$1 ORDER BY created_at DESC LIMIT 8",
            uid,
        )
        for r in rows:
            print(" ", dict(r))
        if not rows:
            print("  (none)")
    except Exception as exc:
        print("  licenses failed", type(exc).__name__, str(exc)[:180])

    print("\n== web_subscriptions ==")
    try:
        rows = await pool.fetch(
            "SELECT id, status, plan_id, plan_name, current_period_end, "
            "monthly_credits_granted, monthly_credits_used, updated_at "
            "FROM web_subscriptions WHERE user_id=$1 ORDER BY updated_at DESC LIMIT 8",
            uid,
        )
        for r in rows:
            print(" ", dict(r))
        if not rows:
            print("  (none)")
    except Exception as exc:
        print("  web_subscriptions failed", type(exc).__name__, str(exc)[:180])

    print("\n== suno_tasks by source/status ==")
    rows = await pool.fetch(
        """
        SELECT COALESCE(source,'(null)') AS source, status, count(*) AS n,
               min(created_at) AS first, max(created_at) AS last
        FROM suno_tasks WHERE user_id=$1
        GROUP BY 1, 2 ORDER BY last DESC
        """,
        uid,
    )
    for r in rows:
        print(" ", dict(r))

    print("\n== download flags (non-web_music) last 14d ==")
    try:
        row = await pool.fetchrow(
            """
            SELECT count(*) AS n,
                   count(*) FILTER (WHERE status ILIKE 'success') AS success,
                   count(*) FILTER (WHERE downloaded_ok) AS dl_ok,
                   count(*) FILTER (WHERE downloaded_alt) AS dl_alt,
                   count(*) FILTER (
                     WHERE status ILIKE 'success'
                       AND NOT COALESCE(downloaded_ok,false)
                       AND NOT COALESCE(downloaded_alt,false)
                   ) AS success_undownloaded
            FROM suno_tasks
            WHERE user_id=$1
              AND COALESCE(source,'') <> 'web_music'
              AND created_at > now() - interval '14 days'
            """,
            uid,
        )
        print(" ", dict(row) if row else None)
    except Exception as exc:
        print("  flags failed", type(exc).__name__, str(exc)[:180])

    print("\n== package / b2 / url presence (all sources, last 7d) ==")
    try:
        row = await pool.fetchrow(
            """
            SELECT count(*) AS n,
                   count(*) FILTER (WHERE audio_url_ok IS NOT NULL AND btrim(audio_url_ok)<>'') AS has_url_ok,
                   count(*) FILTER (WHERE audio_url_alt IS NOT NULL AND btrim(audio_url_alt)<>'') AS has_url_alt,
                   count(*) FILTER (WHERE b2_storage_key_ok IS NOT NULL AND btrim(b2_storage_key_ok)<>'') AS has_b2_ok,
                   count(*) FILTER (WHERE b2_storage_key_alt IS NOT NULL AND btrim(b2_storage_key_alt)<>'') AS has_b2_alt,
                   count(*) FILTER (WHERE package_status_ok='ready') AS pkg_ok_ready,
                   count(*) FILTER (WHERE package_status_alt='ready') AS pkg_alt_ready,
                   count(*) FILTER (WHERE error_message IS NOT NULL AND btrim(error_message)<>'') AS with_err
            FROM suno_tasks
            WHERE user_id=$1 AND created_at > now() - interval '7 days'
            """,
            uid,
        )
        print(" ", dict(row) if row else None)
    except Exception as exc:
        print("  package query failed", type(exc).__name__, str(exc)[:180])

    print("\n== recent 20 suno_tasks ===")
    cols_ok = await pool.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name='suno_tasks'
        """
    )
    colnames = {r["column_name"] for r in cols_ok}
    extra = []
    for c in (
        "downloaded_ok", "downloaded_alt", "package_status_ok", "package_status_alt",
        "b2_storage_key_ok", "b2_storage_key_alt", "wav_status_ok", "wav_status_alt",
        "external_task_id", "title", "error_message",
    ):
        if c in colnames:
            extra.append(c)
    select_extra = ", ".join(extra) if extra else "1 as _x"
    rows = await pool.fetch(
        f"""
        SELECT id, status, source, created_at, updated_at,
               left(coalesce(audio_url_ok,''), 1) as has_ok_ch,
               left(coalesce(audio_url_alt,''), 1) as has_alt_ch,
               {select_extra}
        FROM suno_tasks WHERE user_id=$1
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 20
        """,
        uid,
    )
    for r in rows:
        d = dict(r)
        for k in ("audio_url_ok", "audio_url_alt"):
            if k in d:
                d[k] = host_of(d[k])
        for k in ("b2_storage_key_ok", "b2_storage_key_alt"):
            if k in d and d[k]:
                d[k] = str(d[k])[:80]
        if d.get("error_message"):
            d["error_message"] = str(d["error_message"])[:180]
        print(" ", d)

    print("\n== url hosts on latest success tasks ===")
    rows = await pool.fetch(
        """
        SELECT id, source, status, created_at,
               audio_url_ok, audio_url_alt
        FROM suno_tasks WHERE user_id=$1 AND status ILIKE 'success'
        ORDER BY created_at DESC LIMIT 8
        """,
        uid,
    )
    for r in rows:
        print(" ", {
            "id": str(r["id"]),
            "source": r["source"],
            "created": str(r["created_at"]),
            "ok": host_of(r["audio_url_ok"]),
            "alt": host_of(r["audio_url_alt"]),
        })

    print("\n== export_events last 15 ===")
    try:
        rows = await pool.fetch(
            """
            SELECT created_at, format, variant, actor, suno_task_id
            FROM export_events WHERE user_id=$1
            ORDER BY created_at DESC LIMIT 15
            """,
            uid,
        )
        for r in rows:
            print(" ", dict(r))
        if not rows:
            print("  (none)")
    except Exception as exc:
        print("  export_events failed", type(exc).__name__, str(exc)[:180])

    print("\n== pending desktop downloads (success, not downloaded) last 20 ===")
    try:
        rows = await pool.fetch(
            """
            SELECT id, source, status, created_at, updated_at, downloaded_ok, downloaded_alt,
                   left(coalesce(error_message,''), 120) AS err
            FROM suno_tasks
            WHERE user_id=$1
              AND status ILIKE 'success'
              AND COALESCE(source,'') <> 'web_music'
              AND (NOT COALESCE(downloaded_ok,false) OR NOT COALESCE(downloaded_alt,false))
            ORDER BY created_at DESC
            LIMIT 20
            """,
            uid,
        )
        print("  count_shown", len(rows))
        for r in rows:
            print(" ", dict(r))
    except Exception as exc:
        print("  pending query failed", type(exc).__name__, str(exc)[:180])

    await pool.close()
    print("DB_PROBE_DONE")

asyncio.run(main())
PYEOF

echo
echo "=== [2] api journal download errors (6h) ==="
UID=$(cd /opt/camxora/repo/platform_api && env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PY'
import asyncio, os
import asyncpg
async def m():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL","")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://","postgresql://",1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
    uid = await pool.fetchval("SELECT id FROM users WHERE lower(email)=$1", "somvannda@gmail.com")
    print(uid or "")
    await pool.close()
asyncio.run(m())
PY
)
echo "UID=$UID"
journalctl -u camxora-api --since "6 hours ago" --no-pager 2>/dev/null \
  | grep -iE "somvannda|${UID}|Web music MP3|download CDN|Audio file is not available|download_requires_subscription|MissingKey|cdn1.suno|tempfile.aiquickdraw|watermark|download_mp3|/download" \
  | tail -80
echo
echo "=== [3] nginx music/api download paths (2h) ==="
sudo awk '$4 >= "[17/Sep/2026:00:00:00" {
  if ($0 ~ /download/ && $0 ~ /(mp3|wav|web-music|suno)/) print
}' /var/log/nginx/access.log 2>/dev/null | grep -iE 'download|web-music' | tail -40
echo
echo "=== [4] journal traceback around download (6h) ==="
journalctl -u camxora-api --since "6 hours ago" --no-pager 2>/dev/null \
  | grep -iE 'Traceback|download_suno_mp3|NotFoundError|ForbiddenError|encrypted_playback|validate_mp3' \
  | tail -40
echo DIAG_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== prod MP3 download diag {host} email={EMAIL} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
