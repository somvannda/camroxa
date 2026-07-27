"""Scan CAMXORA run directories for DistroKid albums (WAV + thumbnail)."""

from __future__ import annotations

import re
from pathlib import Path

from features.distrokid.models.distrokid_models import Album, Track, TrackStatus

_TITLE_SUFFIX_RE = re.compile(r"_(OK|Alt)$", re.IGNORECASE)
_LEADING_TRACK_RE = re.compile(r"^(\d+)\.\s*")


def clean_track_title(stem: str) -> str:
    name = _LEADING_TRACK_RE.sub("", stem.strip())
    name = _TITLE_SUFFIX_RE.sub("", name)
    return name.strip() or stem.strip()


def _role_from_stem(stem: str) -> str:
    lower = stem.lower()
    if lower.endswith("_alt") or " secondary" in lower or lower.endswith("_secondary"):
        return "secondary"
    return "primary"


def scan_album_directory(
    directory: Path,
    *,
    album_name: str | None = None,
    batch_id: str = "",
    artist_name: str = "",
) -> Album | None:
    """Build an Album from a run folder that already has .wav files (or mp3 placeholders)."""
    root = Path(directory)
    if not root.is_dir():
        return None

    wav_by_stem: dict[str, Path] = {}
    mp3_files: list[Path] = []
    try:
        for entry in root.iterdir():
            if not entry.is_file():
                continue
            suffix = entry.suffix.lower()
            if suffix == ".wav":
                wav_by_stem[entry.stem.lower()] = entry
            elif suffix == ".mp3":
                mp3_files.append(entry)
    except OSError:
        return None

    tracks: list[Track] = []
    # Prefer pairing MP3 metadata with WAV; if only WAVs exist, use those.
    sources = sorted(mp3_files) if mp3_files else sorted(wav_by_stem.values())
    for index, source in enumerate(sources, start=1):
        stem = source.stem
        wav_path = wav_by_stem.get(stem.lower())
        if wav_path is None and source.suffix.lower() == ".wav":
            wav_path = source
        title = clean_track_title(stem)
        track = Track(
            filename=source.name,
            title=title,
            path=source if source.suffix.lower() == ".mp3" else (wav_path or source),
            wav_path=wav_path,
            track_number=index,
            status=TrackStatus.READY if wav_path and wav_path.exists() else TrackStatus.WAV_PENDING,
            role=_role_from_stem(stem),
        )
        tracks.append(track)

    if not tracks:
        return None

    album = Album(
        name=(album_name or root.name).strip() or root.name,
        path=root,
        tracks=tracks,
        batch_id=batch_id,
        artist_name=artist_name,
    )
    album.mark_tracks_ready_from_wav()
    return album


def find_run_dir_albums(
    roots: list[Path],
    *,
    artist_name: str = "",
) -> list[Album]:
    albums: list[Album] = []
    for root in roots:
        album = scan_album_directory(root, artist_name=artist_name)
        if album is not None:
            albums.append(album)
    return albums
