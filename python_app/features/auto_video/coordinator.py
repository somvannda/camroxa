"""Auto-video feature coordinator.

Orchestrates the automatic video generation pipeline after Suno batches complete:
- Directory scanning for MP3 files
- Background image / template resolution
- Export worker spawning and progress tracking
- Merge invocation coordination

Uses dependency injection to avoid direct MainWindow references.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..ports import LoggerPort


@dataclass
class AutoVideoChannelPlan:
    """Resolved inputs for one auto-video channel export."""
    batch_id: str
    profile_id: str
    role: str
    output_dir: str
    mp3s: list[str]
    bg_path: str
    logo_path: str
    template: dict
    ffmpeg_path: str
    expected_count: int
    width: int
    height: int
    speed_mode: str
    export_workers: int


@dataclass
class AutoMergePlan:
    """Resolved inputs for an auto-merge export."""
    ffmpeg_path: str
    output_dir: str
    mp4_files: list[str]
    target_path: str
    mp3_dir_name: str
    timestamp: str


@dataclass
class AutoVideoReelPlan:
    """Resolved inputs for one auto-video reel (9:16 portrait) export."""
    reel_template: dict     # Parsed template JSON for 9:16 rendering
    width: int = 1080       # Always 1080
    height: int = 1920      # Always 1920
    mp3s: list[str] = field(default_factory=list)  # Same MP3 list from the standard plan
    bg_path: str = ""       # Same background image
    logo_path: str = ""     # Same logo from profile
    output_dir: str = ""    # Same output directory
    ffmpeg_path: str = ""   # FFmpeg executable path
    speed_mode: str = "balanced"  # Export speed mode
    export_workers: int = 1      # Number of parallel export workers


class AutoVideoCoordinator:
    """Coordinates auto-video generation lifecycle.

    All host dependencies are injected via constructor parameters so the
    coordinator is instantiable without a QApplication.
    """

    def __init__(
        self,
        *,
        db_cfg_accessor: Callable[[], Any],
        settings_accessor: Callable[[], dict],
        profile_accessor: Callable[[str], dict],
        get_video_template_fn: Callable[[str], Any],
        resolved_output_resolution_fn: Callable[[dict], tuple[int, int]],
        auto_video_batches_accessor: Callable[[], dict],
        ffmpeg_path_accessor: Callable[[], str],
        export_batch_state_accessor: Callable[[], dict],
        logger: LoggerPort | None = None,
    ) -> None:
        if db_cfg_accessor is None:
            raise ValueError("AutoVideoCoordinator requires a non-None db_cfg_accessor")
        if settings_accessor is None:
            raise ValueError("AutoVideoCoordinator requires a non-None settings_accessor")
        if profile_accessor is None:
            raise ValueError("AutoVideoCoordinator requires a non-None profile_accessor")
        if get_video_template_fn is None:
            raise ValueError("AutoVideoCoordinator requires a non-None get_video_template_fn")
        if resolved_output_resolution_fn is None:
            raise ValueError("AutoVideoCoordinator requires a non-None resolved_output_resolution_fn")
        self._db_cfg_accessor = db_cfg_accessor
        self._settings_accessor = settings_accessor
        self._profile_accessor = profile_accessor
        self._get_video_template_fn = get_video_template_fn
        self._resolved_output_resolution_fn = resolved_output_resolution_fn
        self._auto_video_batches_accessor = auto_video_batches_accessor if auto_video_batches_accessor is not None else (lambda: {})
        self._ffmpeg_path_accessor = ffmpeg_path_accessor if ffmpeg_path_accessor is not None else (lambda: "")
        self._export_batch_state_accessor = export_batch_state_accessor if export_batch_state_accessor is not None else (lambda: {})
        self._logger = logger

    def resolve_channel_plan(
        self,
        batch_id: str,
        profile_id: str,
        role: str,
        output_dir: str,
        settings: dict,
    ) -> AutoVideoChannelPlan | None:
        """Resolve all inputs needed to start one auto-video channel.

        Returns None if any prerequisite is missing (caller should skip silently).
        """
        from ...database.image_db import get_ready_background_output

        ffmpeg_path = self._find_ffmpeg(settings)
        if not ffmpeg_path:
            return None

        out_dir = Path(str(output_dir)).resolve()
        if not out_dir.exists() or not out_dir.is_dir():
            return None

        mp3s = sorted([str(p) for p in out_dir.glob("*.mp3") if p.is_file()])
        if not mp3s:
            return None

        expected_count = self._resolve_expected_count(batch_id)
        if expected_count > 0 and len(mp3s) < expected_count:
            return None
        if expected_count > 0 and len(mp3s) > expected_count:
            mp3s = mp3s[:expected_count]

        db_cfg = self._db_cfg_accessor()
        bg_path = get_ready_background_output(db_cfg, batch_id=batch_id, profile_id=profile_id)
        if not bg_path or not Path(bg_path).exists():
            return None

        profile = self._profile_accessor(profile_id)
        tpl_id = str(profile.get("videoTemplateId", "")).strip()
        if not tpl_id:
            return None

        tpl_row = self._get_video_template_fn(tpl_id)
        if tpl_row is None:
            return None

        logo_path = str(profile.get("logoPath", "")).strip()
        tpl = dict(tpl_row.template or {}) if hasattr(tpl_row, 'template') else dict(tpl_row) if isinstance(tpl_row, dict) else {}
        ow, oh = self._resolved_output_resolution_fn(profile)
        speed_mode = str(settings.get("videoExportSpeedMode", "balanced")).strip() or "balanced"
        export_workers = self._resolve_export_workers(settings, len(mp3s))

        return AutoVideoChannelPlan(
            batch_id=batch_id,
            profile_id=profile_id,
            role=role,
            output_dir=str(out_dir),
            mp3s=mp3s,
            bg_path=bg_path,
            logo_path=logo_path,
            template=tpl,
            ffmpeg_path=ffmpeg_path,
            expected_count=expected_count,
            width=int(ow),
            height=int(oh),
            speed_mode=speed_mode,
            export_workers=export_workers,
        )

    def build_export_progress_message(self, role: str, current: int, total: int, workers: int) -> str:
        """Build the progress status message for export workers."""
        return f"Auto-Video: exporting {role} {current}/{total} (workers {workers})"

    def build_export_complete_message(self, role: str, batch_name: str, mp4_count: int) -> str:
        """Build the export-complete status message."""
        return f"Auto-Video: export complete for {role} ({batch_name}) · {mp4_count} MP4(s)"

    def resolve_auto_merge_plan(
        self,
        settings: dict,
        *,
        export_batch_ffmpeg_path: str = "",
        export_batch_output_dir: str = "",
        export_batch_mp3s: list[str] | None = None,
        export_outputs_by_mp3: dict[str, str] | None = None,
        mp3_dir: str = "",
    ) -> AutoMergePlan | None:
        """Resolve all inputs needed to start an auto-merge export.

        Returns None if any prerequisite is missing (caller should skip silently).
        """
        from ...services.video_export import find_ffmpeg_from_path_hint

        ffmpeg_path = str(
            settings.get("ffmpegPath", "")
            or export_batch_ffmpeg_path
            or find_ffmpeg_from_path_hint(self._ffmpeg_path_accessor() or "")
            or ""
        ).strip()
        output_dir = str(
            settings.get("outputDir", "")
            or export_batch_output_dir
            or ""
        ).strip()
        if not ffmpeg_path or not output_dir:
            return None

        mp4s: list[str] = []
        batch_mp3s: list[str] = export_batch_mp3s or []
        outputs_map: dict[str, str] = export_outputs_by_mp3 or {}
        for mp3 in batch_mp3s:
            out = str(outputs_map.get(mp3, "") or "").strip()
            if out:
                mp4s.append(out)
        if len(mp4s) != len(batch_mp3s):
            return None

        mp3_dir_name = Path(str(mp3_dir or "export")).name or "export"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = Path(output_dir) / f"{mp3_dir_name}_MERGED_{stamp}.mp4"
        idx = 2
        while target.exists():
            target = Path(output_dir) / f"{mp3_dir_name}_MERGED_{stamp}-{idx}.mp4"
            idx += 1

        return AutoMergePlan(
            ffmpeg_path=ffmpeg_path,
            output_dir=output_dir,
            mp4_files=mp4s,
            target_path=str(target),
            mp3_dir_name=mp3_dir_name,
            timestamp=stamp,
        )

    def _find_ffmpeg(self, settings: dict) -> str | None:
        from ...services.video_export import find_ffmpeg_from_path_hint

        return find_ffmpeg_from_path_hint(
            str(settings.get("ffmpegPath", "")).strip()
            or self._ffmpeg_path_accessor()
        )

    def _resolve_expected_count(self, batch_id: str) -> int:
        batches = self._auto_video_batches_accessor()
        meta = batches.get(str(batch_id).strip(), {}) if isinstance(batches, dict) else {}
        return int(meta.get("songsPerBatch", 0) or 0)

    @staticmethod
    def _resolve_export_workers(settings: dict, pending_count: int) -> int:
        workers = int(settings.get("videoExportWorkers", 1) or 1)
        workers = max(1, min(10, workers))
        return min(workers, max(1, pending_count))

    def resolve_reel_plan(
        self,
        plan: AutoVideoChannelPlan,
        settings: dict,
    ) -> AutoVideoReelPlan | None:
        """Resolve all inputs needed to start one auto-video reel (9:16) export.

        Returns None if the profile has no reel template configured or the
        template cannot be found (caller should skip with a warning).
        """
        profile = self._profile_accessor(plan.profile_id)
        reel_template_id = str(profile.get("reelTemplateId", "")).strip() if profile else ""

        if not reel_template_id:
            if self._logger:
                self._logger.warning(
                    f"Auto-Reel: skipped {plan.role} — no reel template configured"
                )
            return None

        tpl_row = self._get_video_template_fn(reel_template_id)
        if tpl_row is None:
            if self._logger:
                self._logger.warning(
                    f"Auto-Reel: skipped {plan.role} — no reel template configured"
                )
            return None

        # Extract template dict from the row object
        tpl = (
            dict(tpl_row.template or {})
            if hasattr(tpl_row, "template")
            else dict(tpl_row) if isinstance(tpl_row, dict) else {}
        )

        speed_mode = str(settings.get("videoExportSpeedMode", "balanced")).strip() or "balanced"
        export_workers = self._resolve_export_workers(settings, len(plan.mp3s))

        return AutoVideoReelPlan(
            reel_template=tpl,
            width=1080,
            height=1920,
            mp3s=list(plan.mp3s),
            bg_path=plan.bg_path,
            logo_path=plan.logo_path,
            output_dir=plan.output_dir,
            ffmpeg_path=plan.ffmpeg_path,
            speed_mode=speed_mode,
            export_workers=export_workers,
        )

    # ------------------------------------------------------------------ #
    #  Core export orchestration (decoupled from MainWindow UI state)     #
    # ------------------------------------------------------------------ #

    def check_mp3_readiness(self, role: str, plan: AutoVideoChannelPlan) -> tuple[bool, str]:
        """Validate that MP3s are ready for export.

        Returns (True, "") on success, (False, reason) on failure.
        """
        if not plan.mp3s:
            return False, f"No MP3s found for {role}"
        if plan.expected_count > 0 and len(plan.mp3s) < plan.expected_count:
            return (
                False,
                f"MP3s incomplete for {role}: {len(plan.mp3s)}/{plan.expected_count}",
            )
        return True, ""

    def build_expected_mp4s(self, plan: AutoVideoChannelPlan) -> list[str]:
        """Resolve the list of expected MP4 output paths from the plan."""
        return [str(Path(plan.output_dir) / f"{Path(mp3).stem}.mp4") for mp3 in plan.mp3s]

    def resolve_pending_mp3s(
        self,
        plan: AutoVideoChannelPlan,
        expected_mp4s: list[str],
    ) -> list[str]:
        """Return MP3s that still need export (skip existing valid MP4s)."""
        pending: list[str] = []
        for mp3, target_mp4_str in zip(plan.mp3s, expected_mp4s):
            target_mp4 = Path(target_mp4_str)
            if target_mp4.exists():
                try:
                    if int(target_mp4.stat().st_size) > 50_000:
                        continue
                except Exception:
                    pass
            pending.append(mp3)
        return pending

    def execute_single_export(
        self,
        mp3_path: str,
        template: dict,
        bg_path: str,
        logo_path: str,
        es: Any,
    ) -> None:
        """Run one export job synchronously.

        Raises RuntimeError on export failure.
        """
        from ...services.video_export import ExportJob
        from ...visualizer.contracts import RenderRequest

        done_evt = threading.Event()
        exit_code = {"code": 1}

        def on_exit(code: int):
            exit_code["code"] = int(code)
            done_evt.set()

        render_request = RenderRequest(
            audio_path=mp3_path,
            output_path=es.output_dir,
            width=es.width,
            height=es.height,
            fps=es.fps,
            template=template,
            background_path=bg_path,
            logo_path=logo_path,
        )
        job = ExportJob.from_render_request(
            render_request,
            ffmpeg_path=es.ffmpeg_path,
            speed_mode=getattr(es, 'speed_mode', 'balanced'),
            on_event=lambda _evt: None,
            on_exit=on_exit,
        )
        job.start()
        done_evt.wait()
        if int(exit_code["code"]) != 0:
            raise RuntimeError(f"Export failed for {Path(mp3_path).name}")
