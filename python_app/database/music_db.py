"""Database functions for the music app."""
from __future__ import annotations

import os
import time
import re
from pathlib import Path
from ..utils.music_common import connect_db, db_identity_key, normalize_text, opening2_lines
from ..database.persistence import DbCfg

# Pool buffers for title generation
_POOL_BUFFERS: dict[str, dict[str, list]] = {}

# Recent title prefix cache for uniqueness
_RECENT_TITLE_PREFIXES_BY_DB: dict[str, dict] = {}
_RECENT_AVOID_CACHE: dict[str, list[str]] = {}


def _cleanup_avoid_cache() -> None:
    """Remove stale entries from the avoid cache."""
    now = time.time()
    stale_keys = [k for k, v in _RECENT_TITLE_PREFIXES_BY_DB.items() if now - v.get("ts", 0) > 3600]
    for k in stale_keys:
        _RECENT_TITLE_PREFIXES_BY_DB.pop(k, None)
        _RECENT_AVOID_CACHE.pop(k, None)


def _first_word(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    return t.split()[0]


def _take_biased_title(db_key: str, buffer: list[dict]) -> dict | None:
    if not buffer:
        return None
    # Prefer index 0 with bias
    idx = 0
    if len(buffer) > 1:
        import random
        idx = random.choices([0, 1], weights=[3, 1], k=1)[0]
        idx = min(idx, len(buffer) - 1)
    return buffer.pop(idx)


def get_recent_for_uniqueness(cfg: DbCfg, n: int = 100) -> list[str]:
    _cleanup_avoid_cache()
    db_key = db_identity_key(cfg) or "default"
    cached = _RECENT_AVOID_CACHE.get(db_key)
    if cached is not None:
        return list(cached)
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select title
                from songs
                where title is not null and title <> ''
                order by created_at desc, id desc
                limit %s
                """,
                (int(n),),
            )
            rows = cur.fetchall()
            titles = [str(r[0]).strip() for r in rows if r[0]]
            _RECENT_AVOID_CACHE[db_key] = titles
            return titles
    finally:
        conn.close()


def get_avoid_lists(cfg: DbCfg | None, limit: int = 200) -> dict:
    _cleanup_avoid_cache()
    if cfg is None:
        return {"titles": [], "albums": [], "openings": []}
    db_key = db_identity_key(cfg) or "default"
    cached = _RECENT_AVOID_CACHE.get(db_key)
    if cached is not None:
        return {"titles": list(cached), "albums": [], "openings": []}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            # Get titles from songs
            cur.execute(
                f"""
                select title
                from songs
                where title is not null and title <> ''
                order by created_at desc, id desc
                limit %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
            titles = [str(r[0]).strip() for r in rows if r[0]]
            _RECENT_AVOID_CACHE[db_key] = titles
            return {"titles": titles, "albums": [], "openings": []}
    finally:
        conn.close()


def pick_batch_and_mark(cfg: DbCfg, profile_id: str, kind: str, limit: int = 1) -> list[dict]:
    """Pick songs from the pool and mark them as in-progress."""
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, song_uid, title, song_description, song_structure, language, creativity,
                    lyrics_raw, lyrics_polished, album, batch_id, batch_index,
                    run_date, profile_ok_id, profile_alt_id, status, created_at
                from songs
                where status = 'pending'
                  and profile_ok_id = %s
                order by created_at asc
                limit %s
                for update skip locked
                """,
                (profile_id, int(limit)),
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                song = {
                    "id": int(r[0]) if r[0] is not None else 0,
                    "songUid": str(r[1] or ""),
                    "title": str(r[2] or ""),
                    "song_description": str(r[3] or ""),
                    "song_structure": str(r[4] or ""),
                    "language": str(r[5] or ""),
                    "creativity": r[6],
                    "lyrics_raw": str(r[7] or ""),
                    "lyrics_polished": str(r[8] or ""),
                    "album": str(r[9] or ""),
                    "batchId": str(r[10] or ""),
                    "batchIndex": int(r[11]) if r[11] is not None else None,
                    "runDate": r[12].isoformat() if r[12] else "",
                    "profileOkId": str(r[13] or ""),
                    "profileAltId": str(r[14] or ""),
                    "status": str(r[15] or ""),
                    "createdAt": r[16].isoformat() if r[16] else "",
                }
                cur.execute(
                    "update songs set status = %s where id = %s",
                    ("in_progress", song["id"]),
                )
                result.append(song)
            conn.commit()
            return result
    except Exception:
        conn.rollback()
        return []
    finally:
        conn.close()


def get_pooled(cfg: DbCfg, *, opening: bool = False, title: bool = True, album: bool = True, limit: int = 50) -> dict:
    """Pick one title, one album, and optionally one opening pair from pool tables."""
    conn = connect_db(cfg, autocommit=True)
    try:
        result: dict = {"title": "", "album": "", "opening": None}
        with conn.cursor() as cur:
            # Pick a title
            if title:
                cur.execute(
                    """
                    select title from title_pool
                    where used_count < %s
                    order by random()
                    limit 1
                    """,
                    (int(limit),),
                )
                row = cur.fetchone()
                if row:
                    result["title"] = str(row[0] or "").strip()
                    cur.execute(
                        "update title_pool set used_count = used_count + 1 where title = %s",
                        (result["title"],),
                    )

            # Pick an album
            if album:
                cur.execute(
                    """
                    select album from album_pool
                    where used_count < %s
                    order by random()
                    limit 1
                    """,
                    (int(limit),),
                )
                row = cur.fetchone()
                if row:
                    result["album"] = str(row[0] or "").strip()
                    cur.execute(
                        "update album_pool set used_count = used_count + 1 where album = %s",
                        (result["album"],),
                    )

            # Pick an opening pair
            if opening:
                cur.execute(
                    """
                    select line1, line2 from opening_pairs
                    where used_count < %s
                    order by random()
                    limit 1
                    """,
                    (int(limit),),
                )
                row = cur.fetchone()
                if row:
                    result["opening"] = {"line1": str(row[0] or "").strip(), "line2": str(row[1] or "").strip()}
                    cur.execute(
                        "update opening_pairs set used_count = used_count + 1 where line1 = %s and line2 = %s",
                        (result["opening"]["line1"], result["opening"]["line2"]),
                    )

        conn.commit()
        return result
    except Exception:
        conn.rollback()
        return {"title": "", "album": "", "opening": None}
    finally:
        conn.close()


def upsert_song(cfg: DbCfg, song: dict) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            song_uid = str(song.get("songUid") or song.get("id") or "").strip()
            song_description = str(song.get("song_description") or song.get("songDescription") or "").strip()
            song_structure = str(song.get("song_structure") or song.get("songStructure") or "").strip()
            lyrics_raw = str(song.get("lyrics_raw") or song.get("lyricsRaw") or "").strip()
            lyrics_polished = str(song.get("lyrics_polished") or song.get("lyricsPolished") or "").strip()
            batch_id = str(song.get("batchId") or song.get("batch_id") or "").strip()
            cur.execute(
                """
                insert into songs(
                    song_uid, title, song_description, song_structure, language, creativity,
                    lyrics_raw, lyrics_polished, album, batch_id, batch_index,
                    run_date, profile_ok_id, profile_alt_id, status, created_at
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    now()
                )
                on conflict (song_uid) do update set
                    title = excluded.title,
                    song_description = excluded.song_description,
                    song_structure = excluded.song_structure,
                    language = excluded.language,
                    creativity = excluded.creativity,
                    lyrics_raw = excluded.lyrics_raw,
                    lyrics_polished = excluded.lyrics_polished,
                    album = excluded.album,
                    batch_id = excluded.batch_id,
                    batch_index = excluded.batch_index,
                    run_date = excluded.run_date,
                    profile_ok_id = excluded.profile_ok_id,
                    profile_alt_id = excluded.profile_alt_id,
                    status = excluded.status
                """,
                (
                    song_uid,
                    str(song.get("title", "") or "").strip(),
                    song_description,
                    song_structure,
                    str(song.get("language", "") or "").strip(),
                    song.get("creativity"),
                    lyrics_raw,
                    lyrics_polished,
                    str(song.get("album", "") or "").strip(),
                    batch_id,
                    song.get("batchIndex"),
                    str(song.get("runDate", "") or "").strip() or None,
                    str(song.get("profileOkId", "") or "").strip(),
                    str(song.get("profileAltId", "") or "").strip(),
                    str(song.get("status", "pending") or "pending").strip(),
                ),
            )
            conn.commit()
    finally:
        conn.close()


def insert_history(cfg: DbCfg, *, kind: str = "info", message: str = "", song_uid: str = "") -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into history(kind, message, song_uid, created_at)
                values (%s, %s, %s, now())
                """,
                (kind, message, song_uid),
            )
            conn.commit()
    finally:
        conn.close()


def get_suno_task_by_request_hash(cfg: DbCfg, request_hash: str) -> dict | None:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, request_hash, song_uid, batch_id, track_no, model, title, style, instrumental,
                    task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir,
                    downloaded_ok, downloaded_alt, updated_at
                from suno_tasks
                where request_hash = %s
                limit 1
                """,
                (request_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "requestHash": str(row[1] or ""),
                "songUid": str(row[2] or ""),
                "batchId": str(row[3] or ""),
                "trackNo": int(row[4]) if row[4] is not None else None,
                "model": str(row[5] or ""),
                "title": str(row[6] or ""),
                "style": str(row[7] or ""),
                "instrumental": bool(row[8]),
                "taskId": str(row[9] or ""),
                "status": str(row[10] or ""),
                "audioUrlOk": str(row[11] or ""),
                "audioUrlAlt": str(row[12] or ""),
                "outputDirOk": str(row[13] or ""),
                "outputDirAlt": str(row[14] or ""),
                "outputDir": str(row[15] or ""),
                "downloadedOk": bool(row[16]),
                "downloadedAlt": bool(row[17]),
                "updatedAt": row[18].isoformat() if row[18] else "",
            }
    finally:
        conn.close()


def get_latest_suno_output_dirs_by_song_uid(cfg: DbCfg, song_uid: str) -> dict:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select output_dir_ok, output_dir_alt, output_dir
                from suno_tasks
                where song_uid = %s
                  and output_dir_ok is not null
                  and output_dir_ok <> ''
                order by updated_at desc, id desc
                limit 1
                """,
                (song_uid,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "message": "No Suno output directories found for song"}
            ok_dir = str(row[0] or row[2] or "").strip() or None
            alt_dir = str(row[1] or row[2] or "").strip() or None
            return {"ok": True, "okDir": ok_dir, "altDir": alt_dir}
    finally:
        conn.close()


def list_latest_suno_tasks_by_song_uids(cfg: DbCfg, song_uids: list[str]) -> dict[str, dict]:
    if not song_uids:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(song_uids))
            cur.execute(
                f"""
                select distinct on (song_uid) song_uid, task_id, status, audio_url_ok, audio_url_alt,
                    output_dir_ok, output_dir_alt, downloaded_ok, downloaded_alt, updated_at
                from suno_tasks
                where song_uid in ({placeholders})
                order by song_uid, updated_at desc, id desc
                """,
                tuple(song_uids),
            )
            rows = cur.fetchall()
            out: dict[str, dict] = {}
            for r in rows:
                uid = str(r[0] or "")
                out[uid] = {
                    "taskId": str(r[1] or ""),
                    "status": str(r[2] or ""),
                    "audioUrlOk": str(r[3] or ""),
                    "audioUrlAlt": str(r[4] or ""),
                    "outputDirOk": str(r[5] or ""),
                    "outputDirAlt": str(r[6] or ""),
                    "downloadedOk": bool(r[7]),
                    "downloadedAlt": bool(r[8]),
                    "updatedAt": r[9].isoformat() if r[9] else "",
                }
            return out
    finally:
        conn.close()


def list_songs_for_history(cfg: DbCfg, *, offset: int = 0, limit: int = 50, from_ymd: str = "", to_ymd: str = "", latest_batch_only: bool = False) -> list[dict]:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            where_parts = []
            params: list = []
            if from_ymd:
                where_parts.append("s.created_at >= %s")
                params.append(from_ymd)
            if to_ymd:
                where_parts.append("s.created_at < (%s::date + interval '1 day')")
                params.append(to_ymd)
            where_parts.append("s.hidden = false")
            where_sql = ""
            if where_parts:
                where_sql = " where " + " and ".join(where_parts)
            cur.execute(
                f"""
                select s.id, s.song_uid, s.title, s.song_description, s.song_structure, s.language, s.creativity,
                    s.lyrics_raw, s.lyrics_polished, s.album, s.batch_id, s.batch_index,
                    s.run_date, s.profile_ok_id, s.profile_alt_id, s.status, s.created_at,
                    pok.name as profile_ok_name, palt.name as profile_alt_name
                from songs s
                left join profiles pok on s.profile_ok_id = pok.uid
                left join profiles palt on s.profile_alt_id = palt.uid
                {where_sql}
                order by s.created_at desc, s.id desc
                limit %s offset %s
                """,
                (*params, int(limit), int(offset)),
            )
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": int(r[0]) if r[0] is not None else 0,
                    "songUid": str(r[1] or ""),
                    "title": str(r[2] or ""),
                    "song_description": str(r[3] or ""),
                    "song_structure": str(r[4] or ""),
                    "language": str(r[5] or ""),
                    "creativity": r[6],
                    "lyrics_raw": str(r[7] or ""),
                    "lyrics_polished": str(r[8] or ""),
                    "album": str(r[9] or ""),
                    "batchId": str(r[10] or ""),
                    "batchIndex": int(r[11]) if r[11] is not None else None,
                    "runDate": r[12].isoformat() if r[12] else "",
                    "profileOkId": str(r[13] or ""),
                    "profileAltId": str(r[14] or ""),
                    "status": str(r[15] or ""),
                    "createdAt": r[16].isoformat() if r[16] else "",
                    "profileOkName": str(r[17] or ""),
                    "profileAltName": str(r[18] or ""),
                })
            return out
    finally:
        conn.close()


def list_batches_for_history(cfg: DbCfg, *, from_ymd: str = "", to_ymd: str = "", limit: int = 200) -> list[dict]:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            conditions: list[str] = []
            params: list = []
            if from_ymd:
                conditions.append("s.run_date >= %s::date")
                params.append(from_ymd)
            if to_ymd:
                conditions.append("s.run_date <= %s::date")
                params.append(to_ymd)
            where_clause = " and ".join(conditions) if conditions else "1=1"
            cur.execute(
                f"""
                select s.batch_id, count(*) as song_count,
                    min(s.created_at) as min_created, max(s.created_at) as max_created,
                    max(s.profile_ok_id) as profile_ok_id, max(s.profile_alt_id) as profile_alt_id,
                    max(pok.name) as profile_ok_name, max(palt.name) as profile_alt_name,
                    max(s.run_date) as run_date
                from songs s
                left join profiles pok on s.profile_ok_id = pok.uid
                left join profiles palt on s.profile_alt_id = palt.uid
                where s.batch_id is not null and s.batch_id <> ''
                  and s.hidden = false
                  and {where_clause}
                group by s.batch_id
                order by min_created desc
                limit %s
                """,
                tuple(params + [int(limit)]),
            )
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "batchId": str(r[0] or ""),
                    "songCount": int(r[1]),
                    "minCreatedAt": r[2].isoformat() if r[2] else "",
                    "maxCreatedAt": r[3].isoformat() if r[3] else "",
                    "profileOkId": str(r[4] or ""),
                    "profileAltId": str(r[5] or ""),
                    "profileOkName": str(r[6] or ""),
                    "profileAltName": str(r[7] or ""),
                    "runDate": r[8].isoformat() if r[8] else "",
                })
            return out
    finally:
        conn.close()


def get_latest_suno_output_dirs_by_batch_id(cfg: DbCfg, batch_id: str) -> dict:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select output_dir_ok, output_dir_alt, output_dir
                from suno_tasks
                where batch_id = %s
                order by updated_at desc, id desc
                limit 1
                """,
                (batch_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "message": "No Suno output directories found for batch"}
            ok_dir = str(row[0] or row[2] or "").strip() or None
            alt_dir = str(row[1] or row[2] or "").strip() or None
            return {"ok": True, "okDir": ok_dir, "altDir": alt_dir}
    finally:
        conn.close()


def upsert_suno_task(cfg: DbCfg, task: dict) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into suno_tasks(
                    request_hash, song_uid, batch_id, track_no, model, title, style, instrumental,
                    task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir,
                    downloaded_ok, downloaded_alt, updated_at
                ) values (
                    %s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,
                    %s,%s, now()
                )
                on conflict (request_hash) do update set
                    song_uid = excluded.song_uid,
                    batch_id = excluded.batch_id,
                    track_no = coalesce(excluded.track_no, suno_tasks.track_no),
                    model = excluded.model,
                    title = excluded.title,
                    style = excluded.style,
                    instrumental = excluded.instrumental,
                    task_id = excluded.task_id,
                    status = excluded.status,
                    audio_url_ok = coalesce(nullif(excluded.audio_url_ok,''), suno_tasks.audio_url_ok),
                    audio_url_alt = coalesce(nullif(excluded.audio_url_alt,''), suno_tasks.audio_url_alt),
                    output_dir_ok = coalesce(nullif(excluded.output_dir_ok,''), suno_tasks.output_dir_ok),
                    output_dir_alt = coalesce(nullif(excluded.output_dir_alt,''), suno_tasks.output_dir_alt),
                    output_dir = coalesce(nullif(excluded.output_dir,''), suno_tasks.output_dir),
                    downloaded_ok = excluded.downloaded_ok,
                    downloaded_alt = excluded.downloaded_alt,
                    updated_at = now()
                """,
                (
                    str(task.get("requestHash", "") or "").strip(),
                    str(task.get("songUid", "") or "").strip(),
                    str(task.get("batchId", "") or "").strip(),
                    task.get("trackNo"),
                    str(task.get("model", "") or "").strip(),
                    str(task.get("title", "") or "").strip(),
                    str(task.get("style", "") or "").strip(),
                    bool(task.get("instrumental", False)),
                    str(task.get("taskId", "") or "").strip(),
                    str(task.get("status", "") or "").strip(),
                    str(task.get("audioUrlOk", "") or "").strip(),
                    str(task.get("audioUrlAlt", "") or "").strip(),
                    str(task.get("outputDirOk", "") or "").strip(),
                    str(task.get("outputDirAlt", "") or "").strip(),
                    str(task.get("outputDir", "") or "").strip(),
                    bool(task.get("downloadedOk", False)),
                    bool(task.get("downloadedAlt", False)),
                ),
            )
            conn.commit()
    finally:
        conn.close()


def list_suno_tasks_by_batch(cfg: DbCfg, batch_id: str) -> list[dict]:
    """List all suno tasks for a given batch_id."""
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, request_hash, song_uid, batch_id, track_no, model, title, style, instrumental,
                    task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir,
                    downloaded_ok, downloaded_alt, updated_at
                from suno_tasks
                where batch_id = %s
                  and task_id is not null
                  and task_id <> ''
                order by track_no asc, id asc
                """,
                (batch_id,),
            )
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": int(r[0]),
                    "requestHash": str(r[1] or ""),
                    "songUid": str(r[2] or ""),
                    "batchId": str(r[3] or ""),
                    "trackNo": int(r[4]) if r[4] is not None else None,
                    "model": str(r[5] or ""),
                    "title": str(r[6] or ""),
                    "style": str(r[7] or ""),
                    "instrumental": bool(r[8]),
                    "taskId": str(r[9] or ""),
                    "status": str(r[10] or ""),
                    "audioUrlOk": str(r[11] or ""),
                    "audioUrlAlt": str(r[12] or ""),
                    "outputDirOk": str(r[13] or ""),
                    "outputDirAlt": str(r[14] or ""),
                    "outputDir": str(r[15] or ""),
                    "downloadedOk": bool(r[16]),
                    "downloadedAlt": bool(r[17]),
                    "updatedAt": r[18].isoformat() if r[18] else "",
                })
            return out
    finally:
        conn.close()


def hide_batch(cfg: DbCfg, batch_id: str) -> dict:
    """Hide a batch: set hidden=true on all songs, delete files, delete image/suno records, then delete songs."""
    import shutil

    conn = connect_db(cfg, autocommit=True)
    try:
        # 1. Get batch metadata: output dirs, song uids, run date
        cur = conn.cursor()
        cur.execute(
            """
            select distinct s.output_dir_ok, s.output_dir_alt, s.batch_id, s.song_uid, s.profile_ok_id, s.profile_alt_id, s.run_date
            from songs s
            where s.batch_id = %s
            """,
            (batch_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return {"ok": False, "message": "Batch not found", "deleted_files": 0, "deleted_db_records": 0}

        ok_dir = str(rows[0][0] or "").strip()
        alt_dir = str(rows[0][1] or "").strip()
        song_uids = [str(r[3] or "").strip() for r in rows if str(r[3] or "").strip()]

        # 2. Delete output directories
        deleted_files = 0

        def _delete_dir(d: str) -> int:
            count = 0
            if d and Path(d).exists():
                try:
                    count = sum(len(files) for _, _, files in os.walk(d))
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass
            return count

        deleted_files += _delete_dir(ok_dir)
        deleted_files += _delete_dir(alt_dir)

        # 3. Delete image jobs for this batch
        cur.execute("delete from image_jobs where batch_id = %s", (batch_id,))
        deleted_db_records = max(0, cur.rowcount or 0)

        # 4. Delete suno tasks for this batch
        cur.execute("delete from suno_tasks where batch_id = %s", (batch_id,))
        deleted_db_records += max(0, cur.rowcount or 0)

        # 5. Delete history entries for songs in this batch
        if song_uids:
            cur.execute("delete from history where song_uid = any(%s)", (song_uids,))
            deleted_db_records += max(0, cur.rowcount or 0)

        # 6. Delete songs for this batch
        cur.execute("delete from songs where batch_id = %s", (batch_id,))
        deleted_db_records += max(0, cur.rowcount or 0)

        conn.commit()
        return {"ok": True, "message": "Batch hidden", "deleted_files": deleted_files, "deleted_db_records": deleted_db_records}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": str(exc), "deleted_files": 0, "deleted_db_records": 0}
    finally:
        conn.close()


def remap_suno_task_output_dirs(cfg: DbCfg, old_dir: str, new_dir: str) -> None:
    """Replace old output directory path with new one in suno_tasks rows."""
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update suno_tasks
                set output_dir_ok = replace(output_dir_ok, %s, %s),
                    output_dir_alt = replace(output_dir_alt, %s, %s)
                where output_dir_ok like %s or output_dir_alt like %s
                """,
                (old_dir, new_dir, old_dir, new_dir, f"{old_dir}%", f"{old_dir}%"),
            )
        conn.commit()
    finally:
        conn.close()


def list_pending_suno_tasks(cfg: DbCfg, limit: int = 40) -> list[dict]:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, request_hash, song_uid, batch_id, track_no, model, title, style, instrumental,
                    task_id, status, audio_url_ok, audio_url_alt, output_dir_ok, output_dir_alt, output_dir,
                    downloaded_ok, downloaded_alt, updated_at
                from suno_tasks
                where task_id is not null
                  and task_id <> ''
                  and (coalesce(downloaded_ok, false) = false or coalesce(downloaded_alt, false) = false)
                order by updated_at desc, id desc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": int(r[0]),
                    "requestHash": str(r[1] or ""),
                    "songUid": str(r[2] or ""),
                    "batchId": str(r[3] or ""),
                    "trackNo": int(r[4]) if r[4] is not None else None,
                    "model": str(r[5] or ""),
                    "title": str(r[6] or ""),
                    "style": str(r[7] or ""),
                    "instrumental": bool(r[8]),
                    "taskId": str(r[9] or ""),
                    "status": str(r[10] or ""),
                    "audioUrlOk": str(r[11] or ""),
                    "audioUrlAlt": str(r[12] or ""),
                    "outputDirOk": str(r[13] or ""),
                    "outputDirAlt": str(r[14] or ""),
                    "outputDir": str(r[15] or ""),
                    "downloadedOk": bool(r[16]),
                    "downloadedAlt": bool(r[17]),
                    "updatedAt": r[18].isoformat() if r[18] else "",
                })
            return out
    finally:
        conn.close()


def list_songs_by_batch_id(cfg: DbCfg, batch_id: str) -> list[dict]:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, song_uid, title, song_description, song_structure, language, creativity,
                    lyrics_raw, lyrics_polished, album, batch_id, batch_index,
                    run_date, profile_ok_id, profile_alt_id, status, created_at
                from songs
                where batch_id = %s
                order by batch_index asc, id asc
                """,
                (batch_id,),
            )
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": int(r[0]) if r[0] is not None else 0,
                    "songUid": str(r[1] or ""),
                    "title": str(r[2] or ""),
                    "song_description": str(r[3] or ""),
                    "song_structure": str(r[4] or ""),
                    "language": str(r[5] or ""),
                    "creativity": r[6],
                    "lyrics_raw": str(r[7] or ""),
                    "lyrics_polished": str(r[8] or ""),
                    "album": str(r[9] or ""),
                    "batchId": str(r[10] or ""),
                    "batchIndex": int(r[11]) if r[11] is not None else None,
                    "runDate": r[12].isoformat() if r[12] else "",
                    "profileOkId": str(r[13] or ""),
                    "profileAltId": str(r[14] or ""),
                    "status": str(r[15] or ""),
                    "createdAt": r[16].isoformat() if r[16] else "",
                })
            return out
    finally:
        conn.close()


def count_songs_by_batch_id(cfg: DbCfg, batch_id: str) -> int:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from songs where batch_id = %s",
                (batch_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


def count_songs_by_batch_ids(cfg: DbCfg, batch_ids: list[str]) -> dict[str, int]:
    if not batch_ids:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(batch_ids))
            cur.execute(
                f"select batch_id, count(*) from songs where batch_id in ({placeholders}) group by batch_id",
                tuple(batch_ids),
            )
            rows = cur.fetchall()
            return {str(r[0]): int(r[1]) for r in rows}
    finally:
        conn.close()


def song_time_ranges_by_batch_ids(cfg: DbCfg, batch_ids: list[str]) -> dict[str, dict]:
    if not batch_ids:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(batch_ids))
            cur.execute(
                f"select batch_id, min(created_at), max(created_at) from songs where batch_id in ({placeholders}) group by batch_id",
                tuple(batch_ids),
            )
            rows = cur.fetchall()
            out: dict[str, dict] = {}
            for r in rows:
                bid = str(r[0] or "")
                mn = r[1].isoformat() if r[1] else ""
                mx = r[2].isoformat() if r[2] else ""
                out[bid] = {"minCreatedAt": mn, "maxCreatedAt": mx}
            for bid in batch_ids:
                if bid not in out:
                    out[bid] = {"minCreatedAt": "", "maxCreatedAt": ""}
            return out
    finally:
        conn.close()


def _normalized_abs_path(value: str) -> str:
    """Normalize a path for reliable comparison across mixed separators."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if os.name == 'nt':
            text = text.replace('/', '\\')
        result = os.path.normcase(os.path.abspath(text))
        # Ensure trailing separator consistency (e.g., "d:\" stays, "d:\foo" doesn't end with \)
        if result.endswith(os.sep) and len(result) > 3:
            result = result.rstrip(os.sep)
        return result
    except Exception:
        raw = str(value or "").strip()
        if os.name == 'nt':
            raw = raw.replace('/', '\\')
        return os.path.normcase(raw)


def _rebase_path_if_under_base(path_value: str, old_base_dir: str, new_base_dir: str) -> str:
    raw_path = str(path_value or "").strip()
    old_base = str(old_base_dir or "").strip()
    new_base = str(new_base_dir or "").strip()
    if not raw_path or not old_base or not new_base:
        return raw_path
    old_norm = _normalized_abs_path(old_base)
    new_norm = _normalized_abs_path(new_base)
    path_norm = _normalized_abs_path(raw_path)
    if not old_norm or not new_norm or not path_norm or old_norm == new_norm:
        return raw_path
    try:
        common = os.path.commonpath([path_norm, old_norm])
    except Exception:
        return raw_path
    if common != old_norm:
        return raw_path
    try:
        rel_path = os.path.relpath(raw_path, old_base)
    except Exception:
        try:
            rel_path = os.path.relpath(path_norm, old_norm)
        except Exception:
            return raw_path
    if rel_path in ("", "."):
        return new_base
    return str(os.path.normpath(os.path.join(new_base, rel_path)))


def remap_pending_suno_output_dirs(cfg: DbCfg, *, old_base_dir: str, new_base_dir: str) -> dict[str, int | bool]:
    old_base = str(old_base_dir or "").strip()
    new_base = str(new_base_dir or "").strip()
    if not old_base or not new_base:
        return {"ok": True, "taskRowsUpdated": 0, "batchRowsUpdated": 0}
    if _normalized_abs_path(old_base) == _normalized_abs_path(new_base):
        return {"ok": True, "taskRowsUpdated": 0, "batchRowsUpdated": 0}

    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, output_dir_ok, output_dir_alt, output_dir, batch_id
                from suno_tasks
                where task_id is not null
                  and task_id <> ''
                  and (coalesce(downloaded_ok, false) = false or coalesce(downloaded_alt, false) = false)
                  and coalesce(status, '') not in ('CREATE_TASK_FAILED','GENERATE_AUDIO_FAILED')
                """
            )
            pending_rows = cur.fetchall()
            task_updates: list[tuple[str | None, str | None, str | None, int]] = []
            pending_batch_ids: set[str] = set()
            for row in pending_rows:
                row_id = int(row[0])
                ok_dir = str(row[1] or row[3] or "").strip() or None
                alt_dir = str(row[2] or row[3] or "").strip() or None
                legacy_dir = str(row[3] or "").strip() or None
                batch_id = str(row[4] or "").strip()
                rebased_ok = _rebase_path_if_under_base(ok_dir, old_base, new_base) if ok_dir else None
                rebased_alt = _rebase_path_if_under_base(alt_dir, old_base, new_base) if alt_dir else None
                rebased_legacy = _rebase_path_if_under_base(legacy_dir, old_base, new_base) if legacy_dir else None
                if rebased_ok != ok_dir or rebased_alt != alt_dir or rebased_legacy != legacy_dir:
                    task_updates.append((rebased_ok, rebased_alt, rebased_legacy, row_id))
                    if batch_id:
                        pending_batch_ids.add(batch_id)
            for ok_dir, alt_dir, legacy_dir, row_id in task_updates:
                cur.execute(
                    """
                    update suno_tasks
                    set output_dir_ok = %s,
                        output_dir_alt = %s,
                        output_dir = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (ok_dir, alt_dir, legacy_dir, row_id),
                )

            batch_rows_updated = 0
            if pending_batch_ids:
                placeholders = ", ".join(["%s"] * len(pending_batch_ids))
                cur.execute(
                    f"select batch_id, ok_dir, alt_dir from batch_run_dirs where batch_id in ({placeholders})",
                    tuple(pending_batch_ids),
                )
                batch_rows = cur.fetchall()
                for br in batch_rows:
                    bid = str(br[0] or "")
                    old_ok = str(br[1] or "").strip()
                    old_alt = str(br[2] or "").strip()
                    new_ok = _rebase_path_if_under_base(old_ok, old_base, new_base) if old_ok else old_ok
                    new_alt = _rebase_path_if_under_base(old_alt, old_base, new_base) if old_alt else old_alt
                    if new_ok != old_ok or new_alt != old_alt:
                        cur.execute(
                            "update batch_run_dirs set ok_dir = %s, alt_dir = %s, updated_at = now() where batch_id = %s",
                            (new_ok, new_alt, bid),
                        )
                        batch_rows_updated += 1

            conn.commit()
            return {
                "ok": True,
                "taskRowsUpdated": len(task_updates),
                "batchRowsUpdated": batch_rows_updated,
            }
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": str(exc), "taskRowsUpdated": 0, "batchRowsUpdated": 0}
    finally:
        conn.close()


def remap_all_batch_run_dirs(cfg: DbCfg, *, old_base_dir: str, new_base_dir: str) -> dict[str, int | bool]:
    """Remap ALL batch_run_dirs entries from old base to new base, regardless of task status."""
    old_base = str(old_base_dir or "").strip()
    new_base = str(new_base_dir or "").strip()
    if not old_base or not new_base:
        return {"ok": True, "rowsUpdated": 0}
    if _normalized_abs_path(old_base) == _normalized_abs_path(new_base):
        return {"ok": True, "rowsUpdated": 0}

    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("select batch_id, ok_dir, alt_dir from batch_run_dirs")
            rows = cur.fetchall()
            updates: list[tuple[str, str, str]] = []
            for r in rows:
                bid = str(r[0] or "")
                old_ok = str(r[1] or "").strip()
                old_alt = str(r[2] or "").strip()
                new_ok = _rebase_path_if_under_base(old_ok, old_base, new_base) if old_ok else old_ok
                new_alt = _rebase_path_if_under_base(old_alt, old_base, new_base) if old_alt else old_alt
                if new_ok != old_ok or new_alt != old_alt:
                    updates.append((new_ok, new_alt, bid))
            for new_ok, new_alt, bid in updates:
                cur.execute(
                    "update batch_run_dirs set ok_dir = %s, alt_dir = %s, updated_at = now() where batch_id = %s",
                    (new_ok, new_alt, bid),
                )
            conn.commit()
            return {"ok": True, "rowsUpdated": len(updates)}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": str(exc), "rowsUpdated": 0}
    finally:
        conn.close()


def relocate_batch_output_dir(cfg: DbCfg, *, batch_id: str, old_dir: str, new_dir: str) -> dict:
    """Rewrite all DB path references for one batch's output directory.

    Rebases any stored path that lives under ``old_dir`` to the same relative
    location under ``new_dir`` across ``batch_run_dirs``, ``suno_tasks`` and
    ``image_jobs`` — all in a single transaction. This does NOT move files on
    disk; the caller must move the folder first.

    Returns ``{"ok": bool, "updated": int, "message": str}``.
    """
    batch_id = str(batch_id or "").strip()
    old_dir = str(old_dir or "").strip()
    new_dir = str(new_dir or "").strip()
    if not batch_id or not old_dir or not new_dir:
        return {"ok": False, "message": "Missing batch_id / old_dir / new_dir", "updated": 0}
    if _normalized_abs_path(old_dir) == _normalized_abs_path(new_dir):
        return {"ok": True, "message": "Source and destination are identical", "updated": 0}

    conn = connect_db(cfg)
    updated = 0
    try:
        with conn.cursor() as cur:
            # 1. batch_run_dirs (primary source the converter reads)
            cur.execute("select ok_dir, alt_dir from batch_run_dirs where batch_id = %s", (batch_id,))
            row = cur.fetchone()
            if row:
                old_ok = str(row[0] or "").strip()
                old_alt = str(row[1] or "").strip()
                new_ok = _rebase_path_if_under_base(old_ok, old_dir, new_dir) if old_ok else old_ok
                new_alt = _rebase_path_if_under_base(old_alt, old_dir, new_dir) if old_alt else old_alt
                if new_ok != old_ok or new_alt != old_alt:
                    cur.execute(
                        "update batch_run_dirs set ok_dir = %s, alt_dir = %s, updated_at = now() where batch_id = %s",
                        (new_ok, new_alt, batch_id),
                    )
                    updated += 1

            # 2. suno_tasks (fallback dirs + suno poll)
            cur.execute(
                "select id, output_dir_ok, output_dir_alt, output_dir from suno_tasks where batch_id = %s",
                (batch_id,),
            )
            for r in cur.fetchall():
                rid = int(r[0])
                o_ok, o_alt, o_leg = (str(r[1] or "").strip(), str(r[2] or "").strip(), str(r[3] or "").strip())
                n_ok = _rebase_path_if_under_base(o_ok, old_dir, new_dir) if o_ok else o_ok
                n_alt = _rebase_path_if_under_base(o_alt, old_dir, new_dir) if o_alt else o_alt
                n_leg = _rebase_path_if_under_base(o_leg, old_dir, new_dir) if o_leg else o_leg
                if (n_ok, n_alt, n_leg) != (o_ok, o_alt, o_leg):
                    cur.execute(
                        "update suno_tasks set output_dir_ok = %s, output_dir_alt = %s, output_dir = %s, updated_at = now() where id = %s",
                        (n_ok, n_alt, n_leg, rid),
                    )
                    updated += 1

            # 3. image_jobs (background / thumbnail file locations)
            cur.execute(
                "select id, output_image_path, input_image_path from image_jobs where batch_id = %s",
                (batch_id,),
            )
            for r in cur.fetchall():
                rid = int(r[0])
                o_out, o_in = (str(r[1] or "").strip(), str(r[2] or "").strip())
                n_out = _rebase_path_if_under_base(o_out, old_dir, new_dir) if o_out else o_out
                n_in = _rebase_path_if_under_base(o_in, old_dir, new_dir) if o_in else o_in
                if (n_out, n_in) != (o_out, o_in):
                    cur.execute(
                        "update image_jobs set output_image_path = %s, input_image_path = %s, updated_at = now() where id = %s",
                        (n_out, n_in, rid),
                    )
                    updated += 1

        conn.commit()
        return {"ok": True, "updated": updated, "message": ""}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "message": str(exc), "updated": 0}
    finally:
        conn.close()


def get_batch_run_dirs_by_batch_id(cfg: DbCfg, batch_id: str) -> dict:
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select ok_dir, alt_dir from batch_run_dirs where batch_id = %s",
                (batch_id,),
            )
            row = cur.fetchone()
            if row:
                return {"okDir": str(row[0] or ""), "altDir": str(row[1] or "")}
            return {"okDir": "", "altDir": ""}
    finally:
        conn.close()


def get_batch_run_dirs_by_batch_ids(cfg: DbCfg, batch_ids: list[str]) -> dict[str, dict]:
    if not batch_ids:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(batch_ids))
            cur.execute(
                f"select batch_id, ok_dir, alt_dir from batch_run_dirs where batch_id in ({placeholders})",
                tuple(batch_ids),
            )
            rows = cur.fetchall()
            out: dict[str, dict] = {}
            for r in rows:
                bid = str(r[0] or "")
                out[bid] = {"okDir": str(r[1] or ""), "altDir": str(r[2] or "")}
            for bid in batch_ids:
                if bid not in out:
                    out[bid] = {"okDir": "", "altDir": ""}
            return out
    finally:
        conn.close()


def get_latest_suno_output_dirs_by_batch_ids(cfg: DbCfg, batch_ids: list[str]) -> dict[str, dict]:
    if not batch_ids:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(batch_ids))
            cur.execute(
                f"""
                select distinct on (batch_id) batch_id, output_dir_ok, output_dir_alt, output_dir
                from suno_tasks
                where batch_id in ({placeholders})
                order by batch_id, updated_at desc, id desc
                """,
                tuple(batch_ids),
            )
            rows = cur.fetchall()
            out: dict[str, dict] = {}
            for r in rows:
                bid = str(r[0] or "")
                ok_dir = str(r[1] or r[3] or "")
                alt_dir = str(r[2] or r[3] or "")
                out[bid] = {"okDir": ok_dir, "altDir": alt_dir}
            for bid in batch_ids:
                if bid not in out:
                    out[bid] = {"okDir": "", "altDir": ""}
            return out
    finally:
        conn.close()


def upsert_batch_run_dirs(cfg: DbCfg, *, batch_id: str, ok_dir: str, alt_dir: str = "") -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into batch_run_dirs(batch_id, ok_dir, alt_dir, created_at, updated_at)
                values (%s, %s, %s, now(), now())
                on conflict (batch_id) do update set
                    ok_dir = excluded.ok_dir,
                    alt_dir = excluded.alt_dir,
                    updated_at = now()
                """,
                (batch_id, ok_dir, alt_dir),
            )
            conn.commit()
    finally:
        conn.close()


def find_batch_by_output_dir(cfg: DbCfg, output_dir: str) -> dict:
    """Find batch_id and profile IDs given an output directory path.

    Searches batch_run_dirs for a matching ok_dir or alt_dir, then retrieves
    profile_ok_id and profile_alt_id from the songs table.

    Returns dict with keys: batchId, profileOkId, profileAltId, role.
    Returns empty dict if no match found.
    """
    d = str(output_dir or "").strip().replace("\\", "/").rstrip("/")
    if not d:
        return {}
    conn = connect_db(cfg, autocommit=True)
    try:
        with conn.cursor() as cur:
            # Try to match against batch_run_dirs (ok_dir or alt_dir)
            cur.execute(
                """
                select batch_id, ok_dir, alt_dir from batch_run_dirs
                where replace(ok_dir, '\\', '/') = %s
                   or replace(alt_dir, '\\', '/') = %s
                limit 1
                """,
                (d, d),
            )
            row = cur.fetchone()
            if not row:
                return {}
            batch_id = str(row[0] or "").strip()
            ok_dir_val = str(row[1] or "").strip().replace("\\", "/").rstrip("/")
            alt_dir_val = str(row[2] or "").strip().replace("\\", "/").rstrip("/")
            role = "OK" if d == ok_dir_val else "ALT"

            # Get profile IDs from songs table
            cur.execute(
                """
                select profile_ok_id, profile_alt_id
                from songs
                where batch_id = %s
                limit 1
                """,
                (batch_id,),
            )
            song_row = cur.fetchone()
            profile_ok_id = str(song_row[0] or "").strip() if song_row else ""
            profile_alt_id = str(song_row[1] or "").strip() if song_row else ""

            return {
                "batchId": batch_id,
                "profileOkId": profile_ok_id,
                "profileAltId": profile_alt_id,
                "role": role,
            }
    finally:
        conn.close()
