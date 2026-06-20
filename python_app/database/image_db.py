from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from ..utils.music_common import connect_db
from .persistence import DbCfg


def upsert_image_job(cfg: DbCfg, job: dict) -> dict:
    conn = connect_db(cfg)
    try:
        batch_id = str(job.get("batchId", "")).strip()
        profile_id = str(job.get("profileId", "")).strip()
        kind = str(job.get("kind", "")).strip()
        if not batch_id or not profile_id or not kind:
            raise ValueError("Missing batchId/profileId/kind")
        job_uid = str(job.get("jobUid", "")).strip() or f"img-{batch_id}-{profile_id}-{kind}"
        status = str(job.get("status", "PENDING")).strip() or "PENDING"
        prompt = str(job.get("prompt", "")).strip()
        prompt_source = str(job.get("promptSource", "")).strip()
        run_date = str(job.get("runDate", "")).strip() or None
        pair_index = int(job.get("pairIndex", 0) or 0)
        channel_role = str(job.get("channelRole", "")).strip()
        sample_paths = [str(x).strip() for x in list(job.get("samplePaths") or []) if str(x).strip()]
        input_image_path = str(job.get("inputImagePath", "")).strip()
        output_image_path = str(job.get("outputImagePath", "")).strip()
        error = str(job.get("error", "")).strip()
        attempt_count = int(job.get("attemptCount", 0) or 0)
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into image_jobs(
                    job_uid, batch_id, run_date, pair_index, profile_id, channel_role,
                    kind, status, prompt, prompt_source, sample_paths, input_image_path,
                    output_image_path, error, attempt_count, updated_at
                )
                values(%s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, now())
                on conflict (batch_id, profile_id, kind) do update set
                    job_uid = excluded.job_uid,
                    run_date = excluded.run_date,
                    pair_index = excluded.pair_index,
                    channel_role = excluded.channel_role,
                    status = excluded.status,
                    prompt = excluded.prompt,
                    prompt_source = excluded.prompt_source,
                    sample_paths = excluded.sample_paths,
                    input_image_path = excluded.input_image_path,
                    output_image_path = excluded.output_image_path,
                    error = excluded.error,
                    attempt_count = excluded.attempt_count,
                    updated_at = now()
                returning id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                          prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                          attempt_count, created_at, updated_at
                """,
                (
                    job_uid,
                    batch_id,
                    run_date,
                    pair_index,
                    profile_id,
                    channel_role,
                    kind,
                    status,
                    prompt,
                    prompt_source,
                    json.dumps(sample_paths),
                    input_image_path,
                    output_image_path,
                    error,
                    attempt_count,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return _row_to_image_job(row)
    finally:
        conn.close()


def _row_to_image_job(row: Any) -> dict:
    if not row:
        return {}
    raw_sample_paths = row[11]
    sample_paths: list[str] = []
    try:
        if raw_sample_paths is None:
            sample_paths = []
        elif isinstance(raw_sample_paths, str):
            sample_paths = json.loads(raw_sample_paths or "[]") or []
        elif isinstance(raw_sample_paths, list):
            sample_paths = raw_sample_paths
        else:
            sample_paths = json.loads(str(raw_sample_paths) or "[]") or []
    except Exception:
        sample_paths = []
    return {
        "id": int(row[0]),
        "jobUid": str(row[1] or ""),
        "batchId": str(row[2] or ""),
        "runDate": str(row[3] or ""),
        "pairIndex": int(row[4]) if row[4] is not None else 0,
        "profileId": str(row[5] or ""),
        "channelRole": str(row[6] or ""),
        "kind": str(row[7] or ""),
        "status": str(row[8] or ""),
        "prompt": str(row[9] or ""),
        "promptSource": str(row[10] or ""),
        "samplePaths": [str(x).strip() for x in (sample_paths or []) if str(x).strip()],
        "inputImagePath": str(row[12] or ""),
        "outputImagePath": str(row[13] or ""),
        "error": str(row[14] or ""),
        "attemptCount": int(row[15]) if row[15] is not None else 0,
        "createdAt": str(row[16] or ""),
        "updatedAt": str(row[17] or ""),
    }


def list_image_jobs(cfg: DbCfg, *, from_ymd: str = "", to_ymd: str = "", limit: int = 5000) -> list[dict]:
    from_text = str(from_ymd or "").strip()
    to_text = str(to_ymd or "").strip()
    safe_limit = max(1, min(20000, int(limit or 5000)))
    where_parts: list[str] = []
    params: list[object] = []
    if from_text:
        where_parts.append("(run_date is not null and run_date >= %s::date)")
        params.append(from_text)
    if to_text:
        where_parts.append("(run_date is not null and run_date <= %s::date)")
        params.append(to_text)
    where_sql = (" where " + " and ".join(where_parts)) if where_parts else ""
    params.append(safe_limit)
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                       prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                       attempt_count, created_at, updated_at
                from image_jobs
                {where_sql}
                order by run_date desc nulls last, updated_at desc, id desc
                limit %s
                """,
                tuple(params),
            )
            return [_row_to_image_job(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_pending_image_jobs(cfg: DbCfg, limit: int = 10, *, stale_running_sec: int = 600) -> list[dict]:
    safe_limit = max(1, min(50, int(limit or 10)))
    stale_sec = max(30, min(24 * 3600, int(stale_running_sec or 600)))
    threshold = datetime.utcnow() - timedelta(seconds=stale_sec)
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                       prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                       attempt_count, created_at, updated_at
                from image_jobs
                where status = 'PENDING'
                   or (status = 'RUNNING' and (updated_at is null or updated_at < %s))
                order by updated_at asc nulls first, id asc
                limit %s
                """,
                (threshold, safe_limit),
            )
            return [_row_to_image_job(row) for row in cur.fetchall()]
    finally:
        conn.close()


def claim_pending_image_jobs(
    cfg: DbCfg,
    limit: int = 8,
    *,
    stale_running_sec: int = 600,
    max_running: int = 4,
) -> list[dict]:
    safe_limit = max(1, min(50, int(limit or 8)))
    stale_sec = max(30, min(24 * 3600, int(stale_running_sec or 600)))
    threshold = datetime.utcnow() - timedelta(seconds=stale_sec)
    max_run = max(1, min(50, int(max_running or 4)))
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select count(*) from image_jobs where status = 'RUNNING' and updated_at is not null and updated_at >= %s",
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
                    from image_jobs
                    where status = 'PENDING'
                       or (status = 'RUNNING' and (updated_at is null or updated_at < %s))
                    order by
                        case when lower(kind) = 'background' then 0 else 1 end,
                        updated_at asc nulls first,
                        id asc
                    for update skip locked
                    limit %s
                )
                update image_jobs
                set status='RUNNING', error='', updated_at=now()
                where id in (select id from cte)
                returning id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                          prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                          attempt_count, created_at, updated_at
                """,
                (threshold, safe_limit),
            )
            rows = cur.fetchall()
        conn.commit()
        return [_row_to_image_job(row) for row in rows]
    finally:
        conn.close()


def get_image_job_by_key(cfg: DbCfg, *, batch_id: str, profile_id: str, kind: str) -> dict | None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                       prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                       attempt_count, created_at, updated_at
                from image_jobs
                where batch_id=%s and profile_id=%s and kind=%s
                limit 1
                """,
                (str(batch_id or "").strip(), str(profile_id or "").strip(), str(kind or "").strip()),
            )
            row = cur.fetchone()
            return _row_to_image_job(row) if row else None
    finally:
        conn.close()


def get_existing_thumbnail_prompts_for_batch(cfg: DbCfg, *, batch_id: str) -> list[str]:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select prompt
                from image_jobs
                where batch_id=%s and kind='thumbnail' and prompt is not null and prompt <> ''
                """,
                (str(batch_id or "").strip(),),
            )
            return [str(row[0] or "").strip() for row in cur.fetchall() if str(row[0] or "").strip()]
    finally:
        conn.close()


def get_used_thumb_samples_for_batch(cfg: DbCfg, *, batch_id: str) -> list[str]:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct sp.value
                from image_jobs ij
                join image_random_history sp on sp.value = any(ij.sample_paths)
                where ij.batch_id=%s and ij.kind='thumbnail' and sp.kind='thumb_sample'
                """,
                (str(batch_id or "").strip(),),
            )
            return [str(row[0] or "").strip() for row in cur.fetchall() if str(row[0] or "").strip()]
    finally:
        conn.close()


def mark_image_job_running(cfg: DbCfg, job_uid: str) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set status='RUNNING', error='', updated_at=now() where job_uid=%s and status <> 'CANCELLED'",
                (str(job_uid or "").strip(),),
            )
        conn.commit()
    finally:
        conn.close()


def mark_image_job_ready(cfg: DbCfg, job_uid: str, *, output_image_path: str) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set status='READY', output_image_path=%s, error='', updated_at=now() where job_uid=%s and status <> 'CANCELLED'",
                (str(output_image_path or "").strip(), str(job_uid or "").strip()),
            )
        conn.commit()
    finally:
        conn.close()


def mark_image_job_failed(cfg: DbCfg, job_uid: str, *, error: str) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set status='FAILED', error=%s, updated_at=now() where job_uid=%s and status <> 'CANCELLED'",
                (str(error or "").strip(), str(job_uid or "").strip()),
            )
        conn.commit()
    finally:
        conn.close()


def mark_image_job_pending(cfg: DbCfg, job_uid: str, *, error: str = "") -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set status='PENDING', error=%s, updated_at=now() where job_uid=%s and status <> 'CANCELLED'",
                (str(error or "").strip(), str(job_uid or "").strip()),
            )
        conn.commit()
    finally:
        conn.close()


def mark_image_job_cancelled(cfg: DbCfg, job_uid: str, *, reason: str = "Cancelled by user") -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set status='CANCELLED', error=%s, updated_at=now() where job_uid=%s",
                (str(reason or "Cancelled by user").strip(), str(job_uid or "").strip()),
            )
        conn.commit()
    finally:
        conn.close()


def cancel_image_jobs_for_row(cfg: DbCfg, *, batch_id: str, profile_id: str, reason: str = "Cancelled by user") -> int:
    bid = str(batch_id or "").strip()
    pid = str(profile_id or "").strip()
    if not bid or not pid:
        return 0
    msg = str(reason or "Cancelled by user").strip()
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update image_jobs
                set status='CANCELLED',
                    error=%s,
                    updated_at=now()
                where batch_id=%s
                  and profile_id=%s
                  and kind in ('background', 'thumbnail')
                  and status in ('PENDING', 'RUNNING')
                """,
                (msg, bid, pid),
            )
            affected = int(cur.rowcount or 0)
        conn.commit()
        return affected
    finally:
        conn.close()


def cancel_all_pending_image_jobs(cfg: DbCfg, *, reason: str = "Cancelled by user") -> int:
    msg = str(reason or "Cancelled by user").strip()
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update image_jobs
                set status='CANCELLED',
                    error=%s,
                    updated_at=now()
                where status in ('PENDING', 'RUNNING')
                """,
                (msg,),
            )
            affected = int(cur.rowcount or 0)
        conn.commit()
        return affected
    finally:
        conn.close()


def reset_image_job_for_retry(cfg: DbCfg, job_uid: str) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update image_jobs
                set status='PENDING',
                    error='',
                    attempt_count=0,
                    output_image_path='',
                    sample_paths='[]'::jsonb,
                    updated_at=now()
                where job_uid=%s
                """,
                (str(job_uid or "").strip()),
            )
        conn.commit()
    finally:
        conn.close()


def bump_image_job_attempt(cfg: DbCfg, job_uid: str) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set attempt_count=attempt_count+1, updated_at=now() where job_uid=%s",
                (str(job_uid or "").strip(),),
            )
        conn.commit()
    finally:
        conn.close()


def list_image_jobs_for_batch(cfg: DbCfg, *, batch_id: str, profile_ids: list[str]) -> list[dict]:
    key = str(batch_id or "").strip()
    ids = [str(x).strip() for x in (profile_ids or []) if str(x).strip()]
    if not key or not ids:
        return []
    placeholders = ", ".join(["%s"] * len(ids))
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                       prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                       attempt_count, created_at, updated_at
                from image_jobs
                where batch_id=%s
                  and profile_id in ({placeholders})
                  and kind in ('background', 'thumbnail')
                """,
                tuple([key] + ids),
            )
            return [_row_to_image_job(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_image_jobs_for_batches(cfg: DbCfg, *, batch_ids: list[str], profile_ids: list[str]) -> list[dict]:
    batches = [str(x).strip() for x in (batch_ids or []) if str(x).strip()]
    profiles = [str(x).strip() for x in (profile_ids or []) if str(x).strip()]
    if not batches or not profiles:
        return []
    batch_placeholders = ", ".join(["%s"] * len(batches))
    profile_placeholders = ", ".join(["%s"] * len(profiles))
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                       prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                       attempt_count, created_at, updated_at
                from image_jobs
                where batch_id in ({batch_placeholders})
                  and profile_id in ({profile_placeholders})
                  and kind in ('background', 'thumbnail')
                """,
                tuple([*batches, *profiles]),
            )
            return [_row_to_image_job(row) for row in cur.fetchall()]
    finally:
        conn.close()


def retry_image_job(cfg: DbCfg, job_uid: str) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "update image_jobs set status='PENDING', error='', attempt_count=0, output_image_path='', updated_at=now() where job_uid=%s",
                (str(job_uid or "").strip(),),
            )
        conn.commit()
    finally:
        conn.close()


def clear_all_image_jobs(cfg: DbCfg) -> None:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("truncate table image_jobs")
        conn.commit()
    finally:
        conn.close()


def get_ready_background_output(cfg: DbCfg, *, batch_id: str, profile_id: str) -> str:
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select output_image_path
                from image_jobs
                where batch_id=%s and profile_id=%s and kind='background' and status='READY'
                order by updated_at desc, id desc
                limit 1
                """,
                (str(batch_id or "").strip(), str(profile_id or "").strip()),
            )
            row = cur.fetchone()
            path = str(row[0] or "").strip() if row else ""
            if path:
                return path
            cur.execute("select image_config from profiles where uid=%s", (str(profile_id or "").strip(),))
            prow = cur.fetchone()
            image_cfg = prow[0] if prow else {}
            if isinstance(image_cfg, str):
                try:
                    image_cfg = json.loads(image_cfg or "{}")
                except Exception:
                    image_cfg = {}
            mode = str((image_cfg or {}).get("mode", "")).strip().lower().replace("-", "_") if isinstance(image_cfg, dict) else ""
            if mode != "thumb_only":
                return ""
            cur.execute(
                """
                select output_image_path
                from image_jobs
                where batch_id=%s and profile_id=%s and kind='thumbnail' and status='READY'
                order by updated_at desc, id desc
                limit 1
                """,
                (str(batch_id or "").strip(), str(profile_id or "").strip()),
            )
            row = cur.fetchone()
            return str(row[0] or "").strip() if row else ""
    finally:
        conn.close()


def list_prompt_presets(cfg: DbCfg, *, kind: str) -> list[dict]:
    k = str(kind or "").strip() or "background"
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, kind, name, prompt, used_count, used_at
                from image_prompt_presets
                where kind=%s
                order by name asc, id asc
                """,
                (k,),
            )
            out: list[dict] = []
            for row in cur.fetchall():
                out.append(
                    {
                        "id": int(row[0]),
                        "kind": str(row[1] or ""),
                        "name": str(row[2] or ""),
                        "prompt": str(row[3] or ""),
                        "usedCount": int(row[4] or 0),
                        "usedAt": str(row[5] or ""),
                    }
                )
            return out
    finally:
        conn.close()


def upsert_prompt_preset(cfg: DbCfg, *, preset_id: int | None, kind: str, name: str, prompt: str) -> dict:
    k = str(kind or "").strip() or "background"
    n = str(name or "").strip()
    p = str(prompt or "").strip()
    if not n or not p:
        raise ValueError("Preset name and prompt are required")
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            if preset_id is not None and int(preset_id) > 0:
                cur.execute(
                    """
                    update image_prompt_presets
                    set kind=%s, name=%s, prompt=%s
                    where id=%s
                    returning id, kind, name, prompt, used_count, used_at
                    """,
                    (k, n, p, int(preset_id)),
                )
            else:
                cur.execute(
                    """
                    insert into image_prompt_presets(kind, name, prompt)
                    values(%s, %s, %s)
                    on conflict (kind, name) do update set prompt=excluded.prompt
                    returning id, kind, name, prompt, used_count, used_at
                    """,
                    (k, n, p),
                )
            row = cur.fetchone()
        conn.commit()
        if not row:
            raise RuntimeError("Preset save failed")
        return {
            "id": int(row[0]),
            "kind": str(row[1] or ""),
            "name": str(row[2] or ""),
            "prompt": str(row[3] or ""),
            "usedCount": int(row[4] or 0),
            "usedAt": str(row[5] or ""),
        }
    finally:
        conn.close()


def delete_prompt_preset(cfg: DbCfg, preset_id: int) -> None:
    pid = int(preset_id or 0)
    if pid <= 0:
        return
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("delete from image_prompt_presets where id=%s", (pid,))
        conn.commit()
    finally:
        conn.close()


def get_image_job_by_uid(cfg: DbCfg, job_uid: str) -> dict | None:
    uid = str(job_uid or "").strip()
    if not uid:
        return None
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, job_uid, batch_id, run_date, pair_index, profile_id, channel_role, kind, status,
                       prompt, prompt_source, sample_paths, input_image_path, output_image_path, error,
                       attempt_count, created_at, updated_at
                from image_jobs
                where job_uid=%s
                """,
                (uid,),
            )
            row = cur.fetchone()
            return _row_to_image_job(row) if row else None
    finally:
        conn.close()


def pick_least_used_preset(cfg: DbCfg, *, kind: str, exclude_ids: list[int] | None = None) -> dict | None:
    k = str(kind or "").strip() or "background"
    exclude = [int(x) for x in (exclude_ids or []) if x]
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            exclude_clause = " and id <> all(%s)" if exclude else ""
            params: tuple = (k,) if not exclude else (k, exclude)
            cur.execute(
                f"""
                select id, name, prompt
                from image_prompt_presets
                where kind=%s{exclude_clause}
                order by used_count asc, used_at asc nulls first, id asc
                limit 1
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                return None
            preset_id = int(row[0])
            name = str(row[1] or "")
            prompt = str(row[2] or "")
            cur.execute(
                "update image_prompt_presets set used_count=used_count+1, used_at=now() where id=%s",
                (preset_id,),
            )
        conn.commit()
        return {"id": preset_id, "kind": k, "name": name, "prompt": prompt}
    finally:
        conn.close()


def pick_least_used_value(cfg: DbCfg, *, kind: str, values: list[str], exclude: list[str] | None = None) -> str:
    k = str(kind or "").strip()
    candidates = [str(x).strip() for x in (values or []) if str(x).strip()]
    excluded = {str(x).strip() for x in (exclude or []) if str(x).strip()}
    if excluded:
        candidates = [v for v in candidates if v not in excluded]
    if not k or not candidates:
        return (values[0] if values else "") if not excluded else ""
    conn = connect_db(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select value, used_count, used_at
                from image_random_history
                where kind=%s and value = any(%s)
                """,
                (k, candidates),
            )
            stats = {str(row[0] or ""): {"used": int(row[1] or 0), "at": row[2]} for row in cur.fetchall()}
            best = None
            best_used = None
            best_at = None
            for v in candidates:
                row = stats.get(v)
                used = int(row["used"]) if row else 0
                used_at = row["at"] if row else None
                if best is None or used < int(best_used or 0) or (used == int(best_used or 0) and (best_at is None or (used_at is not None and used_at < best_at))):
                    best = v
                    best_used = used
                    best_at = used_at
            chosen = str(best or candidates[0]).strip()
            cur.execute(
                """
                insert into image_random_history(kind, value, used_count, used_at)
                values(%s, %s, 1, now())
                on conflict (kind, value) do update set
                    used_count = image_random_history.used_count + 1,
                    used_at = now()
                """,
                (k, chosen),
            )
        conn.commit()
        return chosen
    finally:
        conn.close()
