"""Post-export MP4 validity — size gate plus optional ffprobe media checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES, is_valid_export_output
from shared.lib.subprocess_utils import run_hidden

MIN_VALID_EXPORT_DURATION_SEC = 0.05
# Reject truncated encodes whose container duration is far shorter than the source audio.
MIN_AUDIO_DURATION_RATIO = 0.85
# FPS tolerance for concat-copy compatibility (float probe noise).
FPS_MATCH_TOLERANCE = 0.08
# Canonical audio layout for all CAMXORA exports (concat-copy safe).
EXPORT_AUDIO_SAMPLE_RATE = 48000
EXPORT_AUDIO_CHANNELS = 2


@dataclass(frozen=True, slots=True)
class ExportStreamIdentity:
    width: int
    height: int
    fps: float
    video_codec: str
    color_range: str
    audio_sample_rate: int
    audio_channels: int

    @property
    def label(self) -> str:
        return (
            f"{self.width}x{self.height}@{self.fps:.3g}fps "
            f"v={self.video_codec or '?'} range={self.color_range or '?'} "
            f"a={self.audio_sample_rate or '?'}Hz/{self.audio_channels or '?'}ch"
        )


def resolve_ffprobe_path(ffmpeg_path: str = "") -> str:
    from shared.lib.ffmpeg_paths import resolve_ffprobe_path

    hint = str(ffmpeg_path or "").strip() or "ffmpeg"
    resolved = resolve_ffprobe_path(hint)
    return resolved if Path(resolved).is_file() else ""


def _probe_format_duration(target_path: str, ffprobe_path: str) -> float:
    if not ffprobe_path or not Path(ffprobe_path).is_file():
        return 0.0
    try:
        completed = run_hidden(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                target_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return 0.0
    try:
        parsed = float(str(completed.stdout or "").strip() or "0")
    except ValueError:
        return 0.0
    return max(0.0, parsed) if parsed == parsed else 0.0


def _has_video_stream(target_path: str, ffprobe_path: str) -> bool:
    if not ffprobe_path or not Path(ffprobe_path).is_file():
        return False
    try:
        completed = run_hidden(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                target_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if getattr(completed, "returncode", 1) != 0:
        return False
    return "video" in str(completed.stdout or "").strip().lower()


def _parse_fps_token(raw: object) -> float:
    text = str(raw or "").strip()
    if not text or text in {"0/0", "N/A"}:
        return 0.0
    if "/" in text:
        num_s, den_s = text.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
        except ValueError:
            return 0.0
        return (num / den) if den else 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_video_codec(codec: object) -> str:
    text = str(codec or "").strip().lower()
    if not text:
        return ""
    if "nvenc" in text or text in {"h264", "avc", "libx264"}:
        return "h264"
    return text


def _normalize_color_range(raw: object) -> str:
    text = str(raw or "").strip().lower()
    if text in {"pc", "full", "jpeg"}:
        return "pc"
    if text in {"tv", "limited", "mpeg"}:
        return "tv"
    if text in {"1", "2"}:
        # ffprobe sometimes emits numeric: 1=tv/limited, 2=pc/full (varies by build)
        return "pc" if text == "2" else "tv"
    return text or "unknown"


def probe_export_stream_identity(
    target_path: str,
    *,
    ffprobe_path: str = "",
    ffmpeg_path: str = "",
) -> ExportStreamIdentity | None:
    """Probe width/height/fps/codec/color_range/audio layout for concat compatibility."""
    probe = str(ffprobe_path or "").strip() or resolve_ffprobe_path(ffmpeg_path)
    path = Path(str(target_path or "").strip())
    if not probe or not path.is_file():
        return None
    try:
        completed = run_hidden(
            [
                probe,
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,"
                "color_range,sample_rate,channels",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if getattr(completed, "returncode", 1) != 0:
        return None
    try:
        payload = json.loads(str(completed.stdout or "") or "{}")
    except json.JSONDecodeError:
        return None
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        return None
    video = next((s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"), None)
    if not isinstance(video, dict):
        return None
    try:
        width = int(video.get("width") or 0)
        height = int(video.get("height") or 0)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    fps = _parse_fps_token(video.get("avg_frame_rate")) or _parse_fps_token(video.get("r_frame_rate"))
    sample_rate = 0
    channels = 0
    if isinstance(audio, dict):
        try:
            sample_rate = int(float(str(audio.get("sample_rate") or "0") or "0"))
        except (TypeError, ValueError):
            sample_rate = 0
        try:
            channels = int(audio.get("channels") or 0)
        except (TypeError, ValueError):
            channels = 0
    return ExportStreamIdentity(
        width=width,
        height=height,
        fps=float(fps or 0.0),
        video_codec=_normalize_video_codec(video.get("codec_name")),
        color_range=_normalize_color_range(video.get("color_range")),
        audio_sample_rate=sample_rate,
        audio_channels=channels,
    )


def identities_concat_compatible(left: ExportStreamIdentity, right: ExportStreamIdentity) -> list[str]:
    """Return human reasons the two streams cannot stream-copy concat (empty = ok)."""
    reasons: list[str] = []
    if left.width != right.width or left.height != right.height:
        reasons.append(f"resolution {left.width}x{left.height} vs {right.width}x{right.height}")
    if left.fps > 0 and right.fps > 0 and abs(left.fps - right.fps) > FPS_MATCH_TOLERANCE:
        reasons.append(f"fps {left.fps:.3g} vs {right.fps:.3g}")
    if left.video_codec and right.video_codec and left.video_codec != right.video_codec:
        reasons.append(f"video codec {left.video_codec} vs {right.video_codec}")
    if (
        left.color_range not in {"", "unknown"}
        and right.color_range not in {"", "unknown"}
        and left.color_range != right.color_range
    ):
        reasons.append(f"color_range {left.color_range} vs {right.color_range}")
    if left.audio_sample_rate and right.audio_sample_rate and left.audio_sample_rate != right.audio_sample_rate:
        reasons.append(f"audio rate {left.audio_sample_rate} vs {right.audio_sample_rate}")
    if left.audio_channels and right.audio_channels and left.audio_channels != right.audio_channels:
        reasons.append(f"audio channels {left.audio_channels} vs {right.audio_channels}")
    return reasons


def matches_expected_export_geometry(
    identity: ExportStreamIdentity,
    *,
    width: int,
    height: int,
    fps: int | float,
) -> bool:
    if identity.width != int(width) or identity.height != int(height):
        return False
    expected_fps = float(fps or 0)
    if expected_fps > 0 and identity.fps > 0 and abs(identity.fps - expected_fps) > FPS_MATCH_TOLERANCE:
        return False
    return True


def export_matches_batch_specs(
    target_path: str,
    *,
    width: int,
    height: int,
    fps: int | float,
    ffmpeg_path: str = "",
    audio_path: str = "",
) -> bool:
    """True when file is usable and matches this batch's resolution/FPS (rejects stale leftovers)."""
    if not is_usable_export_output(
        target_path,
        ffmpeg_path=ffmpeg_path,
        audio_path=audio_path,
        require_media=True,
    ):
        return False
    identity = probe_export_stream_identity(target_path, ffmpeg_path=ffmpeg_path)
    if identity is None:
        # No ffprobe — keep prior usable gate only.
        return True
    if not matches_expected_export_geometry(identity, width=width, height=height, fps=fps):
        return False
    # Prefer canonical audio so leftover files from older builds are re-exported.
    if identity.audio_sample_rate and identity.audio_sample_rate != EXPORT_AUDIO_SAMPLE_RATE:
        return False
    if identity.audio_channels and identity.audio_channels != EXPORT_AUDIO_CHANNELS:
        return False
    return True


def assert_concat_copy_compatible(
    mp4_paths: list[str],
    *,
    ffmpeg_path: str = "",
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_fps: int | float | None = None,
) -> ExportStreamIdentity:
    """Require all inputs share concat-copy identity; raise RuntimeError with details otherwise."""
    paths = [str(p).strip() for p in mp4_paths if str(p).strip()]
    if len(paths) < 2:
        raise RuntimeError("Need at least two MP4 files to merge.")
    identities: list[tuple[str, ExportStreamIdentity]] = []
    for path in paths:
        identity = probe_export_stream_identity(path, ffmpeg_path=ffmpeg_path)
        if identity is None:
            continue
        identities.append((path, identity))
    if not identities:
        return ExportStreamIdentity(
            width=int(expected_width or 0),
            height=int(expected_height or 0),
            fps=float(expected_fps or 0),
            video_codec="",
            color_range="unknown",
            audio_sample_rate=EXPORT_AUDIO_SAMPLE_RATE,
            audio_channels=EXPORT_AUDIO_CHANNELS,
        )

    _first_path, baseline = identities[0]
    if expected_width and expected_height:
        if not matches_expected_export_geometry(
            baseline,
            width=int(expected_width),
            height=int(expected_height),
            fps=float(expected_fps or 0),
        ):
            raise RuntimeError(
                "Merge blocked — first export does not match this batch's export settings "
                f"(file {baseline.label}; expected {expected_width}x{expected_height}"
                + (f"@{expected_fps}fps" if expected_fps else "")
                + "). Re-export the batch, then merge again."
            )

    problems: list[str] = []
    for path, identity in identities[1:]:
        reasons = identities_concat_compatible(baseline, identity)
        if reasons:
            problems.append(f"{Path(path).name}: {', '.join(reasons)}")
    if problems:
        shown = "; ".join(problems[:6])
        extra = f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        raise RuntimeError(
            "Merge blocked — exports are not identical enough for lossless join "
            f"(baseline {baseline.label}). {shown}{extra}. "
            "Re-export the whole batch with one resolution/FPS/speed setting, then merge."
        )
    return baseline


def export_media_looks_complete(
    target_path: str,
    *,
    ffprobe_path: str = "",
    audio_path: str = "",
) -> bool:
    """Return True when the MP4 has a video stream and a usable duration.

    When ``audio_path`` is provided, also reject exports whose duration is much
    shorter than the source audio (incomplete / truncated encodes).
    """
    probe = str(ffprobe_path or "").strip() or resolve_ffprobe_path()
    if not probe:
        return True
    if not _has_video_stream(target_path, probe):
        return False
    duration = _probe_format_duration(target_path, probe)
    if duration <= MIN_VALID_EXPORT_DURATION_SEC:
        return False
    audio = str(audio_path or "").strip()
    if audio and Path(audio).is_file():
        audio_duration = _probe_format_duration(audio, probe)
        if audio_duration > 1.0 and duration < (audio_duration * MIN_AUDIO_DURATION_RATIO):
            return False
    return True


def is_usable_export_output(
    target_path: str,
    *,
    ffmpeg_path: str = "",
    audio_path: str = "",
    require_media: bool = True,
) -> bool:
    """Size gate plus optional media completeness (video stream / duration)."""
    if not is_valid_export_output(target_path):
        return False
    if not require_media:
        return True
    probe = resolve_ffprobe_path(ffmpeg_path)
    if not probe:
        return True
    return export_media_looks_complete(
        target_path,
        ffprobe_path=probe,
        audio_path=audio_path,
    )


def resolve_written_export_path(
    *,
    preferred_path: str,
    output_dir: str,
    audio_path: str,
    ffmpeg_path: str = "",
    require_media: bool = True,
) -> str | None:
    """Resolve the real on-disk MP4 after export (preferred path or stem fallback)."""
    preferred = str(preferred_path or "").strip()
    stem = Path(str(audio_path or "").strip()).stem if str(audio_path or "").strip() else "export"
    fallback = str(Path(str(output_dir or "").strip() or ".") / f"{stem}.mp4")
    candidates: list[str] = []
    for candidate in (preferred, fallback):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        if is_usable_export_output(
            candidate,
            ffmpeg_path=ffmpeg_path,
            audio_path=audio_path,
            require_media=require_media,
        ):
            return candidate
    return None


def filter_merge_ready_paths(
    mp4_paths: list[str],
    *,
    ffmpeg_path: str = "",
) -> list[str]:
    """Keep only merge-ready MP4s (size + media when ffprobe is available)."""
    ready: list[str] = []
    for raw in mp4_paths:
        path = str(raw or "").strip()
        if not path:
            continue
        if is_usable_export_output(path, ffmpeg_path=ffmpeg_path, require_media=True):
            ready.append(path)
    return ready


def default_stem_export_path(*, audio_path: str, output_dir: str) -> str:
    stem = Path(str(audio_path or "").strip()).stem if str(audio_path or "").strip() else "manual-export"
    return str(Path(str(output_dir or "").strip() or ".") / f"{stem}.mp4")
