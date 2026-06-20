from __future__ import annotations

from ..utils.music_common import connect_db
from .persistence import DbCfg


def _range_where_ts(column: str, *, from_ymd: str = "", to_ymd: str = "") -> tuple[str, list[object]]:
    parts: list[str] = []
    params: list[object] = []
    f = str(from_ymd or "").strip()
    t = str(to_ymd or "").strip()
    if f:
        parts.append(f"{column} >= %s::date")
        params.append(f)
    if t:
        parts.append(f"{column} < (%s::date + interval '1 day')")
        params.append(t)
    if not parts:
        return "", []
    return " where " + " and ".join(parts), params


def count_songs(cfg: DbCfg, *, from_ymd: str = "", to_ymd: str = "") -> int:
    where_sql, params = _range_where_ts("created_at", from_ymd=from_ymd, to_ymd=to_ymd)
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from songs{where_sql}", tuple(params))
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def count_images(cfg: DbCfg, *, status: str, from_ymd: str = "", to_ymd: str = "", profile_id: str = "") -> int:
    st = str(status or "").strip().upper()
    pid = str(profile_id or "").strip()
    where_sql, params = _range_where_ts("updated_at", from_ymd=from_ymd, to_ymd=to_ymd)
    extra: list[str] = ["status = %s"]
    p: list[object] = [st]
    if pid:
        extra.append("profile_id = %s")
        p.append(pid)
    where_sql2 = (" where " if not where_sql else where_sql + " and ") + " and ".join(extra)
    params2 = [*params, *p]
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from image_jobs{where_sql2}", tuple(params2))
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def count_youtube(cfg: DbCfg, *, status: str, from_ymd: str = "", to_ymd: str = "", profile_id: str = "") -> int:
    st = str(status or "").strip().upper()
    pid = str(profile_id or "").strip()
    where_sql, params = _range_where_ts("updated_at", from_ymd=from_ymd, to_ymd=to_ymd)
    extra: list[str] = ["status = %s"]
    p: list[object] = [st]
    if pid:
        extra.append("profile_id = %s")
        p.append(pid)
    where_sql2 = (" where " if not where_sql else where_sql + " and ") + " and ".join(extra)
    params2 = [*params, *p]
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from youtube_upload_jobs{where_sql2}", tuple(params2))
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def list_recent_activity(cfg: DbCfg, *, from_ymd: str = "", to_ymd: str = "", limit: int = 50, profile_id: str = "") -> list[dict]:
    safe_limit = max(1, min(500, int(limit or 50)))
    pid = str(profile_id or "").strip()
    where_song, params_song = _range_where_ts("s.created_at", from_ymd=from_ymd, to_ymd=to_ymd)
    where_img, params_img = _range_where_ts("i.updated_at", from_ymd=from_ymd, to_ymd=to_ymd)
    where_yt, params_yt = _range_where_ts("y.updated_at", from_ymd=from_ymd, to_ymd=to_ymd)
    img_filter = ""
    yt_filter = ""
    if pid:
        img_filter = " and i.profile_id = %s"
        yt_filter = " and y.profile_id = %s"
        params_img = [*params_img, pid]
        params_yt = [*params_yt, pid]
    params = [*params_song, *params_img, *params_yt, safe_limit]
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select ts, kind, batch_id, profile_id, role, stage, status, detail
                from (
                    select
                        s.created_at as ts,
                        'Song Created' as kind,
                        s.batch_id as batch_id,
                        '' as profile_id,
                        '' as role,
                        'Music' as stage,
                        coalesce(s.status, '') as status,
                        coalesce(s.title, '') as detail
                    from songs s
                    {where_song}
                    union all
                    select
                        i.updated_at as ts,
                        case
                            when upper(i.status) = 'READY' then 'Image Ready'
                            when upper(i.status) = 'FAILED' then 'Image Failed'
                            when upper(i.status) = 'CANCELLED' then 'Image Cancelled'
                            else 'Image ' || upper(i.status)
                        end as kind,
                        i.batch_id as batch_id,
                        i.profile_id as profile_id,
                        upper(coalesce(i.channel_role, '')) as role,
                        'Image' as stage,
                        upper(i.status) as status,
                        (coalesce(i.kind, '') || case when coalesce(i.error, '') <> '' then ' · ' || i.error else '' end) as detail
                    from image_jobs i
                    {where_img}{img_filter}
                    union all
                    select
                        y.updated_at as ts,
                        case
                            when upper(y.status) = 'READY' then 'YouTube Uploaded'
                            when upper(y.status) = 'FAILED' then 'YouTube Failed'
                            when upper(y.status) = 'CANCELLED' then 'YouTube Cancelled'
                            else 'YouTube ' || upper(y.status)
                        end as kind,
                        coalesce(y.batch_id, '') as batch_id,
                        coalesce(y.profile_id, '') as profile_id,
                        upper(coalesce(y.role, '')) as role,
                        'YouTube' as stage,
                        upper(coalesce(y.status, '')) as status,
                        coalesce(y.error, '') as detail
                    from youtube_upload_jobs y
                    {where_yt}{yt_filter}
                ) t
                order by ts desc nulls last
                limit %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
            out: list[dict] = []
            for ts, kind, batch_id, profile_id, role, stage, status, detail in rows:
                out.append(
                    {
                        "ts": ts.isoformat(timespec="seconds") if hasattr(ts, "isoformat") else str(ts or ""),
                        "kind": str(kind or ""),
                        "batchId": str(batch_id or ""),
                        "profileId": str(profile_id or ""),
                        "role": str(role or ""),
                        "stage": str(stage or ""),
                        "status": str(status or ""),
                        "detail": str(detail or ""),
                    }
                )
            return out
    finally:
        conn.close()
