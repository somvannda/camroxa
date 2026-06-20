from __future__ import annotations

import io
import re
import time
from pathlib import Path

from typing import Any, TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from .generation_proxy import GenerationProxy

from ..database.image_db import (
    claim_pending_image_jobs,
    mark_image_job_failed,
    mark_image_job_pending,
    mark_image_job_ready,
    bump_image_job_attempt,
    get_ready_background_output,
    pick_least_used_value,
)
from ..database.music_db import get_batch_run_dirs_by_batch_id, get_latest_suno_output_dirs_by_batch_id
from ..database.persistence import db_get_profile_image_config


def list_images_in_folder(folder: str) -> list[dict]:
    root = Path(str(folder or "").strip())
    if not root.exists() or not root.is_dir():
        return []
    out: list[dict] = []
    for p in root.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        try:
            stat = p.stat()
            out.append(
                {
                    "filePath": str(p),
                    "fileName": p.name,
                    "mtimeMs": int(stat.st_mtime_ns // 1_000_000),
                }
            )
        except Exception:
            continue
    out.sort(key=lambda x: (-int(x.get("mtimeMs", 0) or 0), str(x.get("fileName", ""))))
    return out


def _resolve_provider(
    kind: str,
    settings: dict,
) -> str:
    """Resolve the provider name for a given job kind.

    Args:
        kind: Job kind — "background" or "thumbnail".
        settings: Current application settings dict.

    Returns:
        Provider name string: "fal" or "slai".
    """
    setting_key = (
        "imageBackgroundProvider" if kind == "background" else "imageThumbnailProvider"
    )
    provider = str((settings or {}).get(setting_key, "") or "").strip().lower()
    if provider not in ("slai", "fal"):
        provider = "slai"

    return provider


def run_pending_image_jobs(
    *,
    db_cfg: Any,
    settings: dict,
    generation_proxy: GenerationProxy,
    max_jobs: int = 8,
    should_cancel: Any = None,
    on_log: Any = None,
) -> dict:
    resolution = str(settings.get("outputResolution", "")).strip() or str(settings.get("imageResolution", "1920x1080")).strip() or "1920x1080"
    strength = int(settings.get("styleStrength", 60) or 60)
    strength = max(0, min(100, strength))
    bg_random = bool(settings.get("imageBgRandom", False))
    thumb_random = bool(settings.get("imageThumbRandom", False))
    bg_dir, thumb_dir = _resolve_image_sample_dirs(settings)
    profile_cfg_cache: dict[str, dict] = {}

    def _profile_cfg(profile_id: str) -> dict:
        pid = str(profile_id or "").strip()
        if not pid:
            return {}
        cached = profile_cfg_cache.get(pid)
        if isinstance(cached, dict):
            return cached
        try:
            raw = db_get_profile_image_config(db_cfg, pid)
            resolved = raw if isinstance(raw, dict) else {}
        except Exception:
            resolved = {}
        try:
            from ..database.persistence import db_get_profile_output_resolution

            pr = str(db_get_profile_output_resolution(db_cfg, pid) or "").strip()
            if pr:
                resolved = {**resolved, "outputResolution": pr}
        except Exception:
            pass
        profile_cfg_cache[pid] = resolved
        return resolved
    limit = max(1, min(40, int(max_jobs or 8)))
    try:
        workers = int(settings.get("perfImageWorkers", 4) or 4)
    except Exception:
        workers = 4
    workers = max(1, min(8, workers))
    claim_n = max(1, min(int(limit), int(workers)))
    jobs = claim_pending_image_jobs(db_cfg, claim_n, stale_running_sec=600, max_running=workers)
    if not jobs:
        return {"ok": True, "checked": 0, "completed": 0, "failed": 0}
    if callable(on_log):
        on_log(f"[{time.strftime('%H:%M:%S')}] Image worker: picked {len(jobs)} pending job(s)")
    completed = 0
    failed = 0
    deferred = 0
    max_attempts = 3

    # Separate background and thumbnail jobs for sequential processing
    bg_jobs = [j for j in jobs if str(j.get("kind", "")).strip().lower() == "background"]
    th_jobs = [j for j in jobs if str(j.get("kind", "")).strip().lower() == "thumbnail"]

    # Process background jobs first
    if bg_jobs:
        result = _run_job_batch(db_cfg, bg_jobs, generation_proxy, resolution, strength, bg_random, thumb_random, settings, should_cancel, on_log, max_attempts)
        completed += result["completed"]
        failed += result["failed"]
        deferred += result["deferred"]

    # Process thumbnail jobs after backgrounds complete
    if th_jobs:
        result = _run_job_batch(db_cfg, th_jobs, generation_proxy, resolution, strength, bg_random, thumb_random, settings, should_cancel, on_log, max_attempts)
        completed += result["completed"]
        failed += result["failed"]
        deferred += result["deferred"]

    return {"ok": True, "checked": len(jobs), "completed": completed, "failed": failed, "deferred": deferred}


def _run_job_batch(db_cfg: Any, jobs: list[dict], generation_proxy: GenerationProxy, resolution: str, style_strength: int, bg_random: bool, thumb_random: bool, settings: dict, should_cancel: Any, on_log: Any, max_attempts: int) -> dict:
    """Run a batch of image jobs sequentially with rate limiting between SLAI requests."""
    completed = 0
    failed = 0
    deferred = 0
    _profile_cfg_cache: dict[str, dict] = {}
    bg_dir, thumb_dir = _resolve_image_sample_dirs(settings)

    def _profile_cfg(profile_id: str) -> dict:
        pid = str(profile_id or "").strip()
        if not pid:
            return {}
        cached = _profile_cfg_cache.get(pid)
        if isinstance(cached, dict):
            return cached
        try:
            raw = db_get_profile_image_config(db_cfg, pid)
            resolved = raw if isinstance(raw, dict) else {}
        except Exception:
            resolved = {}
        try:
            from ..database.persistence import db_get_profile_output_resolution

            pr = str(db_get_profile_output_resolution(db_cfg, pid) or "").strip()
            if pr:
                resolved = {**resolved, "outputResolution": pr}
        except Exception:
            pass
        _profile_cfg_cache[pid] = resolved
        return resolved

    last_slai_time = 0.0
    rate_limit_sec = 5  # Minimum 5 seconds between SLAI requests

    for job in jobs:
        if callable(should_cancel) and bool(should_cancel()):
            break

        uid = str(job.get("jobUid", "")).strip()
        if not uid:
            continue
        kind = str(job.get("kind", "")).strip().lower()
        role = str(job.get("channelRole", "")).strip().upper()
        batch_id = str(job.get("batchId", "")).strip()
        profile_id = str(job.get("profileId", "")).strip()
        cfg = _profile_cfg(profile_id)
        job_resolution = resolution
        try:
            r2 = str(cfg.get("outputResolution", "")).strip() if isinstance(cfg, dict) else ""
            if r2:
                job_resolution = r2
        except Exception:
            job_resolution = resolution
        mode = str(cfg.get("mode", "bg_thumb")).strip() if isinstance(cfg, dict) else "bg_thumb"
        mode_norm = mode.lower().replace("-", "_")

        if kind == "thumbnail":
            if mode_norm != "thumb_only":
                bg_path = get_ready_background_output(db_cfg, batch_id=batch_id, profile_id=profile_id)
                if not bg_path or not Path(bg_path).exists():
                    try:
                        mark_image_job_pending(db_cfg, uid, error="Background image is not ready yet")
                    except Exception:
                        pass
                    if callable(on_log):
                        on_log(
                            f"[{time.strftime('%H:%M:%S')}] Image job deferred: job={uid} kind={kind} role={role} batch={batch_id} reason=Background image is not ready yet"
                        )
                    deferred += 1
                    continue

        # Rate limit: wait at least 30 seconds since last SLAI request
        elapsed = time.time() - last_slai_time
        if last_slai_time > 0 and elapsed < rate_limit_sec:
            wait_time = rate_limit_sec - elapsed
            if callable(on_log):
                on_log(f"[{time.strftime('%H:%M:%S')}] Rate limit: waiting {wait_time:.0f}s before next SLAI request")
            time.sleep(wait_time)

        attempt = int(job.get("attemptCount", 0) or 0) + 1
        if callable(on_log):
            on_log(f"[{time.strftime('%H:%M:%S')}] Image job start: job={uid} kind={kind} role={role} batch={batch_id} attempt={attempt}")
        started = time.time()
        bump_image_job_attempt(db_cfg, uid)
        job_bg_random = bg_random
        job_thumb_random = thumb_random
        v = cfg.get("backgroundRandom", None) if isinstance(cfg, dict) else None
        if v is not None:
            job_bg_random = bool(v)
        v = cfg.get("thumbnailRandom", None) if isinstance(cfg, dict) else None
        if v is not None:
            job_thumb_random = bool(v)
        job_bg_dir = bg_dir
        job_thumb_dir = thumb_dir
        v = str(cfg.get("backgroundSamplesDir", "")).strip() if isinstance(cfg, dict) else ""
        if v:
            job_bg_dir = v
        v = str(cfg.get("thumbnailSamplesDir", "")).strip() if isinstance(cfg, dict) else ""
        if v:
            job_thumb_dir = v
        try:
            _run_one_image_job(
                db_cfg=db_cfg,
                job=job,
                generation_proxy=generation_proxy,
                resolution=job_resolution,
                style_strength=style_strength,
                bg_samples_dir=job_bg_dir,
                thumb_samples_dir=job_thumb_dir,
                bg_random=job_bg_random,
                thumb_random=job_thumb_random,
                mode=mode,
                settings=settings,
                should_cancel=should_cancel,
                on_log=on_log,
            )
            last_slai_time = time.time()
        except InterruptedError:
            try:
                mark_image_job_pending(db_cfg, uid, error="Cancelled")
            except Exception:
                pass
            raise
        except Exception as exc:
            msg = str(exc)
            retryable = _is_retryable_image_error(msg)
            if retryable and attempt < max_attempts:
                try:
                    mark_image_job_pending(db_cfg, uid, error=msg)
                except Exception:
                    pass
                if callable(on_log):
                    on_log(
                        f"[{time.strftime('%H:%M:%S')}] Image job retry queued: job={uid} kind={kind} role={role} batch={batch_id} attempt={attempt} error={exc}"
                    )
                continue
            try:
                mark_image_job_failed(db_cfg, uid, error=msg)
            except Exception:
                pass
            if callable(on_log):
                on_log(f"[{time.strftime('%H:%M:%S')}] Image job failed: job={uid} kind={kind} role={role} batch={batch_id} error={exc}")
            failed += 1
            continue
        if callable(on_log):
            on_log(f"[{time.strftime('%H:%M:%S')}] Image job done: job={uid} elapsed={int((time.time() - started) * 1000)}ms")
        completed += 1

    return {"completed": completed, "failed": failed, "deferred": deferred}


def _run_one_image_job(
    *,
    db_cfg: Any,
    job: dict,
    generation_proxy: GenerationProxy,
    resolution: str,
    style_strength: int,
    bg_samples_dir: str,
    thumb_samples_dir: str,
    bg_random: bool,
    thumb_random: bool,
    mode: str = "bg_thumb",
    settings: dict | None = None,
    should_cancel: Any = None,
    on_log: Any = None,
) -> None:
    batch_id = str(job.get("batchId", "")).strip()
    kind = str(job.get("kind", "")).strip()
    role = str(job.get("channelRole", "")).strip().upper()
    profile_id = str(job.get("profileId", "")).strip()
    if not batch_id or not kind or not profile_id:
        raise RuntimeError("Invalid image job metadata")
    if callable(should_cancel) and bool(should_cancel()):
        raise InterruptedError("Cancelled")

    # Resolve provider name based on job kind and settings
    job_kind = kind.lower()
    if settings:
        provider = _resolve_provider(job_kind, settings)
    else:
        # Fallback to SLAI when settings not provided
        provider = "slai"
    dirs = get_batch_run_dirs_by_batch_id(db_cfg, batch_id)
    ok_dir = str(dirs.get("okDir", "")).strip()
    alt_dir = str(dirs.get("altDir", "")).strip()
    if not ok_dir and not alt_dir:
        existing = get_latest_suno_output_dirs_by_batch_id(db_cfg, batch_id)
        if bool(existing.get("ok")):
            ok_dir = str(existing.get("okDir", "")).strip()
            alt_dir = str(existing.get("altDir", "")).strip()
    output_dir = ok_dir if role == "OK" else (alt_dir or ok_dir)
    if not output_dir:
        raise RuntimeError("Batch output folder is not ready yet")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    suffix = _batch_suffix(batch_id)
    output_name = f"{kind}_{suffix}.png"
    out_path = str(Path(output_dir) / output_name)
    prompt = str(job.get("prompt", "")).strip()
    sample_paths = [str(x).strip() for x in list(job.get("samplePaths") or []) if str(x).strip()]
    uid = str(job.get("jobUid", "")).strip()
    if kind == "thumbnail":
        mode_norm = str(mode or "bg_thumb").strip().lower().replace("-", "_")
        # Prefer pre-assigned sample_paths (set at job creation time for uniqueness)
        if sample_paths:
            candidates = sample_paths
        elif bool(thumb_random):
            candidates = [str(r.get("filePath", "")).strip() for r in list_images_in_folder(thumb_samples_dir) if str(r.get("filePath", "")).strip()]
        else:
            candidates = sample_paths
        usable = [p for p in candidates if Path(p).exists()]
        overlay_path = pick_least_used_value(db_cfg, kind="thumb_sample", values=usable) if usable else ""
        if bool(thumb_random) and not overlay_path:
            raise RuntimeError("Thumbnail sample folder has no usable images for Random mode")
        bg_cover: Image.Image | None = None
        if mode_norm == "thumb_only":
            base_path = str(job.get("inputImagePath", "")).strip()
            if base_path and Path(base_path).exists():
                bg_cover = _read_cover_image(base_path, resolution)
            elif bool(bg_random):
                candidates = [str(r.get("filePath", "")).strip() for r in list_images_in_folder(bg_samples_dir) if str(r.get("filePath", "")).strip()]
                usable = [p for p in candidates if Path(p).exists()]
                base_path = pick_least_used_value(db_cfg, kind="bg_sample", values=usable) if usable else ""
                if base_path and Path(str(base_path)).exists():
                    bg_cover = _read_cover_image(str(base_path), resolution)
            if bg_cover is None:
                w, h = _resolution_wh(resolution)
                bg_cover = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        else:
            bg_path = get_ready_background_output(db_cfg, batch_id=batch_id, profile_id=profile_id)
            if not bg_path or not Path(bg_path).exists():
                raise RuntimeError("Background image is not ready yet")
            bg_cover = _read_cover_image(bg_path, resolution)

        # Determine thumbnail overlay mode for this profile
        thumbnail_overlay_mode = _get_thumbnail_overlay_mode(db_cfg, profile_id, settings or {})

        if thumbnail_overlay_mode == "preset_text":
            # Programmatic text overlay path — skip AI provider call entirely
            from ..database.music_db import list_songs_by_batch_id
            from ..database.preset_db import pick_least_used_text_preset
            from .text_overlay_renderer import render_text_overlay, TextStylePreset
            from .font_manager import FontManager

            songs = list_songs_by_batch_id(db_cfg, batch_id)
            titles = [str(s.get("title", "")).strip() for s in songs if str(s.get("title", "")).strip()]

            preset_record = pick_least_used_text_preset(db_cfg)
            if preset_record is None:
                raise RuntimeError("No text style presets configured")

            # Convert dict record to TextStylePreset dataclass
            preset = TextStylePreset(
                name=preset_record["name"],
                font_path=str(preset_record.get("font_path", "")),
                font_size=int(preset_record.get("font_size", 72)),
                primary_color=str(preset_record.get("primary_color", "#FFFFFFFF")),
                position=str(preset_record.get("position", "center")),
                glow_color=str(preset_record.get("glow_color", "#00000000")),
                glow_radius=int(preset_record.get("glow_radius", 0)),
                shadow_offset_x=int(preset_record.get("shadow_offset_x", 0)),
                shadow_offset_y=int(preset_record.get("shadow_offset_y", 0)),
                shadow_color=str(preset_record.get("shadow_color", "#00000080")),
                stroke_width=int(preset_record.get("stroke_width", 0)),
                stroke_color=str(preset_record.get("stroke_color", "#000000FF")),
                gradient_enabled=bool(preset_record.get("gradient_enabled", False)),
                gradient_start_color=str(preset_record.get("gradient_start_color", "#FFFFFFFF")),
                gradient_end_color=str(preset_record.get("gradient_end_color", "#000000FF")),
                line_spacing=float(preset_record.get("line_spacing", 1.4)),
                alignment=str(preset_record.get("alignment", "center")),
                max_text_width_pct=int(preset_record.get("max_text_width_pct", 80)),
                vertical_padding_pct=int(preset_record.get("vertical_padding_pct", 10)),
            )

            # Initialize FontManager with fonts directory from application settings
            fonts_dir = str((settings or {}).get("fontsDirectory", ""))
            font_manager = FontManager(fonts_dir) if fonts_dir else None

            w, h = _resolution_wh(resolution)
            overlay = render_text_overlay(titles, preset, w, h, font_manager)
            overlay = _scale_overlay_center(overlay, 0.91)
            final = Image.alpha_composite(bg_cover, overlay)

            out = io.BytesIO()
            final.save(out, format="PNG")
            final_bytes = out.getvalue()
            Path(out_path).write_bytes(final_bytes)
            mark_image_job_ready(db_cfg, uid, output_image_path=out_path)
            if callable(on_log):
                on_log(f"[{time.strftime('%H:%M:%S')}] Text overlay thumbnail saved: {out_path} (preset='{preset.name}')")
            return

        # AI overlay path (existing flow, uses generation proxy)
        overlay_input_bytes = _build_thumbnail_overlay_input_png(overlay_path, resolution, style_strength)
        started = time.time()
        png_bytes = generation_proxy.generate_image(
            prompt=prompt,
            provider=provider,
            resolution=resolution,
            style_strength=float(style_strength),
            base_image_png_bytes=overlay_input_bytes,
        )
        if callable(on_log):
            on_log(f"[{time.strftime('%H:%M:%S')}] {provider.upper()} done: kind=thumbnail role={role} batch={batch_id} elapsed={int((time.time() - started) * 1000)}ms")
        overlay = _chroma_key_black_overlay(png_bytes, resolution)
        overlay = _scale_overlay_center(overlay, 0.91)
        final = Image.alpha_composite(bg_cover, overlay)
        out = io.BytesIO()
        final.save(out, format="PNG")
        final_bytes = out.getvalue()
        Path(out_path).write_bytes(final_bytes)
        mark_image_job_ready(db_cfg, uid, output_image_path=out_path)
        if callable(on_log):
            on_log(f"[{time.strftime('%H:%M:%S')}] Image saved: {out_path}")
        return
    # Prefer pre-assigned sample_paths (set at job creation time for uniqueness)
    if sample_paths:
        candidates = sample_paths
    elif bool(bg_random):
        candidates = [str(r.get("filePath", "")).strip() for r in list_images_in_folder(bg_samples_dir) if str(r.get("filePath", "")).strip()]
    else:
        candidates = sample_paths
    usable = [p for p in candidates if Path(p).exists()]
    # Fallback: if assigned samples are unusable, scan the global folder
    if not usable and not bool(bg_random) and bg_samples_dir:
        if callable(on_log):
            on_log(f"[{time.strftime('%H:%M:%S')}] Image job: sample_paths unusable, falling back to folder: {bg_samples_dir}")
        candidates = [str(r.get("filePath", "")).strip() for r in list_images_in_folder(bg_samples_dir) if str(r.get("filePath", "")).strip()]
        if callable(on_log):
            on_log(f"[{time.strftime('%H:%M:%S')}] Image job: fallback found {len(candidates)} candidates, {len([p for p in candidates if Path(p).exists()])} exist on disk")
        usable = [p for p in candidates if Path(p).exists()]
    sample_path = pick_least_used_value(db_cfg, kind="bg_sample", values=usable) if usable else ""
    if callable(on_log):
        sp = sample_path[:50] if sample_path else '(empty)'
        on_log(f"[{time.strftime('%H:%M:%S')}] Image job: sample_paths={len(sample_paths)}, candidates={len(candidates)}, usable={len(usable)}, sample_path={sp}")
    if not sample_path or not Path(sample_path).exists():
        if bool(bg_random):
            raise RuntimeError("Background sample folder has no usable images for Random mode")
        missing = [Path(p).name for p in (sample_paths or [])[:6] if p]
        hint = f" (selected: {', '.join(missing)})" if missing else ""
        debug = f" (bg_random={bool(bg_random)}, bg_samples_dir='{bg_samples_dir}', usable_count={len(usable)})"
        raise RuntimeError(f"Background sample is missing{hint}{debug}")
    base_png = _read_png_bytes(sample_path)
    started = time.time()
    png_bytes = generation_proxy.generate_image(
        prompt=prompt,
        provider=provider,
        resolution=resolution,
        style_strength=float(style_strength),
        base_image_png_bytes=base_png,
    )
    if callable(on_log):
        on_log(f"[{time.strftime('%H:%M:%S')}] {provider.upper()} done: kind=background role={role} batch={batch_id} elapsed={int((time.time() - started) * 1000)}ms")
    final_bytes = to_cover_png_bytes(png_bytes, resolution)
    Path(out_path).write_bytes(final_bytes)
    mark_image_job_ready(db_cfg, uid, output_image_path=out_path)
    if callable(on_log):
        on_log(f"[{time.strftime('%H:%M:%S')}] Image saved: {out_path}")


def _batch_suffix(batch_id: str) -> str:
    text = str(batch_id or "").strip()
    m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-(\d+)-(\d+)$", text)
    if m:
        return f"{m.group(1)}_{m.group(2)}_{m.group(3)}"
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)
    return safe[-80:] if len(safe) > 80 else safe


def _resolution_wh(resolution: str) -> tuple[int, int]:
    r = str(resolution or "").strip()
    m = re.match(r"^(\d+)x(\d+)$", r)
    if not m:
        return (1920, 1080)
    w = max(1, int(m.group(1)))
    h = max(1, int(m.group(2)))
    return (w, h)


def _resolve_image_sample_dirs(settings: dict) -> tuple[str, str]:
    bg_dir = str((settings or {}).get("imageBackgroundSamplesDir", "")).strip()
    thumb_dir = str((settings or {}).get("imageThumbnailSamplesDir", "")).strip()
    base = str((settings or {}).get("imageSamplesDir", "")).strip()
    if (not bg_dir or not thumb_dir) and base:
        if not bg_dir:
            bg_dir = str(Path(base) / "background")
        if not thumb_dir:
            thumb_dir = str(Path(base) / "thumbnail")
    return (bg_dir, thumb_dir)


def _is_retryable_image_error(message: str) -> bool:
    s = str(message or "").strip().lower()
    if not s:
        return False
    if "background image is not ready yet" in s:
        return True
    if "timed out" in s or "timeout" in s:
        return True
    if "eof occurred in violation of protocol" in s:
        return True
    if "temporarily unavailable" in s or "connection reset" in s:
        return True
    if "turnstile" in s or "sentinel" in s or "blocked the request" in s:
        return True
    if "maximum call stack" in s:
        return True
    if "upload failed" in s:
        return True
    if "payload too large" in s or "request entity too large" in s:
        return True
    if "502" in s or "503" in s or "504" in s:
        return True
    if "rate limit" in s or "too many requests" in s:
        return True
    return False


def _read_png_bytes(file_path: str) -> bytes:
    p = str(file_path or "").strip()
    if not p:
        return b""
    img = Image.open(p).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _read_cover_image(file_path: str, resolution: str) -> Image.Image:
    p = str(file_path or "").strip()
    img = Image.open(p).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cover = Image.open(io.BytesIO(to_cover_png_bytes(buf.getvalue(), resolution))).convert("RGBA")
    return cover


def to_cover_png_bytes(png_bytes: bytes, resolution: str) -> bytes:
    w, h = _resolution_wh(resolution)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return png_bytes
    scale = max(float(w) / float(iw), float(h) / float(ih))
    rw = max(1, int(round(float(iw) * scale)))
    rh = max(1, int(round(float(ih) * scale)))
    resized = img.resize((rw, rh), Image.Resampling.LANCZOS)
    x = max(0, int((rw - w) / 2))
    y = max(0, int((rh - h) / 2))
    cropped = resized.crop((x, y, x + w, y + h))
    out = io.BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue() or png_bytes


def _build_thumbnail_overlay_input_png(overlay_path: str, resolution: str, style_strength: int) -> bytes:
    w, h = _resolution_wh(resolution)
    base = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    if not overlay_path or not Path(str(overlay_path)).exists():
        out = io.BytesIO()
        base.save(out, format="PNG")
        return out.getvalue()
    ov = Image.open(str(overlay_path)).convert("RGBA")
    box_w = max(240, int(round(float(w) * 0.34)))
    box_h = max(200, int(round(float(h) * 0.28)))
    margin = max(16, int(round(float(min(w, h)) * 0.02)))
    pad = max(10, int(round(float(min(w, h)) * 0.012)))
    x0 = max(0, w - box_w - margin)
    y0 = max(0, h - box_h - margin)
    alpha = max(0.0, min(1.0, float(style_strength) / 100.0))

    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    panel_bg = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 180))
    panel.paste(panel_bg, (x0, y0))

    max_w = max(1, box_w - pad * 2)
    max_h = max(1, box_h - pad * 2)
    ov_copy = ov.copy()
    ov_copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    ox = x0 + int((box_w - ov_copy.size[0]) / 2)
    oy = y0 + int((box_h - ov_copy.size[1]) / 2)
    if alpha >= 1.0:
        panel.paste(ov_copy, (ox, oy), ov_copy)
    else:
        a = ov_copy.getchannel("A")
        a = a.point(lambda v: int(v * alpha))
        ov_copy.putalpha(a)
        panel.paste(ov_copy, (ox, oy), ov_copy)

    composed = Image.alpha_composite(base, panel)
    out = io.BytesIO()
    composed.save(out, format="PNG")
    return out.getvalue()


def _chroma_key_black_overlay(png_bytes: bytes, resolution: str) -> Image.Image:
    w, h = _resolution_wh(resolution)
    img = Image.open(io.BytesIO(to_cover_png_bytes(png_bytes, resolution))).convert("RGBA")
    px = img.load()
    if px is None:
        return img
    threshold = 24
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if r <= threshold and g <= threshold and b <= threshold:
                px[x, y] = (r, g, b, 0)
            else:
                px[x, y] = (r, g, b, 255)
    box_w = max(240, int(round(float(w) * 0.34)))
    box_h = max(200, int(round(float(h) * 0.28)))
    margin = max(16, int(round(float(min(w, h)) * 0.02)))
    x0 = max(0, w - box_w - margin)
    y0 = max(0, h - box_h - margin)
    for y in range(y0, min(h, y0 + box_h)):
        for x in range(x0, min(w, x0 + box_w)):
            r, g, b, _a = px[x, y]
            px[x, y] = (r, g, b, 0)
    return img


def _scale_overlay_center(overlay: Image.Image, scale: float) -> Image.Image:
    s = float(scale or 1.0)
    if s >= 0.999:
        return overlay
    w, h = overlay.size
    nw = max(1, int(round(float(w) * s)))
    nh = max(1, int(round(float(h) * s)))
    resized = overlay.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = max(0, int((w - nw) / 2))
    y = max(0, int((h - nh) / 2))
    canvas.paste(resized, (x, y), resized)
    return canvas


_VALID_THUMBNAIL_OVERLAY_MODES = ("ai", "preset_text")


def _get_thumbnail_overlay_mode(db_cfg: Any, profile_id: str, settings: dict) -> str:
    """Read profile's thumbnailOverlayMode. Returns 'ai' or 'preset_text'.

    Reads the profile's image_config from the database and extracts the
    thumbnailOverlayMode field. Defaults to 'ai' if the field is absent
    or contains an invalid value.
    """
    try:
        image_config = db_get_profile_image_config(db_cfg, profile_id)
    except Exception:
        return "ai"
    if not isinstance(image_config, dict):
        return "ai"
    mode = image_config.get("thumbnailOverlayMode", "ai")
    if mode not in _VALID_THUMBNAIL_OVERLAY_MODES:
        return "ai"
    return mode
