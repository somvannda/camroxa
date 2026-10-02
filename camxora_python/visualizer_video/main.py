from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from shared.lib.subprocess_utils import popen_hidden

from .audio import AudioAnalyzer
from .automation import Automation, apply_automations
from .config import load_template_any, load_template_any_raw
from .effects import BloomConfig, RgbSplitConfig, apply_bloom, apply_rgb_split
from .particles import ParticleConfig, ParticleSystem
from .renderer import RenderSize


def _send(evt: dict) -> None:
    print(f"MG_EVENT {json.dumps(evt, ensure_ascii=True)}", flush=True)


def _stem(p: str) -> str:
    return Path(p).stem or "output"


def normalize_visualizer_job_argv(argv: list[str]) -> list[str]:
    """Strip launcher flags so argparse sees mp3_path as the first positional arg."""
    parts = [str(part) for part in argv if part is not None]
    if len(parts) > 1 and parts[1] == "--visualizer":
        return [parts[0], *parts[2:]]
    if len(parts) > 2 and parts[1] == "-m" and parts[2] == "visualizer.main":
        return ["visualizer.main", *parts[3:]]
    return parts


def main() -> int:
    return run_visualizer_argv(sys.argv)


def run_visualizer_argv(argv: list[str]) -> int:
    saved_argv = sys.argv[:]
    sys.argv = list(argv)
    try:
        return _main_impl()
    finally:
        sys.argv = saved_argv


def _main_impl() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mp3_path")
    parser.add_argument("template_path")
    parser.add_argument("--templateB64", dest="template_b64", default="")
    parser.add_argument("--background", dest="background_path", default="")
    parser.add_argument("--logo", dest="logo_path", default="")
    parser.add_argument("--outputDir", dest="output_dir", default="")
    parser.add_argument("--output", dest="output_path", default="")
    parser.add_argument("--ffmpeg", dest="ffmpeg_path", default="ffmpeg")
    parser.add_argument("--renderer", dest="renderer", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument(
        "--speedMode",
        dest="speed_mode",
        choices=["balanced", "fast", "very_fast", "quality", "best_quality", "master", "best"],
        default="balanced",
    )
    parser.add_argument("--fps", dest="fps", type=int, default=60)
    parser.add_argument("--width", dest="width", type=int, default=1920)
    parser.add_argument("--height", dest="height", type=int, default=1080)
    parser.add_argument("--previewPng", dest="preview_png", default="")
    parser.add_argument("--previewFrame", dest="preview_frame", type=int, default=150)
    parser.add_argument("--livePreview", dest="live_preview", action="store_true", default=False)
    args = parser.parse_args()

    mp3_path = str(args.mp3_path)
    template_path = str(args.template_path)
    template_b64 = str(args.template_b64 or "").strip()
    if template_b64:
        raw = json.loads(base64.b64decode(template_b64).decode("utf-8"))
        template = load_template_any_raw(raw)
    else:
        template = load_template_any(template_path)

    background_path = str(args.background_path or "").strip() or str(template.get("background", "")).strip()
    if not background_path and not args.live_preview:
        raise RuntimeError("Background path missing (template.background or --background)")
    logo_settings = template.get("logoSettings") if isinstance(template.get("logoSettings"), dict) else {}
    logo_enabled = bool(logo_settings.get("enabled", True))
    if not logo_enabled:
        args.logo_path = ""

    output_dir = str(args.output_dir or "").strip() or str(Path.cwd() / "output")
    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)

    explicit_out = str(getattr(args, "output_path", "") or "").strip()
    if explicit_out:
        out_path = Path(explicit_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_path = out_base / f"{_stem(mp3_path)}.mp4"

    fps = int(args.fps)
    size = RenderSize(width=int(args.width), height=int(args.height))
    speed_mode = str(args.speed_mode or "balanced").strip().lower() or "balanced"
    if speed_mode in {"master", "best"}:
        speed_mode = "best_quality"

    def speed_params(mode: str) -> dict[str, str]:
        m = str(mode or "").strip().lower()
        if m in {"best", "master"}:
            m = "best_quality"
        if m == "very_fast":
            return {"nvenc_preset": "p1", "x264_preset": "ultrafast"}
        if m == "fast":
            return {"nvenc_preset": "p3", "x264_preset": "superfast"}
        if m == "best_quality":
            return {"nvenc_preset": "p7", "x264_preset": "medium"}
        if m == "quality":
            return {"nvenc_preset": "p5", "x264_preset": "veryfast"}
        # balanced
        return {"nvenc_preset": "p3", "x264_preset": "veryfast"}

    sp = speed_params(speed_mode)

    if str(args.renderer or "gpu").strip().lower() == "gpu":
        from .gpu_render import GpuOptions, render_preview_png, run_gpu_render, run_live_preview

        gopts = GpuOptions(
            mp3_path=mp3_path,
            background_path=background_path,
            output_dir=output_dir,
            template_path=template_path,
            template_b64=template_b64,
            logo_path=str(args.logo_path or "").strip(),
            ffmpeg_path=str(args.ffmpeg_path or "ffmpeg").strip(),
            fps=fps,
            width=size.width,
            height=size.height,
            speed_mode=speed_mode,
            output_path=explicit_out,
        )
        if args.live_preview:
            return run_live_preview(gopts)
            
        preview_png = str(args.preview_png or "").strip()
        if preview_png:
            _send({"status": "running", "message": "Rendering preview PNG...", "progress": 0.0})
            out_png = render_preview_png(gopts, preview_png, preview_frame=int(args.preview_frame))
            _send({"status": "done", "message": "Preview ready", "progress": 1.0, "outputPath": str(out_png)})
            return 0
        
        # Do not catch exceptions here! Let the GPU renderer crash so we can see the exact error traceback
        from features.video.lib.export_cancel import export_cancel_requested

        return run_gpu_render(gopts, cancel_check=export_cancel_requested)

    # CPU path only — keep pygame out of the GPU export import graph so
    # OpenBLAS/librosa.stft is not poisoned before audio analysis.
    import pygame

    _send({"status": "running", "message": "Analyzing audio...", "progress": 0.0})
    point_count = 1024 # Sync with gpu_render
    analyzer = AudioAnalyzer(mp3_path=mp3_path, fps=fps, point_count=point_count)
    total_frames = analyzer.info.frames

    background_img = pygame.image.load(background_path)
    background_img = pygame.transform.smoothscale(background_img, (size.width, size.height))

    logo_path = str(args.logo_path or "").strip()
    logo_img = None
    if logo_path:
        li = pygame.image.load(logo_path)
        w, h = li.get_width(), li.get_height()
        target = int(round(size.height * 0.55))
        if w > 0 and h > 0 and target > 0:
            scale = min(target / float(w), target / float(h))
            nw = max(1, int(round(w * scale)))
            nh = max(1, int(round(h * scale)))
            li = pygame.transform.smoothscale(li, (nw, nh))
        logo_img = li.convert_alpha()

    particles_cfg_raw = template.get("particles") if isinstance(template.get("particles"), dict) else {}
    particles_cfg = ParticleConfig(
        enabled=bool(particles_cfg_raw.get("enabled", False)),
        max_count=int(particles_cfg_raw.get("max_count", 800)),
        spawn_rate=float(particles_cfg_raw.get("spawn_rate", 80.0)),
        lifetime_sec=float(particles_cfg_raw.get("lifetime_sec", 2.0)),
        size=float(particles_cfg_raw.get("size", 2.0)),
        opacity=float(particles_cfg_raw.get("opacity", 0.35)),
        color=tuple(particles_cfg_raw.get("color", (255, 255, 255))),
        speed=float(particles_cfg_raw.get("speed", 120.0)),
    )
    particles = ParticleSystem(particles_cfg, width=size.width, height=size.height)

    effects_raw = template.get("effects") if isinstance(template.get("effects"), dict) else {}
    bloom_raw = effects_raw.get("bloom") if isinstance(effects_raw.get("bloom"), dict) else {}
    rgb_raw = effects_raw.get("rgb_split") if isinstance(effects_raw.get("rgb_split"), dict) else {}
    shake_raw = effects_raw.get("camera_shake") if isinstance(effects_raw.get("camera_shake"), dict) else {}

    bloom_cfg = BloomConfig(
        enabled=bool(bloom_raw.get("enabled", False)),
        strength=float(bloom_raw.get("strength", 1.0)),
        blur_radius=int(bloom_raw.get("blur_radius", 11)),
        threshold=float(bloom_raw.get("threshold", 0.75)),
        opacity=float(bloom_raw.get("opacity", 0.9)),
    )
    rgb_cfg = RgbSplitConfig(
        enabled=bool(rgb_raw.get("enabled", False)),
        red_offset=tuple(rgb_raw.get("red_offset", (2, 0))),
        green_offset=tuple(rgb_raw.get("green_offset", (0, 0))),
        blue_offset=tuple(rgb_raw.get("blue_offset", (-2, 0))),
        opacity=float(rgb_raw.get("opacity", 0.6)),
    )
    shake_enabled = bool(shake_raw.get("enabled", False))
    shake_intensity = float(shake_raw.get("intensity", 8.0))
    shake_smoothing = float(shake_raw.get("smoothing", 0.85))
    shake_state = {"x": 0.0, "y": 0.0}

    autos_raw = template.get("automations") if isinstance(template.get("automations"), list) else []
    autos: list[Automation] = []
    for a in autos_raw:
        if not isinstance(a, dict):
            continue
        autos.append(
            Automation(
                source=str(a.get("source", "")),
                target=str(a.get("target", "")),
                multiplier=float(a.get("multiplier", 1.0)),
                offset=float(a.get("offset", 0.0)),
                smoothing=float(a.get("smoothing", 0.0)),
                clamp_min=float(a["clamp_min"]) if "clamp_min" in a else None,
                clamp_max=float(a["clamp_max"]) if "clamp_max" in a else None,
            )
        )

    _send({"status": "running", "message": f"Rendering frames ({total_frames})...", "progress": 0.0, "totalFrames": total_frames})

    def blend_flag(mode: str) -> int:
        m = str(mode or "").lower().strip()
        if m == "additive":
            return pygame.BLEND_RGBA_ADD
        if m == "multiply":
            return pygame.BLEND_RGBA_MULT
        if m == "screen":
            return pygame.BLEND_RGBA_ADD
        return 0

    ffmpeg_path = str(args.ffmpeg_path or "").strip() or "ffmpeg"
    if os.name == "nt" and not ffmpeg_path.lower().endswith(".exe") and "\\" in ffmpeg_path:
        ffmpeg_path = f"{ffmpeg_path}.exe"

    def start_ffmpeg(codec: str) -> subprocess.Popen:
        cmd: list[str] = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostats",
            "-y",
            "-fflags",
            "+genpts",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{size.width}x{size.height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-i",
            mp3_path,
            "-af",
            "aresample=async=1000",
            "-c:v",
            codec,
        ]
        if codec == "h264_nvenc":
            from shared.lib.export_bitrate import ffmpeg_vbr_bitrate_args, recommended_vbr_ladder_kbps

            t_kbps, m_kbps, b_kbps = recommended_vbr_ladder_kbps(
                size.width, size.height, fps, speed_mode
            )
            cmd += [
                "-preset",
                sp["nvenc_preset"],
                "-rc",
                "vbr",
                *ffmpeg_vbr_bitrate_args(t_kbps, m_kbps, b_kbps),
            ]
        elif codec == "libx264":
            from shared.lib.export_bitrate import ffmpeg_vbr_bitrate_args, recommended_vbr_ladder_kbps

            t_kbps, m_kbps, b_kbps = recommended_vbr_ladder_kbps(
                size.width, size.height, fps, speed_mode
            )
            cmd += [
                "-preset",
                sp["x264_preset"],
                *ffmpeg_vbr_bitrate_args(t_kbps, m_kbps, b_kbps),
            ]
        cmd += [
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-shortest",
            str(out_path),
        ]
        err_file = open(Path(out_path).parent / f"ffmpeg_error_{uuid.uuid4().hex[:8]}.log", "w+", encoding="utf-8")
        enc = popen_hidden(cmd, stdin=subprocess.PIPE, stderr=err_file)
        enc._err_file = err_file
        return enc

    _send({"status": "running", "message": "Starting encoder...", "progress": 0.0})
    from visualizer_video.nvenc_capability import nvenc_error_indicates_unavailable, probe_h264_nvenc

    codec = "h264_nvenc" if probe_h264_nvenc(ffmpeg_path) else "libx264"
    enc = start_ffmpeg(codec)
    time.sleep(0.2)
    if enc.poll() is not None:
        enc._err_file.seek(0)
        err_txt = enc._err_file.read()
        if codec == "h264_nvenc" and (
            "Unknown encoder" in err_txt
            or "h264_nvenc" in err_txt
            or "nvenc" in err_txt
            or nvenc_error_indicates_unavailable(err_txt)
        ):
            enc._err_file.close()
            enc = start_ffmpeg("libx264")
        else:
            raise RuntimeError(err_txt.strip() or "FFmpeg encoder failed to start")

    for i in range(total_frames):
        fft = analyzer.fft_for_frame(i)
        feats = analyzer.features_for_frame(i)

        base_state = {
            "camera_shake.intensity": shake_intensity,
            "spectrum.scale": 1.0,
            "particles.spawn_rate": float(particles_cfg.spawn_rate),
            "effects.bloom.strength": float(bloom_cfg.strength),
            "effects.rgb_split.opacity": float(rgb_cfg.opacity),
        }
        state = apply_automations(base_state, feats, autos)

        dt = 1.0 / max(1.0, float(fps))
        if shake_enabled:
            target = float(state.get("camera_shake.intensity", shake_intensity)) * (0.35 + float(feats.get("bass", 0.0)) * 1.2 + float(feats.get("beat", 0.0)) * 1.5)
            jitter_x = (pygame.time.get_ticks() * 0.001 + i * 0.013) % 1.0
            jitter_y = (pygame.time.get_ticks() * 0.001 + i * 0.017) % 1.0
            tx = (jitter_x * 2.0 - 1.0) * target
            ty = (jitter_y * 2.0 - 1.0) * target
            s = max(0.0, min(0.99, shake_smoothing))
            shake_state["x"] = shake_state["x"] * s + tx * (1.0 - s)
            shake_state["y"] = shake_state["y"] * s + ty * (1.0 - s)
        else:
            shake_state["x"] = 0.0
            shake_state["y"] = 0.0

        scene = pygame.Surface((size.width, size.height), flags=pygame.SRCALPHA)
        off_x = int(round(shake_state["x"]))
        off_y = int(round(shake_state["y"]))

        for l in sorted(template.get("layers", []), key=lambda x: int(x.get("z_index", 0)) if isinstance(x, dict) else 0):
            if not isinstance(l, dict):
                continue
            if not bool(l.get("enabled", True)):
                continue
            layer_type = str(l.get("type", "")).lower().strip()
            opacity = float(l.get("opacity", 1.0))
            opacity = max(0.0, min(1.0, opacity))
            mode = str(l.get("blend_mode", "normal"))
            flag = blend_flag(mode)

            layer_surf = pygame.Surface((size.width, size.height), flags=pygame.SRCALPHA)

            if layer_type == "background":
                layer_surf.blit(background_img, (off_x, off_y))
                if logo_img is not None:
                    lw, lh = logo_img.get_width(), logo_img.get_height()
                    x = (size.width - lw) // 2 + off_x
                    y = (size.height - lh) // 2 + off_y
                    layer_surf.blit(logo_img, (x, y))
            elif layer_type == "particles":
                particles.update_cfg(
                    ParticleConfig(
                        enabled=bool(particles_cfg_raw.get("enabled", False)),
                        max_count=int(particles_cfg_raw.get("max_count", 800)),
                        spawn_rate=float(state.get("particles.spawn_rate", particles_cfg.spawn_rate)),
                        lifetime_sec=float(particles_cfg_raw.get("lifetime_sec", 2.0)),
                        size=float(particles_cfg_raw.get("size", 2.0)),
                        opacity=float(particles_cfg_raw.get("opacity", 0.35)),
                        color=tuple(particles_cfg_raw.get("color", (255, 255, 255))),
                        speed=float(particles_cfg_raw.get("speed", 120.0)),
                    )
                )
                particles.update(dt, feats)
                particles.render(layer_surf)
            elif layer_type == "spectrum":
                # CPU spectrum rendering is not fully supported with the new architecture.
                # If they fall back to CPU, it just won't render the spectrum layer correctly.
                # The primary path is always GPU.
                pass

            if opacity < 1.0:
                layer_surf.set_alpha(int(opacity * 255))
            scene.blit(layer_surf, (0, 0), special_flags=flag)

        bloom_cfg2 = BloomConfig(
            enabled=bloom_cfg.enabled,
            strength=float(state.get("effects.bloom.strength", bloom_cfg.strength)),
            blur_radius=bloom_cfg.blur_radius,
            threshold=bloom_cfg.threshold,
            opacity=bloom_cfg.opacity,
        )
        rgb_cfg2 = RgbSplitConfig(
            enabled=rgb_cfg.enabled,
            red_offset=rgb_cfg.red_offset,
            green_offset=rgb_cfg.green_offset,
            blue_offset=rgb_cfg.blue_offset,
            opacity=float(state.get("effects.rgb_split.opacity", rgb_cfg.opacity)),
        )

        surface = scene
        surface = apply_bloom(surface, bloom_cfg2)
        surface = apply_rgb_split(surface, rgb_cfg2)

        raw = pygame.image.tostring(surface, "RGBA")
        try:
            if enc.stdin is None:
                raise RuntimeError("FFmpeg stdin is not available")
            enc.stdin.write(raw)
        except (BrokenPipeError, OSError) as e:
            if hasattr(enc, "_err_file"):
                enc._err_file.seek(0)
                err_txt = enc._err_file.read()
            else:
                err_txt = ""
            raise RuntimeError(f"FFmpeg pipe closed unexpectedly: {err_txt} (OS Error: {e})")
        if i == 0 or (i + 1) % 10 == 0 or i + 1 == total_frames:
            _send(
                {
                    "status": "running",
                    "message": f"Rendering {i + 1}/{total_frames}",
                    "progress": float((i + 1) / max(1, total_frames)),
                    "frame": i + 1,
                    "totalFrames": total_frames,
                }
            )

    _send({"status": "running", "message": "Finalizing MP4...", "progress": 0.99})
    if enc.stdin is not None:
        try:
            enc.stdin.close()
        except Exception:
            pass
    code = enc.wait()
    if code != 0:
        if hasattr(enc, "_err_file"):
            enc._err_file.seek(0)
            err_txt = enc._err_file.read()
        else:
            err_txt = ""
        raise RuntimeError(err_txt.strip() or f"FFmpeg failed (exit code {code})")
        
    if hasattr(enc, "_err_file"):
        enc._err_file.close()

    _send({"status": "done", "message": "Exported MP4", "progress": 1.0, "outputPath": str(out_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
