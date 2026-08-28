"""Create-page history — map web-music generations (database) to table rows."""

from __future__ import annotations

from pathlib import Path

from shared.lib.create_generate import generation_failed, generation_succeeded, safe_audio_filename
from shared.lib.formatting import format_datetime_label
from shared.models.web_music import WebMusicClipResponse, WebMusicGenerationResponse

HISTORY_INDEX_BASE = 1000
HISTORY_PAGE_SIZE = 100
HISTORY_MAX_ITEMS = 300
STATE_GENERATING = "Generating…"
STATE_READY = "Ready"
STATE_FAILED = "Failed"
_AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".flac"}
_CAMXORA_MAGIC = (b"CXA1", b"CXO1")


def is_encrypted_audio_bytes(data: bytes) -> bool:
    """True when the blob is a Camxora package (not a playable MP3)."""
    return bool(data) and data[:4] in _CAMXORA_MAGIC


def is_encrypted_audio_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return is_encrypted_audio_bytes(handle.read(4))
    except OSError:
        return False


def generation_row_state(
    status: str,
    clips: list[WebMusicClipResponse] | None = None,
) -> str:
    if generation_failed(status):
        return STATE_FAILED
    ready = any(clip.ready for clip in (clips or []))
    if generation_succeeded(status) and ready:
        return STATE_READY
    return STATE_GENERATING


def matches_search(title: str, query: str) -> bool:
    needle = (query or "").strip().lower()
    if not needle:
        return True
    return needle in (title or "").lower()


def task_file_token(task_id: str) -> str:
    return (task_id or "").replace("-", "")[:8]


def download_root_from_file(path: str) -> str:
    """Parent of Version 1/2, or the file folder if it is not a version tree."""
    parent = Path(path).parent
    if parent.name in {"Version 1", "Version 2"}:
        return str(parent.parent)
    return str(parent)


def history_file_stem(title: str, task_id: str) -> str:
    """Stable Save-to name without the session index (never '(1000)')."""
    return Path(safe_audio_filename(title, index=1, song_count=1, task_id=task_id)).stem


_FORMAT_KINDS = ("mp3", "wav", "lrc", "srt")


def match_local_audio(folder: Path | None, *, title: str = "", task_id: str = "") -> str:
    if folder is None or not folder.is_dir():
        return ""
    audio = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in _AUDIO_SUFFIXES
    ]
    token = task_file_token(task_id)
    if token:
        for path in audio:
            if token in path.stem.replace("-", ""):
                return str(path)
    cleaned = (title or "").strip().lower()
    if cleaned:
        for path in audio:
            if path.stem.lower() == cleaned or path.stem.lower().startswith(cleaned):
                return str(path)
    return ""


def _stem_matches(path: Path, *, title: str = "", task_id: str = "") -> bool:
    token = task_file_token(task_id)
    stem_flat = path.stem.replace("-", "")
    if token and token in stem_flat:
        return True
    cleaned = (title or "").strip().lower()
    return bool(cleaned) and (path.stem.lower() == cleaned or path.stem.lower().startswith(cleaned))


def match_local_files(folder: Path | None, *, title: str = "", task_id: str = "") -> dict[str, str]:
    """Existing mp3/wav/lrc/srt in a version folder, keyed by kind."""
    found = {kind: "" for kind in _FORMAT_KINDS}
    if folder is None or not folder.is_dir():
        return found
    audio = match_local_audio(folder, title=title, task_id=task_id)
    if audio:
        stem = Path(audio)
        suffix = stem.suffix.lower().lstrip(".")
        if suffix in found:
            found[suffix] = audio
        for kind in _FORMAT_KINDS:
            if found[kind]:
                continue
            sibling = stem.with_suffix(f".{kind}")
            if sibling.is_file():
                found[kind] = str(sibling)
        return found
    for path in folder.iterdir():
        if not path.is_file():
            continue
        kind = path.suffix.lower().lstrip(".")
        if kind not in found or found[kind] or not _stem_matches(path, title=title, task_id=task_id):
            continue
        found[kind] = str(path)
    return found


def history_slots(items: list[WebMusicGenerationResponse]) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for offset, item in enumerate(items):
        rows.append(
            {
                "index": HISTORY_INDEX_BASE + offset,
                "title": (item.title or "").strip() or "Untitled",
                "state": generation_row_state(item.status, item.clips),
                "task_id": item.id,
                "created": format_datetime_label(item.created_at),
            }
        )
    return rows
