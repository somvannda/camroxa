"""Auto-video pipeline handlers extracted from MainWindow.

Handles:
- auto_video_tick: periodic check for batches ready to convert
- _try_start_auto_video_channel: spawn conversion workers for a channel
- _safe_batch_suffix: generate safe filename suffix from batch ID
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

from ..database.music_db import get_batch_run_dirs_by_batch_id, get_latest_suno_output_dirs_by_batch_id
from ..services.video_export import ExportSettings
from ..features.video_export.export_gate import export_gate



class AutoVideoHandlersMixin:
    """Mixin providing auto-video pipeline methods for MainWindow."""

    def _export_reel_videos(self, plan, settings: dict, role: str) -> list[str]:
        """Export 9:16 reel MP4s for each MP3 track after standard export completes.

        Resolves the reel plan from the profile's reelTemplateId, then renders
        one 9:16 MP4 per MP3 track with `_REEL` suffix naming.
        On individual track failure: logs, skips that reel, continues remaining.

        Returns list of successfully exported reel MP4 paths.
        """
        reel_plan = self.auto_video_coordinator.resolve_reel_plan(plan, settings)
        if reel_plan is None:
            # Warning already emitted by resolve_reel_plan
            return []

        reel_mp4s: list[str] = []
        total = len(reel_plan.mp3s)

        for idx, mp3_path in enumerate(reel_plan.mp3s, start=1):
            stem = Path(mp3_path).stem
            reel_output_path = str(Path(reel_plan.output_dir) / f"{stem}_REEL.mp4")

            # Skip if reel already exists and is valid (> 50KB)
            if Path(reel_output_path).exists():
                try:
                    if int(Path(reel_output_path).stat().st_size) > 50_000:
                        reel_mp4s.append(reel_output_path)
                        continue
                except Exception:
                    pass

            self.bus.music_event.emit(
                {"type": "auto_video_status", "message": f"Auto-Reel: exporting {role} {idx}/{total}"}
            )

            # The visualizer writes output as {stem}.mp4 in the output_dir.
            # Since the standard {stem}.mp4 already exists, we protect it
            # during the reel export, then rename the reel output.
            standard_mp4_path = Path(reel_plan.output_dir) / f"{stem}.mp4"
            backup_path = Path(reel_plan.output_dir) / f"{stem}.mp4._std_backup"
            backed_up = False

            try:
                # Protect existing standard MP4
                if standard_mp4_path.exists():
                    standard_mp4_path.rename(backup_path)
                    backed_up = True

                export_gate.acquire()
                try:
                    export_gate.throttle_spawn()
                    self.auto_video_coordinator.execute_single_export(
                        mp3_path=mp3_path,
                        template=reel_plan.reel_template,
                        bg_path=reel_plan.bg_path,
                        logo_path=reel_plan.logo_path,
                        es=ExportSettings(
                            ffmpeg_path=reel_plan.ffmpeg_path,
                            output_dir=reel_plan.output_dir,
                            fps=30,
                            width=reel_plan.width,
                            height=reel_plan.height,
                            speed_mode=reel_plan.speed_mode,
                        ),
                    )
                finally:
                    export_gate.release()

                # Rename produced file from {stem}.mp4 to {stem}_REEL.mp4
                if standard_mp4_path.exists():
                    standard_mp4_path.rename(reel_output_path)
                    reel_mp4s.append(reel_output_path)
                else:
                    # Export didn't produce expected file
                    raise RuntimeError(f"Reel export did not produce {standard_mp4_path.name}")

            except Exception as e:
                self.bus.music_event.emit(
                    {"type": "auto_video_status", "message": f"Auto-Reel: {role} track {stem} failed · {str(e)[:200]}"}
                )
            finally:
                # Restore the standard MP4 from backup
                if backed_up and backup_path.exists():
                    try:
                        backup_path.rename(standard_mp4_path)
                    except Exception:
                        pass

        return reel_mp4s

    def _safe_batch_suffix(self, batch_id: str) -> str:
        text = str(batch_id or "").strip()
        m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-(\d+)-(\d+)$", text)
        if m:
            return f"{m.group(1)}_{m.group(2)}_{m.group(3)}"
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)
        return safe[-80:] if len(safe) > 80 else safe

    def _auto_video_tick(self):
        settings = self._music_settings()
        if not bool(settings.get("autoVideoAfterSuno", False)):
            return
        if not self.db_cfg:
            return
        if bool(self._export_batches):
            return
        # Allow multiple channels to process in parallel
        active_channels = getattr(self, "_auto_video_active_channels", None)
        if not isinstance(active_channels, set):
            active_channels = set()
            self._auto_video_active_channels = active_channels
        # Limit max parallel channels
        max_parallel = max(1, int(settings.get("perfExportParallelBatches", 2) or 2))
        if len(active_channels) >= max_parallel:
            return
        batches = getattr(self, "_auto_video_batches", None)
        if not isinstance(batches, dict) or not batches:
            return
        done = getattr(self, "_auto_video_done", None)
        if not isinstance(done, set):
            done = set()
            self._auto_video_done = done
        for batch_id, meta in list(batches.items()):
            if len(active_channels) >= max_parallel:
                return
            if not isinstance(meta, dict):
                continue
            ok_profile_id = str(meta.get("okProfileId", "")).strip()
            alt_profile_id = str(meta.get("altProfileId", "")).strip()
            if not ok_profile_id or not alt_profile_id:
                continue
            dirs = get_batch_run_dirs_by_batch_id(self.db_cfg, batch_id)
            if not str(dirs.get("okDir", "")).strip():
                dirs = get_latest_suno_output_dirs_by_batch_id(self.db_cfg, batch_id)
            ok_dir = str(dirs.get("okDir", "")).strip()
            alt_dir = str(dirs.get("altDir", "")).strip()
            if ok_dir:
                self._try_start_auto_video_channel(batch_id, ok_profile_id, "OK", ok_dir, done)
            if alt_dir and len(active_channels) < max_parallel:
                self._try_start_auto_video_channel(batch_id, alt_profile_id, "ALT", alt_dir, done)

    def _try_start_auto_video_channel(self, batch_id: str, profile_id: str, role: str, output_dir: str, done: set) -> bool:
        key = (str(batch_id), str(profile_id), str(role))
        if key in done:
            return False
        active_channels = getattr(self, "_auto_video_active_channels", set())
        if key in active_channels:
            return False
        settings = self._music_settings()
        plan = self.auto_video_coordinator.resolve_channel_plan(batch_id, profile_id, role, output_dir, settings)
        if plan is None:
            return False
        # Enforce the GLOBAL concurrent-subprocess cap across all channels.
        # videoExportWorkers is the total budget, not per-channel.
        try:
            export_gate.set_limit(int(settings.get("videoExportWorkers", 1) or 1))
        except Exception:
            pass
        active_channels.add(key)
        self._auto_video_active_channels = active_channels
        self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Video: exporting {role} ({Path(plan.output_dir).name})"})

        def work():
            ok = False
            merged_path = ""
            reel_merged_path = ""
            try:
                suffix = self._safe_batch_suffix(batch_id)
                expected_mp4s = self.auto_video_coordinator.build_expected_mp4s(plan)
                pending = self.auto_video_coordinator.resolve_pending_mp3s(plan, expected_mp4s)

                workers = plan.export_workers
                done_count = {"n": len(plan.mp3s) - len(pending)}
                lock = threading.Lock()
                err: dict[str, str] = {}

                def worker_loop():
                    while True:
                        with lock:
                            if err:
                                return
                            if not pending:
                                return
                            mp3_path = pending.pop(0)
                            current = int(done_count["n"]) + 1
                        self.bus.music_event.emit(
                            {"type": "auto_video_status", "message": self.auto_video_coordinator.build_export_progress_message(role, current, len(plan.mp3s), workers)}
                        )
                        try:
                            export_gate.acquire()
                            try:
                                # Space out interpreter cold-starts so 5+
                                # subprocesses don't thrash the disk loading
                                # numpy/moderngl/pygame all at once.
                                export_gate.throttle_spawn()
                                self.auto_video_coordinator.execute_single_export(
                                    mp3_path=mp3_path,
                                    template=plan.template,
                                    bg_path=plan.bg_path,
                                    logo_path=plan.logo_path,
                                    es=ExportSettings(
                                        ffmpeg_path=plan.ffmpeg_path,
                                        output_dir=plan.output_dir,
                                        fps=30,
                                        width=plan.width,
                                        height=plan.height,
                                        speed_mode=plan.speed_mode,
                                    ),
                                )
                            finally:
                                export_gate.release()
                        except Exception as e2:
                            with lock:
                                if not err:
                                    err["msg"] = str(e2)
                            self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Video: {role} failed · {str(e2)[:200]}"})
                            return
                        with lock:
                            done_count["n"] = int(done_count["n"]) + 1

                threads = []
                for _w in range(workers):
                    t = threading.Thread(target=worker_loop, daemon=True)
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
                if err:
                    raise RuntimeError(str(err.get("msg", "export failed")))
                ok = True
                # --- Reel export phase (runs after standard export) ---
                reel_mp4s: list[str] = []
                if settings.get("autoReelAfterVideo"):
                    reel_mp4s = self._export_reel_videos(plan, settings, role)
                # Gate merge step on autoMergeAfterVideo setting (NOT videoAutoMergeMp4)
                if settings.get("autoMergeAfterVideo"):
                    # Track merge in progress for real-time UI display
                    merging_dirs = getattr(self, "_auto_video_merging_dirs", None)
                    if not isinstance(merging_dirs, set):
                        merging_dirs = set()
                        self._auto_video_merging_dirs = merging_dirs
                    merging_dirs.add(str(plan.output_dir))
                    try:
                        merged_filename = f"MERGED_{role}_{suffix}.mp4"
                        merged_full_path = str(Path(plan.output_dir) / merged_filename)
                        self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Video: merging {role} ({Path(plan.output_dir).name})..."})
                        self.merge_worker.merge(plan.ffmpeg_path, expected_mp4s, merged_full_path)
                        merged_path = merged_full_path
                        self.bus.music_event.emit(
                            {"type": "auto_video_status", "message": self.auto_video_coordinator.build_export_complete_message(role, Path(plan.output_dir).name, len(expected_mp4s))}
                        )
                    except Exception as e:
                        merged_path = ""
                        self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Video: merge failed · {str(e)[:200]}"})
                    finally:
                        merging_dirs.discard(str(plan.output_dir))
                else:
                    merged_path = ""
                # --- Reel merge phase (independent from standard merge) ---
                if settings.get("autoMergeAfterVideo") and settings.get("autoReelAfterVideo") and len(reel_mp4s) >= 2:
                    try:
                        reel_merged_filename = f"MERGED_REEL_{role}_{suffix}.mp4"
                        reel_merged_full_path = str(Path(plan.output_dir) / reel_merged_filename)
                        self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Reel: merging {role} ({Path(plan.output_dir).name})..."})
                        self.merge_worker.merge(plan.ffmpeg_path, reel_mp4s, reel_merged_full_path)
                        reel_merged_path = reel_merged_full_path
                        self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Reel: merge complete {role} · {len(reel_mp4s)} reel files"})
                    except Exception as e_reel:
                        reel_merged_path = ""
                        self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Reel: merge failed · {str(e_reel)[:200]}"})
            except Exception as e:
                merged_path = ""
                self.bus.music_event.emit({"type": "auto_video_status", "message": f"Auto-Video: {role} error · {str(e)[:200]}"})
                ok = False
            finally:
                try:
                    active_channels.discard(key)
                except Exception:
                    pass
                self.bus.music_event.emit({"type": "auto_video_done", "ok": ok, "output": merged_path, "reelOutput": reel_merged_path, "role": role, "batchId": batch_id, "profileId": profile_id})

        threading.Thread(target=work, daemon=True).start()
        done.add(key)
        return True

    def _handle_auto_video_status(self, event: dict) -> None:
        message = str(event.get("message", "")).strip()
        if message:
            self._set_music_status(message)

    def _handle_auto_video_done(self, event: dict) -> None:
        # NOTE: Intentionally reads only "output" (standard merged path) and ignores
        # "reelOutput" (reel merged path). Reel videos are excluded from YouTube
        # auto-upload by design — they target future Facebook Reel automation.
        # See: Requirements 11.2, 11.4
        out = str(event.get("output", "")).strip()
        message = f"Auto-Video: done{f' · {Path(out).name}' if out else ''}"
        self._set_music_status(message)
        if out and bool(self._music_settings().get("autoUploadYouTube", False)) and bool(self.db_cfg):
            batch_id = str(event.get("batchId", "")).strip()
            profile_id = str(event.get("profileId", "")).strip()
            role = str(event.get("role", "")).strip()
            self._youtube_oauth_controller.enqueue_youtube_upload_for_merge(batch_id=batch_id, profile_id=profile_id, role=role, merged_mp4_path=out)

    def _start_auto_merge_export(self) -> None:
        return self.export_coordinator.start_auto_merge_export()

    def _start_auto_merge_export_for_outputs(self, mp4_paths: list[str], output_dir: str) -> None:
        return self.export_coordinator.start_auto_merge_export_for_outputs(mp4_paths, output_dir)
