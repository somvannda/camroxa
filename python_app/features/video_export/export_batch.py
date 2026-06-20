from __future__ import annotations

from dataclasses import dataclass, field

from .export import ExportJob


@dataclass
class ExportBatch:
    """Per-batch export state. Multiple batches can run concurrently."""

    batch_key: str
    output_dir: str
    ffmpeg_path: str
    bg_path: str
    logo_path: str
    queue: list[str] = field(default_factory=list)
    jobs: dict[str, ExportJob] = field(default_factory=dict)
    job_state: dict[str, dict[str, object]] = field(default_factory=dict)
    mp3s: list[str] = field(default_factory=list)
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    outputs_by_mp3: dict[str, str] = field(default_factory=dict)
    running: bool = False
    auto_merge_after: bool = False
