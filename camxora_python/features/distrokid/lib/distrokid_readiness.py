"""Helpers for DistroKid pipeline readiness (Short gate, WAV pairing)."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.pipeline_merge import list_branch_export_outputs


def count_mp3_tracks(run_dir: str | Path) -> int:
    root = Path(run_dir)
    if not root.is_dir():
        return 0
    try:
        return sum(1 for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".mp3")
    except OSError:
        return 0


def short_exports_ready(run_dir: str | Path, *, expected: int | None = None) -> bool:
    """True when individual Short/Reel MP4s exist for each track (no merge required)."""
    root = Path(run_dir)
    need = expected if expected is not None else count_mp3_tracks(root)
    if need <= 0:
        return True
    reels = list_branch_export_outputs(str(root), "reel")
    return len(reels) >= need


def find_matching_mp3_stem(run_dir: Path, *, title: str, track_no: int | None, role: str) -> Path | None:
    """Prefer an existing MP3 filename stem so WAV pairs 1:1 with album scanner."""
    suffix = "OK" if str(role).lower() == "primary" else "Alt"
    title_key = str(title or "").strip().lower()
    candidates: list[Path] = []
    try:
        candidates = [p for p in run_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp3"]
    except OSError:
        return None

    # Exact preferred naming: "N. Title_OK.mp3"
    if isinstance(track_no, int):
        preferred = f"{max(1, track_no)}. {title}_{suffix}.mp3".lower()
        for path in candidates:
            if path.name.lower() == preferred:
                return path

    role_matches = [p for p in candidates if p.stem.lower().endswith(f"_{suffix.lower()}")]
    pool = role_matches or candidates
    for path in pool:
        stem = path.stem
        # Strip leading "N. "
        bare = stem
        if len(bare) > 3 and bare[0].isdigit() and ". " in bare[:6]:
            bare = bare.split(". ", 1)[-1]
        if bare.lower().endswith(f"_{suffix.lower()}"):
            bare = bare[: -(len(suffix) + 1)]
        if bare.strip().lower() == title_key:
            return path
    if isinstance(track_no, int):
        for path in pool:
            if path.name.lower().startswith(f"{max(1, track_no)}. "):
                return path
    return None


def wav_path_for_mp3(mp3_path: Path) -> Path:
    return mp3_path.with_suffix(".wav")
