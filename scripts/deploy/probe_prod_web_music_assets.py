#!/usr/bin/env python3
"""READ-ONLY: size the web-music B2 asset gaps (mp3 captured but wav/lrc/package missing)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
PSQL = "sudo -u postgres psql -d camxora_platform -P pager=off -t -A"

QUERIES = r'''
echo "=== A. suno_tasks totals ==="
%PSQL% -c "SELECT 'total=' || count(*) FROM suno_tasks;"
%PSQL% -c "SELECT 'by_source=' || source || ':' || count(*) FROM suno_tasks GROUP BY source ORDER BY 1;"

echo "=== B. mp3 captured (any variant has b2 key) ==="
%PSQL% -c "SELECT 'with_mp3=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_ok,'') <> '' OR COALESCE(b2_storage_key_alt,'') <> '';"

echo "=== C. mp3 captured but wav missing (per variant) ==="
%PSQL% -c "SELECT 'mp3ok_no_wav_ok=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_ok,'') <> '' AND COALESCE(b2_wav_storage_key_ok,'') = '';"
%PSQL% -c "SELECT 'mp3alt_no_wav_alt=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_alt,'') <> '' AND COALESCE(b2_wav_storage_key_alt,'') = '';"

echo "=== D. mp3 captured but lrc missing (variant-level, all) ==="
%PSQL% -c "SELECT 'mp3ok_no_lrc_ok=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_ok,'') <> '' AND COALESCE(b2_lrc_storage_key_ok,'') = '';"
%PSQL% -c "SELECT 'mp3alt_no_lrc_alt=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_alt,'') <> '' AND COALESCE(b2_lrc_storage_key_alt,'') = '';"

echo "=== E. lrc asymmetry (one variant has lrc, sibling missing) ==="
%PSQL% -c "SELECT 'lrc_ok_only=' || count(*) FROM suno_tasks WHERE COALESCE(b2_lrc_storage_key_ok,'') <> '' AND COALESCE(b2_lrc_storage_key_alt,'') = '' AND COALESCE(b2_storage_key_alt,'') <> '';"
%PSQL% -c "SELECT 'lrc_alt_only=' || count(*) FROM suno_tasks WHERE COALESCE(b2_lrc_storage_key_alt,'') <> '' AND COALESCE(b2_lrc_storage_key_ok,'') = '' AND COALESCE(b2_storage_key_ok,'') <> '';"
%PSQL% -c "SELECT 'instrumental=' || count(*) FROM suno_tasks WHERE COALESCE(instrumental,false) = true;"

echo "=== F. encrypted package not ready (mp3 present) ==="
%PSQL% -c "SELECT 'mp3ok_pkg_not_ready=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_ok,'') <> '' AND COALESCE(package_status_ok,'none') <> 'ready';"
%PSQL% -c "SELECT 'mp3alt_pkg_not_ready=' || count(*) FROM suno_tasks WHERE COALESCE(b2_storage_key_alt,'') <> '' AND COALESCE(package_status_alt,'none') <> 'ready';"

echo "=== G. by month for mp3-without-wav (any variant) ==="
%PSQL% -c "SELECT to_char(created_at,'YYYY-MM') AS m, count(*) FROM suno_tasks WHERE (COALESCE(b2_storage_key_ok,'')<>'' OR COALESCE(b2_storage_key_alt,'')<>'') AND (COALESCE(b2_wav_storage_key_ok,'')='' OR COALESCE(b2_wav_storage_key_alt,'')='') GROUP BY 1 ORDER BY 1 LIMIT 12;"
''' .replace("%PSQL%", PSQL)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== web-music asset gap probe on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(QUERIES, get_pty=True, timeout=240)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-1500:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
