"""Headless pipeline video export + merge for shell automation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject

from features.video.lib.desktop_video_automation import AutoVideoCandidate
from features.video.lib.pipeline_merge import (
    build_merged_output_path,
    collect_verified_merge_inputs,
    is_auto_merge_enabled_for_branch,
    list_branch_export_outputs,
    merge_encode_settings_from_context,
    merged_output_ready,
    resolve_merge_encode_settings,
    resolve_merge_run_dir,
)
from features.video.lib.video_billing import consume_video_operation, refund_video_operation
from features.video.lib.render_scene_request import (
    PIPELINE_EXPORT_FPS,
    build_pipeline_export_output_path,
    build_pipeline_render_scene_request,
    normalize_export_fps,
)
from features.video.services.template_normalizer import TemplateNormalizer
from features.video.services.video_local_store import VideoLocalStore
from features.video.workers.pipeline_export_worker import PipelineExportRequest, VideoPipelineExportWorker
from features.video.workers.pipeline_merge_worker import PipelineMergeRequest, VideoPipelineMergeWorker
from shared.models.desktop import VideoExportState, VideoWorkspaceState
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError
from shared.lib.export_codec import format_export_status_message, normalize_export_speed_mode
from shared.lib.export_tiers import resolve_export_tier_settings
from shared.services.shell_status import emit_shell_status
from shared.services.video_pipeline_activity import (
    any_video_pipeline_threads_running,
    is_app_quitting,
    track_video_pipeline_thread,
)
from shared.services.video_workspace_service import get_video_workspace_service


class PipelineAutomationService(QObject):
    """Runs pipeline export/merge without requiring the Video page to be open."""

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._store = VideoLocalStore()
        self._normalizer = TemplateNormalizer()
        self._settings: dict[str, Any] = {}
        self._export_worker: VideoPipelineExportWorker | None = None
        self._merge_worker: VideoPipelineMergeWorker | None = None
        self._merge_context: dict[str, Any] = {}
        self._busy = False
        self._video_charge: dict[str, Any] = {}
        self._merge_charge: dict[str, Any] = {}
        self._api = api
        self._auth_blocked = False

    def auth_blocked(self) -> bool:
        return self._auth_blocked

    def _workers_running(self) -> bool:
        return bool(
            (self._export_worker is not None and self._export_worker.isRunning())
            or (self._merge_worker is not None and self._merge_worker.isRunning())
        )

    def recover_stale_state(self) -> bool:
        """Clear stuck busy/export flags when no export or merge worker is alive."""
        workers_live = self._workers_running() or any_video_pipeline_threads_running()
        workspace = self._current_workspace()
        export_flagged = bool(
            workspace and (workspace.export.running or workspace.export.merge_running)
        )
        stale_busy = self._busy and not workers_live
        stale_flags = export_flagged and not workers_live
        if not stale_busy and not stale_flags:
            return False

        if stale_busy:
            self._busy = False

        if stale_flags and workspace is not None:
            self._publish_workspace(
                workspace.model_copy(
                    update={
                        "export": workspace.export.model_copy(
                            update={
                                "running": False,
                                "merge_running": False,
                                "current_status": (
                                    "Recovered stale export state — ready for a new export."
                                ),
                            }
                        )
                    }
                )
            )
        return True

    def is_busy(self) -> bool:
        self.recover_stale_state()
        return self._busy or self._workers_running()

    def cancel_active(self) -> bool:
        """Stop the in-flight pipeline export or merge (if any).

        Returns True when a live worker was asked to stop, or when stale
        busy/export flags were cleared so another Start Export can run.
        """
        cancelled_live = False
        export_worker = self._export_worker
        if export_worker is not None and export_worker.isRunning():
            export_worker.cancel()
            cancelled_live = True
        merge_worker = self._merge_worker
        if merge_worker is not None and merge_worker.isRunning():
            merge_worker.cancel()
            cancelled_live = True

        # Always poke the warm visualizer daemon — ExportJob.cancel does this
        # for registered jobs, but a hung daemon with no active job ref still
        # blocks Start Export via any_video_pipeline_threads_running().
        try:
            from features.video.services.visualizer_daemon import get_visualizer_daemon

            get_visualizer_daemon().cancel_active()
        except Exception:
            pass

        if cancelled_live:
            emit_shell_status("Stopping active video export/merge…", tone="neutral")
            return True

        if self.recover_stale_state() or self._busy:
            self._busy = False
            workspace = self._current_workspace()
            if workspace is not None and (
                workspace.export.running or workspace.export.merge_running
            ):
                self._publish_workspace(
                    workspace.model_copy(
                        update={
                            "export": workspace.export.model_copy(
                                update={
                                    "running": False,
                                    "merge_running": False,
                                    "current_status": "Export stopped.",
                                }
                            )
                        }
                    )
                )
            emit_shell_status("Cleared stuck video export state.", tone="neutral")
            return True
        return False

    def start(
        self,
        candidate: AutoVideoCandidate,
        *,
        settings: dict[str, Any],
        force_regenerate: bool = False,
        auto_merge: bool | None = None,
        mp3_paths: list[str] | None = None,
        repair_unhealthy: bool = False,
        force_selected: bool = False,
    ) -> bool:
        if is_app_quitting():
            return False
        if self.is_busy():
            return False
        if force_regenerate and not mp3_paths and not repair_unhealthy:
            self._clear_branch_exports(
                candidate.run_dir,
                candidate.batch_id,
                candidate.role,
                candidate.branch,
            )
        self._auth_blocked = False
        self._settings = dict(settings or {})
        workspace = self._store.set_template(candidate.template_id)
        if candidate.branch == "long" and candidate.output_resolution:
            workspace = self._store.set_output_resolution(
                candidate.output_resolution,
                settings=self._settings,
            )
        run_dir = str(candidate.run_dir or "").strip()
        background_path = str(candidate.background_path or "").strip()
        if not run_dir or not Path(run_dir).is_dir():
            emit_shell_status("Auto-video skipped: run directory is missing.")
            return False
        if not background_path or not Path(background_path).is_file():
            emit_shell_status("Auto-video skipped: branch background image is missing.")
            return False
        branch = "reel" if candidate.branch == "reel" else "long"
        nested_dir = resolve_merge_run_dir(run_dir, branch)
        if nested_dir:
            run_dir = nested_dir

        mp3_list = self._store.list_mp3_files(run_dir)
        if not mp3_list:
            emit_shell_status("Auto-video skipped: no MP3 files in run directory.")
            return False

        available_paths = [item.path for item in mp3_list]
        from features.video.lib.export_track_health import select_export_mp3_paths, unlink_track_export

        track_paths = select_export_mp3_paths(available_paths, requested=mp3_paths)
        if not track_paths:
            emit_shell_status("Auto-video skipped: none of the requested MP3 files are in the run folder.")
            return False
        template = self._build_renderer_template(workspace, track_paths=available_paths)
        if not template:
            emit_shell_status("Auto-video skipped: no video template is loaded.")
            return False

        # Match Manual Export encode defaults (Standard), not silent Draft 720p.
        tier = resolve_export_tier_settings(self._settings, pipeline=False)
        from features.video.lib.render_scene_request import REEL_EXPORT_RESOLUTION

        workspace_resolution = str(workspace.output_resolution or "").strip()
        long_resolution = workspace_resolution or tier.resolution
        output_resolution = REEL_EXPORT_RESOLUTION if branch == "reel" else long_resolution
        export_fps = self._resolve_export_fps(workspace)
        speed_mode = normalize_export_speed_mode(
            self._settings.get("videoExportSpeedMode"),
            default=tier.speed_mode,
        )
        # Preview always draws glow melt. Manual Standard keeps dual glow.
        # Only an explicit Draft tier may skip glow (very_fast/draft → 0 passes).
        if tier.tier != "draft" and speed_mode in {"very_fast", "draft"}:
            speed_mode = "balanced"
        scene = build_pipeline_render_scene_request(
            template=template,
            workspace={
                "templateId": workspace.template_id,
                "outputResolution": output_resolution,
                "logoPath": workspace.logo_path,
                "selectedMp3Path": mp3_list[0].path,
            },
            run_dir=run_dir,
            background_path=background_path,
            branch=branch,
            batch_id=candidate.batch_id,
            role=candidate.role,
            selected_mp3_path=mp3_list[0].path,
            fps=export_fps,
        )
        workers_raw = self._settings.get("videoExportWorkers", self._settings.get("perfExportWorkers", 1))
        from visualizer.export_gpu_tier import resolve_pipeline_export_workers

        worker_limit = resolve_pipeline_export_workers(
            workers_raw,
            default=1,
            speed_mode=speed_mode,
            width=int(scene.output.width),
            height=int(scene.output.height),
        )

        auto_merge = (
            bool(auto_merge)
            if auto_merge is not None
            else is_auto_merge_enabled_for_branch(self._settings, branch)
        )
        if repair_unhealthy:
            from features.video.lib.export_track_health import (
                inspect_run_export_health,
                summarize_export_health,
                tracks_missing_mp3,
                tracks_needing_export,
            )

            health = inspect_run_export_health(
                run_dir,
                branch,
                ffmpeg_path=str(self._settings.get("ffmpegPath") or "ffmpeg"),
                mp3_paths=track_paths,
            )
            missing_audio = tracks_missing_mp3(health)
            track_paths = tracks_needing_export(health)
            if not track_paths:
                if missing_audio:
                    emit_shell_status(
                        "Cannot regenerate MP4s — download missing MP3s first "
                        f"({summarize_export_health(health)})."
                    )
                    return False
                emit_shell_status(
                    f"No missing/broken MP4s to regenerate ({summarize_export_health(health)})."
                )
                if auto_merge:
                    return self.start_manual_merge(
                        candidate,
                        settings=self._settings,
                        skip_repair=True,
                    )
                return False

        if force_selected or (force_regenerate and mp3_paths):
            for path in track_paths:
                unlink_track_export(run_dir, path, branch)

        shuffle_merge = bool(self._settings.get("videoShuffleMerge", False))
        ordered_mp4s = [
            build_pipeline_export_output_path(mp3_path=item.path, output_dir=run_dir, branch=branch)
            for item in mp3_list
        ]
        partial_export = len(track_paths) < len(available_paths)
        profile_id = str(getattr(candidate, "profile_id", None) or "").strip() or None
        ref_base = f"{candidate.batch_id}:{candidate.role}:{branch}"
        video_ref_id = f"video:{ref_base}"
        if repair_unhealthy or partial_export or force_selected:
            video_ref_id = f"video:{ref_base}:repair:{len(track_paths)}"
        try:
            video_bill = consume_video_operation(
                self._api,
                operation_type="video",
                count=len(track_paths),
                channel_profile_id=profile_id,
                ref_id=video_ref_id,
            )
            self._video_charge = {
                "operation_type": "video",
                "count": len(track_paths),
                "charged_credit_units": video_bill.charged_credit_units,
                "channel_profile_id": profile_id,
                "ref_id": video_ref_id,
            }
        except PlatformApiError as exc:
            if exc.status == 401:
                self._auth_blocked = True
                emit_shell_status("Auto-video paused: sign in to continue.", tone="warning")
                return False
            emit_shell_status(f"Auto-video blocked (billing): {exc}")
            return False
        except Exception as exc:
            emit_shell_status(f"Auto-video blocked (billing): {exc}")
            return False

        encode = resolve_merge_encode_settings(
            self._settings,
            branch=branch,
            pipeline=False,
            fps=export_fps,
            speed_mode=speed_mode,
        )
        self._merge_context = {
            "run_dir": run_dir,
            "branch": branch,
            "batch_id": candidate.batch_id,
            "role": candidate.role,
            "auto_merge": auto_merge,
            "shuffle": shuffle_merge,
            "mp4_paths": ordered_mp4s,
            "completed": len(mp3_list),
            "total": len(mp3_list),
            "profile_id": profile_id,
            "ref_base": ref_base,
            "encode_width": int(encode.width),
            "encode_height": int(encode.height),
            "encode_fps": int(encode.fps),
            "encode_speed_mode": str(encode.speed_mode),
            "settings": dict(self._settings),
            "match_export_specs": bool(auto_merge) and not partial_export and not repair_unhealthy,
        }

        branch_label = "Reel" if branch == "reel" else "Long"
        started_at_ms = int(time.time() * 1000)
        export_state = VideoExportState(
            running=True,
            branch=branch_label,
            workers=worker_limit,
            fps=export_fps,
            auto_merge=auto_merge,
            shuffle_merge=shuffle_merge,
            current_status=f"Starting {branch_label} auto-export ({tier.label})…",
            output_dir=run_dir,
            total_jobs=len(track_paths),
            completed_jobs=0,
            progress_percent=0,
            started_at_ms=started_at_ms,
        )
        self._publish_workspace(workspace.model_copy(update={"export": export_state}))
        self._busy = True

        worker = VideoPipelineExportWorker(
            PipelineExportRequest(
                run_dir=run_dir,
                background_path=background_path,
                logo_path=str(workspace.logo_path or ""),
                branch=branch,
                batch_id=candidate.batch_id,
                role=candidate.role,
                template=template,
                mp3_paths=track_paths,
                album_mp3_paths=available_paths,
                settings=self._settings,
                width=int(scene.output.width),
                height=int(scene.output.height),
                fps=int(scene.output.fps),
                speed_mode=speed_mode,
            ),
            parent=None,
        )
        worker.progressed.connect(self._on_export_progress)
        worker.succeeded.connect(self._on_export_succeeded)
        worker.failed.connect(self._on_export_failed)
        worker.finished.connect(self._on_export_finished)
        self._export_worker = worker
        track_video_pipeline_thread(worker)
        worker.start()
        if repair_unhealthy or (mp3_paths and len(track_paths) < len(available_paths)):
            emit_shell_status(
                f"Regenerating {len(track_paths)} MP4(s) for {Path(run_dir).name}."
            )
        else:
            emit_shell_status(f"Auto-video started {branch_label.lower()} export for {Path(run_dir).name}.")
        return True

    def _build_renderer_template(
        self,
        workspace: VideoWorkspaceState,
        *,
        track_paths: list[str],
    ) -> dict | None:
        if not dict(workspace.template):
            return None
        # Same domains as Manual Export from a saved template (lightning, spectrum
        # instances/glow melt, particles, logo, effects, text, …).
        return self._normalizer.from_saved_workspace(
            dict(workspace.template),
            logo_path=str(workspace.logo_path or ""),
            track_paths=track_paths,
            pipeline_album=str(
                self._settings.get("lastAlbumName") or self._settings.get("album") or ""
            ),
            active_track_path=None,
            clear_preview_background=True,
        )

    def _resolve_export_fps(self, workspace: VideoWorkspaceState) -> int:
        return normalize_export_fps(
            workspace.export.fps or self._settings.get("videoExportFps", PIPELINE_EXPORT_FPS)
        )

    def _publish_workspace(self, workspace: VideoWorkspaceState) -> None:
        get_video_workspace_service().set_workspace_state(workspace)

    def _current_workspace(self) -> VideoWorkspaceState | None:
        return get_video_workspace_service().get_workspace_state()

    def _on_export_progress(self, payload: object) -> None:
        workspace = self._current_workspace()
        if not isinstance(payload, dict) or workspace is None:
            return
        raw_message = str(payload.get("message") or payload.get("status") or "Exporting…")
        video_codec = str(payload.get("videoCodec") or workspace.export.video_codec or "").strip() or None
        updates: dict[str, object] = {
            "running": True,
            "current_status": format_export_status_message(raw_message, video_codec=video_codec),
        }
        if video_codec:
            updates["video_codec"] = video_codec
        for key, export_key in (
            ("completedJobs", "completed_jobs"),
            ("totalJobs", "total_jobs"),
            ("progressPercent", "progress_percent"),
        ):
            value = payload.get(key)
            if isinstance(value, int):
                updates[export_key] = value
        output_path = str(payload.get("outputPath") or "").strip()
        if output_path:
            updates["current_output_path"] = output_path
        self._publish_workspace(
            workspace.model_copy(update={"export": workspace.export.model_copy(update=updates)})
        )

    def _on_export_succeeded(self, payload: object) -> None:
        if is_app_quitting():
            self._busy = False
            return
        workspace = self._current_workspace()
        if not isinstance(payload, dict) or workspace is None:
            self._busy = False
            return

        message = str(payload.get("message") or "Auto-video export completed.")
        last_output = str(payload.get("lastOutputPath") or "").strip() or None
        completed = int(payload.get("completed") or workspace.export.total_jobs or 0)
        total = int(payload.get("total") or workspace.export.total_jobs or completed)
        merge_context = dict(self._merge_context)
        merge_context["completed"] = completed
        merge_context["total"] = total
        self._merge_context = merge_context

        if merge_context.get("auto_merge"):
            branch_label = "reel" if str(merge_context.get("branch") or "") == "reel" else "long"
            self._publish_workspace(
                workspace.model_copy(
                    update={
                        "export": workspace.export.model_copy(
                            update={
                                "running": True,
                                "merge_running": True,
                                "current_status": f"Merging {branch_label} video outputs…",
                                "last_output_path": last_output,
                                "progress_percent": 100,
                                "completed_jobs": completed,
                                "total_jobs": total,
                            }
                        )
                    }
                )
            )
            self._start_merge()
            return

        self._busy = False
        self._publish_workspace(
            workspace.model_copy(
                update={
                    "export": workspace.export.model_copy(
                        update={
                            "running": False,
                            "merge_running": False,
                            "current_status": message,
                            "last_output_path": last_output,
                            "progress_percent": 100,
                            "completed_jobs": completed,
                            "total_jobs": total,
                        }
                    )
                }
            )
        )
        emit_shell_status(message)
        self._schedule_progress_local_sync()

    def _schedule_progress_local_sync(self) -> None:
        if is_app_quitting():
            return
        from shared.services.progress_local_sync_coordinator import get_progress_local_sync_coordinator

        coordinator = get_progress_local_sync_coordinator()
        if coordinator is not None:
            coordinator.sync_now()

    def _start_merge(self) -> None:
        if is_app_quitting():
            self._busy = False
            return
        context = dict(self._merge_context)
        branch = str(context.get("branch") or "long").strip()
        run_dir = resolve_merge_run_dir(str(context.get("run_dir") or "").strip(), branch)
        if run_dir:
            context["run_dir"] = run_dir
            self._merge_context = context
        if not run_dir:
            self._on_merge_failed("Auto-merge skipped: run directory is missing.")
            return
        ffmpeg_path = str(self._settings.get("ffmpegPath") or "ffmpeg")
        encode = merge_encode_settings_from_context(context, pipeline=True)
        match_specs = bool(context.get("match_export_specs", context.get("auto_merge")))
        verified_paths = collect_verified_merge_inputs(
            [str(path) for path in (context.get("mp4_paths") or []) if str(path).strip()],
            run_dir=run_dir,
            branch=branch,
            ffmpeg_path=ffmpeg_path,
            expected_width=int(encode.width) if match_specs else None,
            expected_height=int(encode.height) if match_specs else None,
            expected_fps=int(encode.fps) if match_specs else None,
        )
        if len(verified_paths) < 2:
            self._on_merge_failed(
                "Merge did not produce a file — need at least two usable MP4 files in the "
                f"run folder (found {len(verified_paths)})."
            )
            return
        context["mp4_paths"] = verified_paths
        self._merge_context = context
        profile_id = str(context.get("profile_id") or "").strip() or None
        ref_base = str(context.get("ref_base") or "")
        try:
            merge_bill = consume_video_operation(
                self._api,
                operation_type="video_merge",
                count=1,
                channel_profile_id=profile_id,
                ref_id=f"video_merge:{ref_base}",
            )
            self._merge_charge = {
                "operation_type": "video_merge",
                "count": 1,
                "charged_credit_units": merge_bill.charged_credit_units,
                "channel_profile_id": profile_id,
                "ref_id": f"video_merge:{ref_base}",
            }
        except PlatformApiError as exc:
            if exc.status == 401:
                self._auth_blocked = True
                message = "Export complete; auto-merge paused: sign in to continue."
            else:
                message = f"Export complete; auto-merge blocked (billing): {exc}"
            self._busy = False
            workspace = self._current_workspace()
            if workspace is not None:
                self._publish_workspace(
                    workspace.model_copy(
                        update={
                            "export": workspace.export.model_copy(
                                update={
                                    "running": False,
                                    "merge_running": False,
                                    "current_status": message,
                                }
                            )
                        }
                    )
                )
            emit_shell_status(message, tone="warning" if exc.status == 401 else "neutral")
            return
        except Exception as exc:
            self._busy = False
            workspace = self._current_workspace()
            message = f"Export complete; auto-merge blocked (billing): {exc}"
            if workspace is not None:
                self._publish_workspace(
                    workspace.model_copy(
                        update={
                            "export": workspace.export.model_copy(
                                update={
                                    "running": False,
                                    "merge_running": False,
                                    "current_status": message,
                                }
                            )
                        }
                    )
                )
            emit_shell_status(message)
            return
        encode = merge_encode_settings_from_context(context, pipeline=True)
        worker = VideoPipelineMergeWorker(
            PipelineMergeRequest(
                run_dir=run_dir,
                branch=branch,
                batch_id=str(context.get("batch_id") or ""),
                role=str(context.get("role") or ""),
                ffmpeg_path=ffmpeg_path,
                completed=int(context.get("completed") or 0),
                total=int(context.get("total") or 0),
                mp4_paths=tuple(verified_paths),
                shuffle=bool(context.get("shuffle", True)),
                encode=encode,
                match_export_specs=match_specs,
            ),
            parent=None,
        )
        worker.progressed.connect(self._on_merge_progress)
        worker.succeeded.connect(self._on_merge_succeeded)
        worker.failed.connect(self._on_merge_failed)
        worker.finished.connect(self._on_merge_finished)
        self._merge_worker = worker
        track_video_pipeline_thread(worker)
        worker.start()

    def _refund_video_charge(self, reason: str, *, count: int | None = None) -> None:
        charge = dict(self._video_charge or {})
        if not charge:
            return
        original_count = max(1, int(charge.get("count") or 1))
        refund_count = original_count if count is None else max(0, min(original_count, int(count)))
        if refund_count <= 0:
            self._video_charge = {}
            return
        charged = int(charge.get("charged_credit_units") or 0)
        refund_credits = int(round(charged * refund_count / original_count)) if charged else 0
        try:
            refund_video_operation(
                self._api,
                operation_type=str(charge.get("operation_type") or "video"),
                charged_credit_units=refund_credits,
                count=refund_count,
                channel_profile_id=charge.get("channel_profile_id"),
                ref_id=str(charge.get("ref_id") or "") or None,
                reason=reason,
            )
        except Exception:
            pass
        self._video_charge = {}

    def _refund_merge_charge(self, reason: str) -> None:
        charge = dict(self._merge_charge or {})
        if not charge:
            return
        try:
            refund_video_operation(
                self._api,
                operation_type=str(charge.get("operation_type") or "video_merge"),
                charged_credit_units=int(charge.get("charged_credit_units") or 0),
                count=int(charge.get("count") or 1),
                channel_profile_id=charge.get("channel_profile_id"),
                ref_id=str(charge.get("ref_id") or "") or None,
                reason=reason,
            )
        except Exception:
            pass
        self._merge_charge = {}

    @staticmethod
    def _is_user_initiated_stop(message: str) -> bool:
        text = str(message or "").strip().lower()
        return "export stopped" in text

    def _apply_video_refund_for_outcome(self, message: str, *, user_stop: bool) -> None:
        charge = dict(self._video_charge or {})
        if not charge:
            return
        workspace = self._current_workspace()
        completed = int(workspace.export.completed_jobs or 0) if workspace is not None else 0
        charged = max(1, int(charge.get("count") or 1))
        keep = completed + (1 if user_stop else 0)
        refund_count = max(0, charged - keep)
        if refund_count <= 0:
            self._video_charge = {}
            return
        self._refund_video_charge(
            (
                "Auto-video export stopped (unused tracks)."
                if user_stop
                else (message or "Auto-video export failed.")
            ),
            count=refund_count,
        )

    def _on_merge_progress(self, payload: object) -> None:
        workspace = self._current_workspace()
        if not isinstance(payload, dict) or workspace is None:
            return
        message = str(payload.get("message") or "Merging video outputs…")
        merge_percent = payload.get("progress")
        try:
            merge_progress = max(0, min(100, int(merge_percent))) if merge_percent is not None else None
        except (TypeError, ValueError):
            merge_progress = None
        update: dict[str, object] = {
            "running": True,
            "merge_running": True,
            "current_status": message,
        }
        if merge_progress is not None:
            update["merge_progress_percent"] = merge_progress
        self._publish_workspace(
            workspace.model_copy(
                update={"export": workspace.export.model_copy(update=update)}
            )
        )

    def _on_merge_succeeded(self, payload: object) -> None:
        if not isinstance(payload, dict):
            self._on_merge_failed("Video merge failed.")
            return
        merged_output = str(payload.get("mergedOutputPath") or "").strip() or None
        if not merged_output or not merged_output_ready(merged_output):
            self._on_merge_failed(
                str(payload.get("message") or "").strip()
                or "Merge did not produce a file."
            )
            return
        workspace = self._current_workspace()
        self._busy = False
        self._video_charge = {}
        self._merge_charge = {}
        message = str(payload.get("message") or "Auto-merge completed.")
        if workspace is not None:
            self._publish_workspace(
                workspace.model_copy(
                    update={
                        "export": workspace.export.model_copy(
                            update={
                                "running": False,
                                "merge_running": False,
                                "merge_progress_percent": None,
                                "current_status": message,
                                "last_merged_output_path": merged_output,
                                "progress_percent": 100,
                            }
                        )
                    }
                )
            )
        emit_shell_status(message)
        context = dict(self._merge_context or {})
        from shared.lib.pipeline_completion import mark_desktop_pipeline_complete

        mark_desktop_pipeline_complete(
            self._api,
            batch_id=str(context.get("batch_id") or ""),
            profile_id=str(context.get("profile_id") or ""),
            role=str(context.get("role") or "OK"),
            run_dir=str(context.get("run_dir") or ""),
        )
        self._schedule_progress_local_sync()

    def _on_merge_failed(self, message: str) -> None:
        if self._is_user_initiated_stop(message):
            self._merge_charge = {}
        else:
            self._refund_merge_charge(message or "Auto-merge failed.")
        workspace = self._current_workspace()
        self._busy = False
        if workspace is not None:
            self._publish_workspace(
                workspace.model_copy(
                    update={
                        "export": workspace.export.model_copy(
                            update={
                                "running": False,
                                "merge_running": False,
                                "merge_progress_percent": None,
                                "current_status": message or "Auto-merge failed.",
                            }
                        )
                    }
                )
            )
        emit_shell_status(message or "Auto-merge failed.")

    def _on_export_failed(self, message: str) -> None:
        from shared.services.app_logger import log_error

        user_stop = self._is_user_initiated_stop(message)
        self._apply_video_refund_for_outcome(message or "", user_stop=user_stop)
        workspace = self._current_workspace()
        self._busy = False
        status_text = message or "Auto-video export failed."
        # Persist full crash tail (multiline) into diagnostics sync / local log file.
        if not user_stop:
            log_error(status_text, category="export")
        if workspace is not None:
            # Progress row: keep first line short; detail is in diagnostics logs.
            status_line = status_text.splitlines()[0].strip() or status_text
            self._publish_workspace(
                workspace.model_copy(
                    update={
                        "export": workspace.export.model_copy(
                            update={
                                "running": False,
                                "merge_running": False,
                                "current_status": status_line,
                            }
                        )
                    }
                )
            )
        emit_shell_status(status_text.splitlines()[0].strip() or status_text)

    def _on_export_finished(self) -> None:
        self._export_worker = None

    def _on_merge_finished(self) -> None:
        self._merge_worker = None

    @staticmethod
    def _clear_branch_exports(run_dir: str, batch_id: str, role: str, branch: str) -> None:
        normalized_branch = "reel" if str(branch or "").strip().lower() == "reel" else "long"
        for path in list_branch_export_outputs(run_dir, normalized_branch):
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
        merged_path = build_merged_output_path(
            output_dir=run_dir,
            batch_id=batch_id,
            role=role,
            branch=normalized_branch,
        )
        try:
            Path(merged_path).unlink(missing_ok=True)
        except OSError:
            pass

    def start_manual_merge(
        self,
        candidate: AutoVideoCandidate,
        *,
        settings: dict[str, Any],
        skip_repair: bool = False,
    ) -> bool:
        if is_app_quitting():
            return False
        if self.is_busy():
            emit_shell_status("Video pipeline is already running.", tone="warning")
            return False
        self._auth_blocked = False
        self._settings = dict(settings or {})
        branch = "reel" if candidate.branch == "reel" else "long"
        run_dir = resolve_merge_run_dir(str(candidate.run_dir or "").strip(), branch)
        if not run_dir or not Path(run_dir).is_dir():
            emit_shell_status("Merge skipped: run directory is missing.")
            return False

        from features.video.lib.export_track_health import (
            decide_merge_prep,
            inspect_run_export_health,
            summarize_export_health,
            tracks_needing_export,
        )

        health = inspect_run_export_health(
            run_dir,
            branch,
            ffmpeg_path=str(self._settings.get("ffmpegPath") or "ffmpeg"),
        )
        prep = decide_merge_prep(health, skip_repair=skip_repair)
        if prep == "repair":
            repair_paths = tracks_needing_export(health)
            emit_shell_status(
                f"Regenerating {len(repair_paths)} missing/broken MP4(s), then merging "
                f"({summarize_export_health(health)})."
            )
            return self.start(
                candidate,
                settings=self._settings,
                mp3_paths=repair_paths,
                repair_unhealthy=True,
                auto_merge=True,
            )
        if prep == "missing_audio":
            emit_shell_status(
                "Cannot merge — download missing MP3s first "
                f"({summarize_export_health(health)})."
            )
            return False

        mp4_paths = list_branch_export_outputs(run_dir, branch)
        if not mp4_paths:
            emit_shell_status("Merge skipped: no exported MP4 files were found in the run folder.")
            return False
        profile_id = str(getattr(candidate, "profile_id", None) or "").strip() or None
        ref_base = f"{candidate.batch_id}:{candidate.role}:{branch}"
        encode = resolve_merge_encode_settings(self._settings, branch=branch, pipeline=True)
        self._merge_context = {
            "run_dir": run_dir,
            "branch": branch,
            "batch_id": candidate.batch_id,
            "role": candidate.role,
            "auto_merge": False,
            "shuffle": bool(self._settings.get("videoShuffleMerge", False)),
            "mp4_paths": mp4_paths,
            "completed": len(mp4_paths),
            "total": len(mp4_paths),
            "profile_id": profile_id,
            "ref_base": ref_base,
            "encode_width": int(encode.width),
            "encode_height": int(encode.height),
            "encode_fps": int(encode.fps),
            "encode_speed_mode": str(encode.speed_mode),
            "settings": dict(self._settings),
            "match_export_specs": False,
        }
        workspace = self._store.read_workspace_state(self._settings)
        branch_label = "Reel" if branch == "reel" else "Long"
        self._publish_workspace(
            workspace.model_copy(
                update={
                    "export": workspace.export.model_copy(
                        update={
                            "running": True,
                            "merge_running": True,
                            "branch": branch_label,
                            "current_status": f"Starting {branch_label.lower()} merge…",
                            "output_dir": run_dir,
                        }
                    )
                }
            )
        )
        self._busy = True
        self._start_merge()
        emit_shell_status(f"Started {branch_label.lower()} merge for {Path(run_dir).name}.")
        return True
