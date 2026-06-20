from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..utils.music_common import connect_db
from .persistence import DbCfg


@dataclass(frozen=True)
class YouTubeAccount:
    profile_id: str
    channel_id: str
    channel_title: str
    refresh_token_enc: str
    scopes: str


@dataclass(frozen=True)
class YouTubeOAuthApp:
    id: str
    name: str
    client_id: str
    client_secret_enc: str
    updated_at: str


def db_get_youtube_account(cfg: DbCfg, profile_id: str) -> YouTubeAccount | None:
    pid = str(profile_id or "").strip()
    if not pid:
        return None
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select profile_id, channel_id, channel_title, refresh_token_enc, scopes "
                "from youtube_accounts where profile_id = %s",
                (pid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return YouTubeAccount(
                profile_id=str(row[0] or ""),
                channel_id=str(row[1] or ""),
                channel_title=str(row[2] or ""),
                refresh_token_enc=str(row[3] or ""),
                scopes=str(row[4] or ""),
            )
    finally:
        conn.close()


def db_list_youtube_oauth_apps(cfg: DbCfg, limit: int = 500) -> list[YouTubeOAuthApp]:
    lim = max(1, min(5000, int(limit or 500)))
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name, client_id, client_secret_enc, updated_at "
                "from youtube_oauth_apps order by name asc, updated_at desc limit %s",
                (lim,),
            )
            out: list[YouTubeOAuthApp] = []
            for oid, name, client_id, client_secret_enc, updated_at in cur.fetchall():
                out.append(
                    YouTubeOAuthApp(
                        id=str(oid or ""),
                        name=str(name or ""),
                        client_id=str(client_id or ""),
                        client_secret_enc=str(client_secret_enc or ""),
                        updated_at=updated_at.isoformat(timespec="seconds") if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                    )
                )
            return out
    finally:
        conn.close()


def db_get_youtube_oauth_app(cfg: DbCfg, oauth_app_id: str) -> YouTubeOAuthApp | None:
    oid = str(oauth_app_id or "").strip()
    if not oid:
        return None
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name, client_id, client_secret_enc, updated_at from youtube_oauth_apps where id = %s",
                (oid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return YouTubeOAuthApp(
                id=str(row[0] or ""),
                name=str(row[1] or ""),
                client_id=str(row[2] or ""),
                client_secret_enc=str(row[3] or ""),
                updated_at=row[4].isoformat(timespec="seconds") if hasattr(row[4], "isoformat") else str(row[4] or ""),
            )
    finally:
        conn.close()


def db_upsert_youtube_oauth_app(cfg: DbCfg, data: dict[str, Any]) -> str:
    oid = str((data or {}).get("id", "")).strip()
    name = str((data or {}).get("name", "")).strip()
    client_id = str((data or {}).get("clientId", "")).strip()
    client_secret_enc = str((data or {}).get("clientSecretEnc", "")).strip()
    if not oid or not name or not client_id or not client_secret_enc:
        return ""
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into youtube_oauth_apps(id, name, client_id, client_secret_enc, updated_at) "
                "values (%s, %s, %s, %s, now()) "
                "on conflict (id) do update set "
                "name = excluded.name, client_id = excluded.client_id, client_secret_enc = excluded.client_secret_enc, updated_at = excluded.updated_at",
                (oid, name, client_id, client_secret_enc),
            )
    finally:
        conn.close()
    return oid


def db_count_profiles_using_youtube_oauth_app(cfg: DbCfg, oauth_app_id: str) -> int:
    oid = str(oauth_app_id or "").strip()
    if not oid:
        return 0
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("select count(*) from profiles where youtube_oauth_app_id = %s", (oid,))
            row = cur.fetchone()
            return int((row[0] if row else 0) or 0)
    finally:
        conn.close()


def db_delete_youtube_oauth_app(cfg: DbCfg, oauth_app_id: str) -> None:
    oid = str(oauth_app_id or "").strip()
    if not oid:
        return
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from youtube_oauth_apps where id = %s", (oid,))
    finally:
        conn.close()


def db_upsert_youtube_account(cfg: DbCfg, data: dict[str, Any]) -> None:
    profile_id = str((data or {}).get("profileId", "")).strip()
    if not profile_id:
        return
    channel_id = str((data or {}).get("channelId", "")).strip()
    channel_title = str((data or {}).get("channelTitle", "")).strip()
    refresh_token_enc = str((data or {}).get("refreshTokenEnc", "")).strip()
    scopes = str((data or {}).get("scopes", "")).strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into youtube_accounts(id, profile_id, channel_id, channel_title, refresh_token_enc, scopes, updated_at) "
                "values (%s, %s, %s, %s, %s, %s, now()) "
                "on conflict (profile_id) do update set "
                "channel_id = excluded.channel_id, channel_title = excluded.channel_title, "
                "refresh_token_enc = excluded.refresh_token_enc, scopes = excluded.scopes, updated_at = excluded.updated_at",
                (profile_id, profile_id, channel_id, channel_title, refresh_token_enc, scopes),
            )
    finally:
        conn.close()


def db_delete_youtube_account(cfg: DbCfg, profile_id: str) -> None:
    pid = str(profile_id or "").strip()
    if not pid:
        return
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from youtube_accounts where profile_id = %s", (pid,))
    finally:
        conn.close()


def db_enqueue_youtube_upload_job(cfg: DbCfg, job: dict[str, Any]) -> None:
    job_uid = str((job or {}).get("jobUid", "")).strip()
    if not job_uid:
        return
    batch_id = str((job or {}).get("batchId", "")).strip()
    profile_id = str((job or {}).get("profileId", "")).strip()
    role = str((job or {}).get("role", "")).strip()
    file_path = str((job or {}).get("filePath", "")).strip()
    status = str((job or {}).get("status", "")).strip().upper() or "PENDING"
    error = str((job or {}).get("error", "")).strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into youtube_upload_jobs(job_uid, batch_id, profile_id, role, file_path, status, attempt_count, updated_at) "
                "values (%s, %s, %s, %s, %s, %s, 0, now()) "
                "on conflict (job_uid) do update set "
                "file_path = excluded.file_path, "
                "status = case "
                "when youtube_upload_jobs.status in ('FAILED','CANCELLED') and youtube_upload_jobs.file_path <> excluded.file_path and excluded.status = 'PENDING' then 'PENDING' "
                "when youtube_upload_jobs.status in ('BLOCKED') and excluded.status = 'PENDING' then 'PENDING' "
                "else youtube_upload_jobs.status end, "
                "error = case "
                "when youtube_upload_jobs.status in ('FAILED','CANCELLED') and youtube_upload_jobs.file_path <> excluded.file_path and excluded.status = 'PENDING' then '' "
                "when youtube_upload_jobs.status in ('BLOCKED') and excluded.status = 'PENDING' then '' "
                "else youtube_upload_jobs.error end, "
                "updated_at = now()",
                (job_uid, batch_id, profile_id, role, file_path, status),
            )
            if error and status != "PENDING":
                cur.execute(
                    "update youtube_upload_jobs set error = %s, updated_at = now() where job_uid = %s",
                    (error, job_uid),
                )
    finally:
        conn.close()


def db_list_youtube_upload_jobs(cfg: DbCfg, limit: int = 200) -> list[dict]:
    lim = max(1, min(2000, int(limit or 200)))
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select job_uid, batch_id, profile_id, role, file_path, status, attempt_count, error, youtube_video_id, youtube_url, created_at, updated_at "
                "from youtube_upload_jobs order by updated_at desc, id desc limit %s",
                (lim,),
            )
            out: list[dict] = []
            for (
                job_uid,
                batch_id,
                profile_id,
                role,
                file_path,
                status,
                attempt_count,
                error,
                youtube_video_id,
                youtube_url,
                created_at,
                updated_at,
            ) in cur.fetchall():
                out.append(
                    {
                        "jobUid": str(job_uid or ""),
                        "batchId": str(batch_id or ""),
                        "profileId": str(profile_id or ""),
                        "role": str(role or ""),
                        "filePath": str(file_path or ""),
                        "status": str(status or ""),
                        "attemptCount": int(attempt_count or 0),
                        "error": str(error or ""),
                        "youtubeVideoId": str(youtube_video_id or ""),
                        "youtubeUrl": str(youtube_url or ""),
                        "createdAt": created_at.isoformat(timespec="seconds") if hasattr(created_at, "isoformat") else str(created_at or ""),
                        "updatedAt": updated_at.isoformat(timespec="seconds") if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                    }
                )
            return out
    finally:
        conn.close()


def db_pick_pending_youtube_upload_jobs(cfg: DbCfg, max_jobs: int = 5) -> list[dict]:
    limit = max(1, min(50, int(max_jobs or 5)))
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select job_uid, batch_id, profile_id, role, file_path, attempt_count, error, youtube_video_id, youtube_url "
                "from youtube_upload_jobs "
                "where status = 'PENDING' "
                "order by updated_at desc, id desc "
                "limit %s",
                (limit,),
            )
            jobs: list[dict] = []
            for job_uid, batch_id, profile_id, role, file_path, attempt_count, error, youtube_video_id, youtube_url in cur.fetchall():
                jobs.append(
                    {
                        "jobUid": str(job_uid or ""),
                        "batchId": str(batch_id or ""),
                        "profileId": str(profile_id or ""),
                        "role": str(role or ""),
                        "filePath": str(file_path or ""),
                        "attemptCount": int(attempt_count or 0),
                        "error": str(error or ""),
                        "youtubeVideoId": str(youtube_video_id or ""),
                        "youtubeUrl": str(youtube_url or ""),
                    }
                )
            return jobs
    finally:
        conn.close()


def list_youtube_upload_jobs_for_batches(cfg: DbCfg, *, batch_ids: list[str], profile_ids: list[str]) -> list[dict]:
    batches = [str(x).strip() for x in (batch_ids or []) if str(x).strip()]
    profiles = [str(x).strip() for x in (profile_ids or []) if str(x).strip()]
    if not batches or not profiles:
        return []
    batch_placeholders = ", ".join(["%s"] * len(batches))
    profile_placeholders = ", ".join(["%s"] * len(profiles))
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select job_uid, batch_id, profile_id, role, file_path, status, attempt_count, error,
                       youtube_video_id, youtube_url, created_at, updated_at
                from youtube_upload_jobs
                where batch_id in ({batch_placeholders})
                  and profile_id in ({profile_placeholders})
                order by updated_at desc, id desc
                """,
                tuple([*batches, *profiles]),
            )
            out: list[dict] = []
            for (
                job_uid,
                batch_id,
                profile_id,
                role,
                file_path,
                status,
                attempt_count,
                error,
                youtube_video_id,
                youtube_url,
                created_at,
                updated_at,
            ) in cur.fetchall():
                out.append(
                    {
                        "jobUid": str(job_uid or ""),
                        "batchId": str(batch_id or ""),
                        "profileId": str(profile_id or ""),
                        "role": str(role or ""),
                        "filePath": str(file_path or ""),
                        "status": str(status or ""),
                        "attemptCount": int(attempt_count or 0),
                        "error": str(error or ""),
                        "youtubeVideoId": str(youtube_video_id or ""),
                        "youtubeUrl": str(youtube_url or ""),
                        "createdAt": created_at.isoformat(timespec="seconds") if hasattr(created_at, "isoformat") else str(created_at or ""),
                        "updatedAt": updated_at.isoformat(timespec="seconds") if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                    }
                )
            return out
    finally:
        conn.close()


def db_claim_pending_youtube_upload_jobs(
    cfg: DbCfg,
    max_jobs: int = 1,
    *,
    stale_running_sec: int = 3600,
    max_running: int = 1,
) -> list[dict]:
    limit = max(1, min(20, int(max_jobs or 1)))
    stale_sec = max(30, min(24 * 3600, int(stale_running_sec or 3600)))
    threshold = datetime.utcnow() - timedelta(seconds=stale_sec)
    max_run = max(1, min(20, int(max_running or 1)))
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from youtube_upload_jobs where status = 'RUNNING' and updated_at is not null and updated_at >= %s",
                (threshold,),
            )
            row = cur.fetchone()
            running = int((row[0] if row else 0) or 0)
            if running >= max_run:
                conn.commit()
                return []
            cur.execute(
                """
                with cte as (
                    select id
                    from youtube_upload_jobs
                    where status = 'PENDING'
                       or (status = 'RUNNING' and (updated_at is null or updated_at < %s))
                    order by updated_at asc nulls first, id asc
                    for update skip locked
                    limit %s
                )
                update youtube_upload_jobs
                set status='RUNNING', updated_at=now()
                where id in (select id from cte)
                returning job_uid, batch_id, profile_id, role, file_path, attempt_count, error, youtube_video_id, youtube_url
                """,
                (threshold, limit),
            )
            rows = cur.fetchall()
        conn.commit()
        out: list[dict] = []
        for job_uid, batch_id, profile_id, role, file_path, attempt_count, error, youtube_video_id, youtube_url in rows:
            out.append(
                {
                    "jobUid": str(job_uid or ""),
                    "batchId": str(batch_id or ""),
                    "profileId": str(profile_id or ""),
                    "role": str(role or ""),
                    "filePath": str(file_path or ""),
                    "attemptCount": int(attempt_count or 0),
                    "error": str(error or ""),
                    "youtubeVideoId": str(youtube_video_id or ""),
                    "youtubeUrl": str(youtube_url or ""),
                }
            )
        return out
    finally:
        conn.close()


def db_mark_youtube_upload_job_running(cfg: DbCfg, job_uid: str) -> None:
    uid = str(job_uid or "").strip()
    if not uid:
        return
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update youtube_upload_jobs set status = 'RUNNING', updated_at = now() where job_uid = %s and status <> 'CANCELLED'",
                (uid,),
            )
    finally:
        conn.close()


def db_mark_youtube_upload_job_ready(cfg: DbCfg, job_uid: str, youtube_video_id: str, youtube_url: str, note: str = "") -> None:
    uid = str(job_uid or "").strip()
    if not uid:
        return
    vid = str(youtube_video_id or "").strip()
    url = str(youtube_url or "").strip()
    note2 = str(note or "").strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update youtube_upload_jobs set status = 'READY', youtube_video_id = %s, youtube_url = %s, error = %s, updated_at = now() where job_uid = %s and status <> 'CANCELLED'",
                (vid, url, note2, uid),
            )
    finally:
        conn.close()


def db_mark_youtube_upload_job_failed(cfg: DbCfg, job_uid: str, error: str, attempt_count: int) -> None:
    uid = str(job_uid or "").strip()
    if not uid:
        return
    msg = str(error or "").strip()
    attempts = max(0, int(attempt_count or 0))
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update youtube_upload_jobs set status = 'FAILED', error = %s, attempt_count = %s, updated_at = now() where job_uid = %s and status <> 'CANCELLED'",
                (msg, attempts, uid),
            )
    finally:
        conn.close()


def db_mark_youtube_upload_job_pending(cfg: DbCfg, job_uid: str, attempt_count: int, error: str = "") -> None:
    uid = str(job_uid or "").strip()
    if not uid:
        return
    attempts = max(0, int(attempt_count or 0))
    msg = str(error or "").strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update youtube_upload_jobs set status = 'PENDING', error = %s, attempt_count = %s, updated_at = now() where job_uid = %s and status <> 'CANCELLED'",
                (msg, attempts, uid),
            )
    finally:
        conn.close()


def db_force_youtube_upload_job_pending(cfg: DbCfg, job_uid: str, attempt_count: int = 0, error: str = "") -> int:
    uid = str(job_uid or "").strip()
    if not uid:
        return 0
    attempts = max(0, int(attempt_count or 0))
    msg = str(error or "").strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update youtube_upload_jobs set status = 'PENDING', error = %s, attempt_count = %s, updated_at = now() where job_uid = %s",
                (msg, attempts, uid),
            )
            return int(cur.rowcount or 0)
    finally:
        conn.close()


def db_cancel_youtube_jobs_for_row(cfg: DbCfg, *, batch_id: str, profile_id: str, role: str, reason: str = "Cancelled by user") -> int:
    bid = str(batch_id or "").strip()
    pid = str(profile_id or "").strip()
    r = str(role or "").strip().upper()
    if not bid or not pid or not r:
        return 0
    msg = str(reason or "Cancelled by user").strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update youtube_upload_jobs
                set status='CANCELLED',
                    error=%s,
                    updated_at=now()
                where batch_id=%s
                  and profile_id=%s
                  and role=%s
                  and status in ('PENDING', 'RUNNING', 'FAILED', 'BLOCKED')
                """,
                (msg, bid, pid, r),
            )
            return int(cur.rowcount or 0)
    finally:
        conn.close()


def db_mark_youtube_upload_job_cancelled(
    cfg: DbCfg,
    job_uid: str,
    *,
    reason: str = "Cancelled by user",
    youtube_video_id: str = "",
    youtube_url: str = "",
) -> int:
    uid = str(job_uid or "").strip()
    if not uid:
        return 0
    msg = str(reason or "Cancelled by user").strip()
    vid = str(youtube_video_id or "").strip()
    url = str(youtube_url or "").strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            if vid or url:
                cur.execute(
                    """
                    update youtube_upload_jobs
                    set status='CANCELLED',
                        error=%s,
                        youtube_video_id=%s,
                        youtube_url=%s,
                        updated_at=now()
                    where job_uid=%s
                    """,
                    (msg, vid, url, uid),
                )
            else:
                cur.execute(
                    """
                    update youtube_upload_jobs
                    set status='CANCELLED',
                        error=%s,
                        updated_at=now()
                    where job_uid=%s
                    """,
                    (msg, uid),
                )
            return int(cur.rowcount or 0)
    finally:
        conn.close()


def db_cancel_all_pending_youtube_jobs(cfg: DbCfg, *, reason: str = "Cancelled by user") -> int:
    msg = str(reason or "Cancelled by user").strip()
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update youtube_upload_jobs
                set status='CANCELLED',
                    error=%s,
                    updated_at=now()
                where status in ('PENDING', 'RUNNING')
                """,
                (msg,),
            )
            return int(cur.rowcount or 0)
    finally:
        conn.close()
