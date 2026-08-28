"""Create-page generate helpers — web Create payload + Version 1/2 folders."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path

from shared.lib.music_composer import get_inclusive_day_span

VERSION_1 = "Version 1"
VERSION_2 = "Version 2"
_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class CreateGeneratePlan:
    mode: str
    model: str
    title: str
    lyrics: str
    styles: str
    prompt: str
    negative_tags: str
    vocal_gender: str | None
    style_weight: float
    weirdness: float
    audio_weight: float
    song_count: int
    songs_per_day: int
    planned_days: int
    save_folder: str
    version_mode: str
    language: str = "en"
    secondary_language: str = ""
    creativity: int = 55
    auto_image: bool = False
    auto_video: bool = False
    auto_merge: bool = False
    download_wav: bool = False
    download_lrc: bool = False
    download_srt: bool = False
    template_v1_id: str = ""
    template_v2_id: str = ""


def planned_song_count(song_count: int, from_date: str, to_date: str) -> int:
    days = get_inclusive_day_span(from_date, to_date) or 0
    return max(0, int(song_count)) * days


def planned_day_count(from_date: str, to_date: str) -> int:
    return max(0, get_inclusive_day_span(from_date, to_date) or 0)


def validate_create_plan(plan: CreateGeneratePlan) -> str | None:
    if not plan.save_folder.strip():
        return "Choose a Save to folder before generating."
    if plan.song_count <= 0:
        return "Choose a valid date range and Count before generating."
    if plan.mode == "simple":
        if not plan.prompt.strip():
            return "Enter styles for the song you want to create."
        return None
    # Advanced drafts lyrics per song; styles are optional Suno tags.
    return None


def web_generate_body(
    plan: CreateGeneratePlan,
    *,
    title: str | None = None,
    lyrics: str | None = None,
) -> dict[str, object]:
    gender = (plan.vocal_gender or "").strip().lower()
    body: dict[str, object] = {
        "mode": plan.mode,
        "model": plan.model,
        "title": (title if title is not None else plan.title) or "",
        "style": plan.styles,
        "instrumental": False,
        "style_weight": plan.style_weight,
        "weirdness_constraint": plan.weirdness,
        "audio_weight": plan.audio_weight,
    }
    if plan.negative_tags:
        body["negative_tags"] = plan.negative_tags
    if gender in {"m", "f", "both"}:
        body["vocal_gender"] = gender
    if plan.mode == "simple":
        body["prompt"] = plan.prompt
        body["lyrics"] = ""
        return body
    body["lyrics"] = (lyrics if lyrics is not None else plan.lyrics) or ""
    body["prompt"] = ""
    return body


def draft_description(plan: CreateGeneratePlan) -> str:
    return (
        plan.styles.strip()
        or plan.prompt.strip()
        or plan.title.strip()
        or "Create an original song"
    )


def draft_prompt(plan: CreateGeneratePlan) -> str:
    """Prompt for web Create lyric assist (`POST /web-music/generate-draft`)."""
    parts = [draft_description(plan)]
    language = (plan.language or "en").strip() or "en"
    secondary = (plan.secondary_language or "").strip()
    parts.append(f"Write the lyrics in {language}.")
    if secondary:
        parts.append(f"Include {secondary} in the same song (bilingual).")
    return " ".join(parts)


def version_folders(save_folder: str) -> tuple[Path, Path]:
    root = Path(save_folder)
    return root / VERSION_1, root / VERSION_2


def clip_folder_assignment(version_mode: str) -> tuple[str, str]:
    """Map Suno ok/alt clips onto Version 1 / Version 2 folders."""
    mode = (version_mode or "keep").strip().lower()
    if mode in {"shuffle", "random"}:
        folders = [VERSION_1, VERSION_2]
        random.shuffle(folders)
        return folders[0], folders[1]
    if mode in {"v2"}:
        return VERSION_2, VERSION_1
    return VERSION_1, VERSION_2


def safe_audio_filename(title: str, *, index: int = 1, song_count: int = 1, task_id: str = "") -> str:
    cleaned = _UNSAFE_FILENAME.sub("", (title or "").strip()) or "Untitled"
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:80] or "Untitled"
    if song_count > 1:
        cleaned = f"{cleaned} ({index})"
    suffix = (task_id or "").replace("-", "")[:8]
    if suffix:
        cleaned = f"{cleaned} {suffix}"
    return f"{cleaned}.mp3"


def safe_image_filename(kind: str, *, day_index: int, planned_days: int) -> str:
    label = "background" if kind == "background" else "thumbnail"
    if planned_days > 1:
        return f"{label}-day{day_index}.png"
    return f"{label}.png"


def image_prompt_for(plan: CreateGeneratePlan, *, kind: str, day_index: int) -> str:
    style = plan.styles.strip() or plan.prompt.strip() or "cinematic music"
    title = plan.title.strip() or "untitled track"
    subject = "album cover thumbnail" if kind == "thumbnail" else "widescreen music video background"
    return (
        f"{subject} for a song titled '{title}', day {day_index}, "
        f"style cues: {style}. No text, no logos, no watermarks."
    )


def generation_is_open(status: str) -> bool:
    return str(status or "").strip().lower() in {"pending", "running", "queued"}


def generation_failed(status: str) -> bool:
    return str(status or "").strip().lower() in {"failed", "cancelled"}


def generation_succeeded(status: str) -> bool:
    return str(status or "").strip().lower() == "success"
