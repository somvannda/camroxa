"""DistroKid album/track DTOs — CAMXORA port (no Mixea / local convert)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TrackStatus(Enum):
    PENDING = "pending"
    WAV_PENDING = "wav_pending"
    READY = "ready"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class AlbumStatus(Enum):
    PENDING = "pending"
    WAV_PENDING = "wav_pending"
    READY = "ready"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Track:
    """Single DistroKid upload track (Suno WAV required)."""

    filename: str
    title: str
    path: Path
    wav_path: Path | None = None
    track_number: int = 0
    status: TrackStatus = TrackStatus.PENDING
    error_message: str | None = None
    suno_task_id: str = ""
    suno_audio_id: str = ""
    role: str = "primary"
    metadata: dict | None = None

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def wav_exists(self) -> bool:
        return self.wav_path is not None and self.wav_path.exists()

    @property
    def file_size_mb(self) -> float:
        if self.exists:
            return self.path.stat().st_size / (1024 * 1024)
        return 0.0

    @property
    def wav_size_mb(self) -> float:
        if self.wav_exists and self.wav_path is not None:
            return self.wav_path.stat().st_size / (1024 * 1024)
        return 0.0

    @property
    def wav_byte_size(self) -> int:
        if self.wav_exists and self.wav_path is not None:
            return int(self.wav_path.stat().st_size)
        return 0


@dataclass
class Album:
    """Album folder ready for DistroKid (run-dir based)."""

    name: str
    path: Path
    tracks: list[Track] = field(default_factory=list)
    thumbnail: Path | None = None
    status: AlbumStatus = AlbumStatus.PENDING
    error_message: str | None = None
    batch_id: str = ""
    artist_name: str = ""
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if self.thumbnail is None:
            self.thumbnail = self._find_thumbnail()

    def _find_thumbnail(self) -> Path | None:
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        preferred = ("_th.", "thumbnail", "cover", "artwork")
        try:
            files = [f for f in self.path.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]
        except OSError:
            return None
        for file in files:
            lower = file.name.lower()
            if any(token in lower for token in preferred):
                return file
        return files[0] if files else None

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def has_thumbnail(self) -> bool:
        return self.thumbnail is not None and self.thumbnail.exists()

    @property
    def is_ready_for_upload(self) -> bool:
        return self.track_count > 0 and all(track.wav_exists for track in self.tracks)

    def get_ready_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.status == TrackStatus.READY and t.wav_exists]

    def mark_tracks_ready_from_wav(self) -> int:
        ready = 0
        for track in self.tracks:
            if track.wav_exists:
                track.status = TrackStatus.READY
                ready += 1
            else:
                track.status = TrackStatus.WAV_PENDING
        if ready == self.track_count and ready > 0:
            self.status = AlbumStatus.READY
        elif ready > 0:
            self.status = AlbumStatus.WAV_PENDING
        return ready
