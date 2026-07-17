"""Readable progress logging for split draft / batch generation."""

from __future__ import annotations

import logging

from platform_api.terminal_log import emit

logger = logging.getLogger("platform_api.music")


def _emit(level: int, message: str, *args: object) -> None:
    emit("music", message, *args, level=level)


def _progress(message: str, *args: object) -> None:
    _emit(logging.INFO, message, *args)


def _progress_warn(message: str, *args: object) -> None:
    _emit(logging.WARNING, message, *args)


def _batch_label(batch_id: str | None) -> str:
    text = str(batch_id or "").strip()
    return text[:8] if text else "—"


def _song_label(song_number: int | None) -> str:
    if song_number is None:
        return "—"
    return f"#{int(song_number)}"


def log_batch_created(
    *,
    batch_id: str,
    user_id: str,
    song_count: int,
    total_cost: str,
) -> None:
    _progress(
        "[batch %s] Created for user %s with %d song(s). Reserved %s.",
        _batch_label(batch_id),
        user_id,
        song_count,
        total_cost,
    )


def log_batch_execution_started(*, batch_id: str, song_count: int) -> None:
    _progress(
        "[batch %s] Starting draft generation for %d song(s).",
        _batch_label(batch_id),
        song_count,
    )


def log_song_draft_started(
    *,
    batch_id: str | None,
    song_number: int | None,
    song_id: str | None = None,
) -> None:
    suffix = f" (song_id={str(song_id)[:8]})" if song_id else ""
    _progress(
        "[batch %s] [song %s] Draft started%s.",
        _batch_label(batch_id),
        _song_label(song_number),
        suffix,
    )


def log_title_generated(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    attempt: int = 1,
) -> None:
    _progress(
        "[batch %s] [song %s] Title generated successfully (attempt %d): %s",
        _batch_label(batch_id),
        _song_label(song_number),
        attempt,
        title,
    )


def log_album_generated(
    *,
    batch_id: str | None,
    song_number: int | None,
    album: str,
    shared: bool = False,
    attempt: int = 1,
) -> None:
    scope = "shared album" if shared else "album"
    _progress(
        "[batch %s] [song %s] %s generated successfully (attempt %d): %s",
        _batch_label(batch_id),
        _song_label(song_number),
        scope.capitalize(),
        attempt,
        album,
    )


def log_album_reused(
    *,
    batch_id: str | None,
    song_number: int | None,
    album: str,
) -> None:
    _progress(
        "[batch %s] [song %s] Reusing shared album: %s",
        _batch_label(batch_id),
        _song_label(song_number),
        album,
    )


def log_lyrics_generated(
    *,
    batch_id: str | None,
    song_number: int | None,
    lyric_calls: int,
    attempts: int,
) -> None:
    _progress(
        "[batch %s] [song %s] Lyrics generated successfully "
        "(lyric_calls=%d, attempts=%d).",
        _batch_label(batch_id),
        _song_label(song_number),
        lyric_calls,
        attempts,
    )


def log_song_draft_complete(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    album: str,
    song_id: str | None = None,
) -> None:
    _progress(
        "[batch %s] [song %s] Draft complete — title='%s', album='%s'%s",
        _batch_label(batch_id),
        _song_label(song_number),
        title,
        album,
        f", song_id={str(song_id)[:8]}" if song_id else "",
    )


def log_batch_draft_summary(
    *,
    batch_id: str,
    succeeded: int,
    total: int,
) -> None:
    _progress(
        "[batch %s] Draft orchestration finished: %d/%d song(s) succeeded.",
        _batch_label(batch_id),
        succeeded,
        total,
    )


def log_song_draft_failed(
    *,
    batch_id: str | None,
    song_number: int | None,
    reason: str,
    song_id: str | None = None,
) -> None:
    _progress_warn(
        "[batch %s] [song %s] Draft failed%s: %s",
        _batch_label(batch_id),
        _song_label(song_number),
        f" (song_id={str(song_id)[:8]})" if song_id else "",
        reason,
    )


def log_suno_batch_started(*, batch_id: str, song_count: int, model: str) -> None:
    _progress(
        "[batch %s] Submitting %d song(s) to Suno (model=%s).",
        _batch_label(batch_id),
        song_count,
        model,
    )


def log_suno_submit_started(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    model: str,
) -> None:
    _progress(
        "[batch %s] [song %s] Suno submit started — title='%s', model=%s",
        _batch_label(batch_id),
        _song_label(song_number),
        title,
        model,
    )


def log_suno_submitted(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    task_id: str,
) -> None:
    _progress(
        "[batch %s] [song %s] Suno submitted — title='%s', task_id=%s",
        _batch_label(batch_id),
        _song_label(song_number),
        title,
        str(task_id)[:12],
    )


def log_suno_submit_failed(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    reason: str,
    song_id: str | None = None,
) -> None:
    _progress_warn(
        "[batch %s] [song %s] Suno submit failed — title='%s'%s: %s",
        _batch_label(batch_id),
        _song_label(song_number),
        title,
        f" (song_id={str(song_id)[:8]})" if song_id else "",
        reason,
    )


def log_suno_callback_succeeded(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    task_id: str | None = None,
) -> None:
    suffix = f", task_id={str(task_id)[:12]}" if task_id else ""
    _progress(
        "[batch %s] [song %s] Suno completed — title='%s'%s",
        _batch_label(batch_id),
        _song_label(song_number),
        title,
        suffix,
    )


def log_suno_callback_failed(
    *,
    batch_id: str | None,
    song_number: int | None,
    title: str,
    status: str,
    reason: str = "",
) -> None:
    detail = f": {reason}" if reason else ""
    _progress_warn(
        "[batch %s] [song %s] Suno failed — title='%s', status=%s%s",
        _batch_label(batch_id),
        _song_label(song_number),
        title,
        status,
        detail,
    )


def log_suno_batch_submit_summary(
    *,
    batch_id: str,
    submitted: int,
    failed: int,
    total: int,
) -> None:
    if failed > 0:
        _progress_warn(
            "[batch %s] Suno submission finished: %d submitted, %d failed, %d total.",
            _batch_label(batch_id),
            submitted,
            failed,
            total,
        )
    else:
        _progress(
            "[batch %s] Suno submission finished: %d submitted, %d failed, %d total.",
            _batch_label(batch_id),
            submitted,
            failed,
            total,
        )
