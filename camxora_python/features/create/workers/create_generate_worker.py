"""Background worker: web lyric draft (Advanced) + web Create generate + local automation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from shared.services.app_logger import log_error
from shared.lib.create_automation import (
    export_version_videos,
    generate_day_images,
    merge_version_folder,
)
from shared.lib.create_generate import (
    VERSION_1,
    VERSION_2,
    CreateGeneratePlan,
    clip_folder_assignment,
    draft_prompt,
    generation_failed,
    generation_is_open,
    generation_succeeded,
    safe_audio_filename,
    version_folders,
    web_generate_body,
)
from shared.lib.create_history import (
    HISTORY_MAX_ITEMS,
    HISTORY_PAGE_SIZE,
    history_file_stem,
    is_encrypted_audio_bytes,
)
from shared.models.web_music import WebMusicGenerateRequest, WebMusicGenerationResponse
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError

_POLL_SECONDS = 4.0
_POLL_TIMEOUT_SECONDS = 12 * 60
_SUBMIT_RETRIES = 6
_DOWNLOAD_RETRIES = 8
_TRANSIENT_STATUSES = {429, 502, 503}


@dataclass(frozen=True, slots=True)
class CreateGenerateResult:
    saved: int
    failed: int
    last_title: str = ""
    last_lyrics: str = ""


class CreateGenerateWorker(QThread):
    progressed = Signal(str)
    song_started = Signal(int, str)
    song_submitted = Signal(int, str, str)
    song_saved = Signal(int, str, str)
    song_failed = Signal(int)
    files_changed = Signal()
    draft_ready = Signal(str, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        plan: CreateGeneratePlan,
        parent=None,
        *,
        only_index: int | None = None,
        existing_task_id: str | None = None,
        retry_title: str = "",
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._plan = plan
        self._only_index = only_index
        self._existing_task_id = (existing_task_id or "").strip()
        self._retry_title = retry_title

    def run(self) -> None:
        plan = self._plan
        try:
            version_1, version_2 = version_folders(plan.save_folder)
            version_1.mkdir(parents=True, exist_ok=True)
            version_2.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.failed.emit(f"Could not create Version folders: {exc}")
            return

        saved = 0
        failed = 0
        last_title = plan.title
        last_lyrics = plan.lyrics
        songs_per_day = max(1, int(plan.songs_per_day or plan.song_count))
        planned_days = max(1, int(plan.planned_days or 1))

        indexes = (
            [self._only_index]
            if self._only_index
            else list(range(1, plan.song_count + 1))
        )
        if self._existing_task_id and self._only_index:
            self._finish_existing_task(
                index=self._only_index,
                task_id=self._existing_task_id,
                title=self._retry_title or plan.title,
                song_count=plan.song_count,
            )
            return

        # Full runs only: fail fast when Auto Video/Merge credits are short
        # instead of generating everything and stalling at the export stage.
        if self._only_index is None and not self._existing_task_id:
            gate_error = self._preflight_video_merge(plan)
            if gate_error:
                self.failed.emit(gate_error)
                return

        for index in indexes:
            if self.isInterruptionRequested():
                self.failed.emit("Generate cancelled.")
                return
            day_index = ((index - 1) // songs_per_day) + 1
            self.progressed.emit(f"Generating song {index} of {plan.song_count}…")
            try:
                title = plan.title
                lyrics = plan.lyrics
                if plan.mode == "advanced":
                    title, lyrics = self._draft_song(plan)
                    self.draft_ready.emit(title, lyrics)
                    last_title = title
                    last_lyrics = lyrics
                self.song_started.emit(index, title or f"Song {index}")
                body = web_generate_body(plan, title=title, lyrics=lyrics)
                self.progressed.emit(f"Sending song {index} of {plan.song_count} to Suno…")
                generation, path_v1, path_v2 = self._run_one_song(
                    body,
                    index=index,
                    song_count=plan.song_count,
                    title=title or f"Song {index}",
                )
            except PlatformApiError as exc:
                self.song_failed.emit(index)
                self.failed.emit(str(exc) or "Generate failed.")
                return
            except Exception as exc:
                self.song_failed.emit(index)
                self.failed.emit(str(exc) or "Generate failed.")
                return
            last_title = generation.title or last_title
            last_lyrics = generation.lyrics or last_lyrics
            saved += 1
            self.song_saved.emit(index, path_v1, path_v2)

            end_of_day = index % songs_per_day == 0 or index == plan.song_count
            if end_of_day and plan.auto_image:
                try:
                    generate_day_images(
                        self._api,
                        plan,
                        day_index=min(day_index, planned_days),
                        on_progress=self.progressed.emit,
                    )
                    self.files_changed.emit()
                except Exception as exc:
                    self.failed.emit(str(exc) or "Auto Image failed.")
                    return

        if plan.auto_video:
            try:
                self._run_auto_video(plan)
                self.files_changed.emit()
            except Exception as exc:
                self.failed.emit(str(exc) or "Auto Video failed.")
                return

        if plan.auto_merge:
            try:
                self._run_auto_merge(plan)
                self.files_changed.emit()
            except Exception as exc:
                self.failed.emit(str(exc) or "Merge all video failed.")
                return

        self.succeeded.emit(
            CreateGenerateResult(
                saved=saved,
                failed=failed,
                last_title=last_title,
                last_lyrics=last_lyrics,
            )
        )

    def _draft_song(self, plan: CreateGeneratePlan) -> tuple[str, str]:
        self.progressed.emit("Drafting title and lyrics…")
        draft = self._api.generate_web_music_draft(draft_prompt(plan))
        title = (draft.title or plan.title or "Untitled").strip()
        lyrics = (draft.lyrics or "").strip()
        if not lyrics:
            raise RuntimeError("Draft returned empty lyrics.")
        return title, lyrics

    def _run_one_song(
        self,
        body: dict[str, object],
        *,
        index: int,
        song_count: int,
        title: str,
    ) -> tuple[WebMusicGenerationResponse, str, str]:
        created = self._submit(body)
        self.song_submitted.emit(index, created.task_id, title)
        return self._finish_task(
            task_id=created.task_id, index=index, song_count=song_count
        )

    def _finish_existing_task(
        self,
        *,
        index: int,
        task_id: str,
        title: str,
        song_count: int,
    ) -> None:
        try:
            self.song_submitted.emit(index, task_id, title)
            self.progressed.emit(f"Retrying download for {title or f'song {index}'}…")
            generation, path_v1, path_v2 = self._finish_task(
                task_id=task_id, index=index, song_count=song_count
            )
        except PlatformApiError as exc:
            self.song_failed.emit(index)
            self.failed.emit(str(exc) or "Retry download failed.")
            return
        except Exception as exc:
            self.song_failed.emit(index)
            self.failed.emit(str(exc) or "Retry download failed.")
            return
        self.song_saved.emit(index, path_v1, path_v2)
        self.succeeded.emit(
            CreateGenerateResult(saved=1, failed=0, last_title=generation.title or title)
        )

    def _finish_task(
        self,
        *,
        task_id: str,
        index: int,
        song_count: int,
    ) -> tuple[WebMusicGenerationResponse, str, str]:
        generation = self._poll(task_id)
        path_v1, path_v2 = self._download_clips(
            generation, index=index, song_count=song_count
        )
        return generation, path_v1, path_v2

    def _submit(self, body: dict[str, object]):
        payload = WebMusicGenerateRequest.model_validate(body)
        last_error = "Generate failed."
        for attempt in range(_SUBMIT_RETRIES):
            if self.isInterruptionRequested():
                raise RuntimeError("Generate cancelled.")
            try:
                return self._api.generate_web_music(payload)
            except PlatformApiError as exc:
                last_error = str(exc) or last_error
                if exc.status in _TRANSIENT_STATUSES and attempt + 1 < _SUBMIT_RETRIES:
                    time.sleep(_POLL_SECONDS * (attempt + 1))
                    continue
                raise
        raise PlatformApiError(0, last_error)

    def _poll(self, task_id: str) -> WebMusicGenerationResponse:
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        last: WebMusicGenerationResponse | None = None
        while time.monotonic() < deadline:
            if self.isInterruptionRequested():
                raise RuntimeError("Generate cancelled.")
            try:
                last = self._api.get_web_music_generation(task_id)
            except PlatformApiError as exc:
                if exc.status in _TRANSIENT_STATUSES:
                    self.progressed.emit(
                        f"Waiting for Suno (API {exc.status}, retrying)…"
                    )
                    time.sleep(_POLL_SECONDS)
                    continue
                raise
            status = last.status
            if generation_failed(status):
                raise RuntimeError(last.error_message or "Suno generation failed.")
            if generation_succeeded(status) and _clips_ready(last):
                return last
            if generation_succeeded(status) or generation_is_open(status):
                self.progressed.emit(f"Waiting for Suno ({status.lower() or 'queued'})…")
                time.sleep(_POLL_SECONDS)
                continue
            time.sleep(_POLL_SECONDS)
        raise RuntimeError("Timed out waiting for Suno to finish.")

    def _download_clips(
        self,
        generation: WebMusicGenerationResponse,
        *,
        index: int,
        song_count: int,
    ) -> tuple[str, str]:
        ok_folder, alt_folder = clip_folder_assignment(self._plan.version_mode)
        mapping = (("ok", ok_folder), ("alt", alt_folder))
        root = Path(self._plan.save_folder)
        dests: dict[str, str] = {}
        for variant, folder_name in mapping:
            dest_dir = root / folder_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            clip_title = _clip_title(generation, variant)
            filename = safe_audio_filename(
                clip_title,
                index=index,
                song_count=song_count,
                task_id=generation.id,
            )
            dest = dest_dir / filename
            self.progressed.emit(f"Saving {folder_name}/{filename}…")
            data = self._download_variant(generation.id, variant)
            dest.write_bytes(data)
            dests[folder_name] = str(dest)
        self._download_sidecars(generation.id, dests)
        return dests.get(VERSION_1, ""), dests.get(VERSION_2, "")

    def _download_sidecars(self, task_id: str, dests: dict[str, str]) -> None:
        plan = self._plan
        if not (plan.download_wav or plan.download_lrc or plan.download_srt):
            return
        ok_folder, alt_folder = clip_folder_assignment(plan.version_mode)
        variant_by_folder = {ok_folder: "ok", alt_folder: "alt"}
        for folder_name, mp3_path in dests.items():
            variant = variant_by_folder.get(folder_name, "ok")
            stem = Path(mp3_path).with_suffix("")
            if plan.download_wav:
                self._write_sidecar(
                    stem.with_suffix(".wav"),
                    label="WAV",
                    fetch=lambda v=variant: self._api.download_web_music_wav(task_id, v),
                )
            if plan.download_lrc:
                self._write_sidecar(
                    stem.with_suffix(".lrc"),
                    label="LRC",
                    fetch=lambda v=variant: self._api.download_web_music_lyrics(
                        task_id, v, fmt="lrc"
                    ),
                )
            if plan.download_srt:
                self._write_sidecar(
                    stem.with_suffix(".srt"),
                    label="SRT",
                    fetch=lambda v=variant: self._api.download_web_music_lyrics(
                        task_id, v, fmt="srt"
                    ),
                )

    def _write_sidecar(self, dest: Path, *, label: str, fetch) -> None:
        self.progressed.emit(f"Saving {dest.name}…")
        last_error = f"{label} is not available yet."
        for attempt in range(_DOWNLOAD_RETRIES):
            if self.isInterruptionRequested():
                raise RuntimeError("Generate cancelled.")
            try:
                data = fetch()
            except PlatformApiError as exc:
                last_error = str(exc) or last_error
                if exc.status in {404, 409, 429, 502, 503} and attempt + 1 < _DOWNLOAD_RETRIES:
                    time.sleep(_POLL_SECONDS)
                    continue
                self.progressed.emit(f"{label} skipped: {last_error}")
                return
            if data:
                dest.write_bytes(data)
                return
            time.sleep(_POLL_SECONDS)
        self.progressed.emit(f"{label} skipped: {last_error}")

    def _download_variant(self, task_id: str, variant: str) -> bytes:
        last_error = "Audio file is not available yet."
        for attempt in range(_DOWNLOAD_RETRIES):
            if self.isInterruptionRequested():
                raise RuntimeError("Generate cancelled.")
            try:
                data = self._api.download_web_music_clip(task_id, variant)
            except PlatformApiError as exc:
                last_error = str(exc) or last_error
                if exc.status in {404, 409, 429} and attempt + 1 < _DOWNLOAD_RETRIES:
                    time.sleep(_POLL_SECONDS)
                    continue
                raise
            if data:
                return data
            time.sleep(_POLL_SECONDS)
        raise RuntimeError(last_error)

    def _charge_local(self, operation_type: str, count: int, ref_id: str) -> dict:
        from features.video.lib.video_billing import consume_video_operation

        result = consume_video_operation(
            self._api,
            operation_type=operation_type,
            count=count,
            ref_id=ref_id,
        )
        return {
            "operation_type": result.operation_type,
            "count": max(1, int(count)),
            "charged_credit_units": int(result.charged_credit_units),
            "ref_id": ref_id,
        }

    def _refund_local(
        self, charge: dict | None, *, count: int | None = None, reason: str = ""
    ) -> None:
        if not charge:
            return
        from features.video.lib.video_billing import refund_video_operation

        original = max(1, int(charge.get("count") or 1))
        refund_count = original if count is None else max(0, min(original, int(count)))
        if refund_count <= 0:
            return
        charged = int(charge.get("charged_credit_units") or 0)
        refund_credits = int(round(charged * refund_count / original)) if charged else 0
        try:
            refund_video_operation(
                self._api,
                operation_type=str(charge.get("operation_type") or "video"),
                charged_credit_units=refund_credits,
                count=refund_count,
                ref_id=str(charge.get("ref_id") or "") or None,
                reason=reason or "Create automation failed",
            )
        except Exception as exc:  # noqa: BLE001
            log_error("create.video_refund_failed", category="create", exc=exc)

    def _preflight_video_merge(self, plan: CreateGeneratePlan) -> str | None:
        """Best-effort upfront gate for Auto Video/Merge (quota first, then wallet)."""
        from shared.lib.create_generate import estimate_video_merge_ops
        from shared.lib.music_costs import get_operation_unit_cost, map_operation_costs

        video_ops, merge_ops = estimate_video_merge_ops(plan)
        if video_ops <= 0 and merge_ops <= 0:
            return None
        try:
            quota = self._api.get_quota_status()
        except Exception as exc:
            return f"Cannot check credits for Auto Video/Merge: {exc}"
        try:
            costs = map_operation_costs(self._api.get_operation_costs().items)
        except Exception:
            costs = {}
        video_unit = get_operation_unit_cost(costs.get("video")) or 0.0
        merge_unit = get_operation_unit_cost(costs.get("video_merge")) or 0.0
        wallet_needed = video_ops * video_unit + merge_ops * merge_unit

        video_quota_ok = quota.videos_remaining is None or quota.videos_remaining >= video_ops
        merge_quota_ok = (
            merge_ops == 0 or quota.merges_remaining is None or quota.merges_remaining >= merge_ops
        )
        video_daily_ok = (
            quota.daily_videos_remaining is None or quota.daily_videos_remaining >= video_ops
        )
        merge_daily_ok = (
            merge_ops == 0
            or quota.daily_merges_remaining is None
            or quota.daily_merges_remaining >= merge_ops
        )
        if video_quota_ok and merge_quota_ok and video_daily_ok and merge_daily_ok:
            return None
        wallet = float(quota.wallet_balance or 0)
        if wallet >= wallet_needed:
            return None
        return (
            "Not enough credits for Auto Video/Merge. This run needs about "
            f"{wallet_needed:.4g} credits ({video_ops} video export"
            f"{'s' if video_ops != 1 else ''}, {merge_ops} merge"
            f"{'s' if merge_ops != 1 else ''}). Available {wallet:.4g}."
        )

    def _run_auto_video(self, plan: CreateGeneratePlan) -> None:
        from shared.lib.create_automation import (
            find_background_image,
            list_version_mp3s,
            template_payload,
        )

        root = Path(plan.save_folder)
        pairs = (
            (root / VERSION_1, plan.template_v1_id, "v1"),
            (root / VERSION_2, plan.template_v2_id, "v2"),
        )
        for folder, template_id, tag in pairs:
            if self.isInterruptionRequested():
                raise RuntimeError("Generate cancelled.")
            if not str(template_id or "").strip():
                self.progressed.emit(f"Skip Auto Video for {folder.name}: None selected.")
                continue
            if template_payload(template_id) is None or find_background_image(folder) is None:
                self.progressed.emit(f"Skip Auto Video for {folder.name}: assets not ready.")
                continue
            mp3s = list_version_mp3s(folder)
            if not mp3s:
                self.progressed.emit(f"Skip Auto Video for {folder.name}: no MP3 files.")
                continue
            ref_id = f"create-video:{tag}:{folder.name}"
            charge: dict | None = None
            try:
                charge = self._charge_local("video", len(mp3s), ref_id)
                written = export_version_videos(
                    folder,
                    template_id=template_id,
                    on_progress=self.progressed.emit,
                    should_stop=self.isInterruptionRequested,
                )
                unused = max(0, len(mp3s) - len(written or ()))
                if unused:
                    self._refund_local(
                        charge, count=unused, reason="Create auto video: unused exports"
                    )
                self.files_changed.emit()
            except Exception as exc:
                self._refund_local(charge, reason=f"Create auto video failed: {exc}")
                raise

    def _run_auto_merge(self, plan: CreateGeneratePlan) -> None:
        from shared.lib.create_automation import list_mergeable_mp4s

        root = Path(plan.save_folder)
        for folder, role, tag in (
            (root / VERSION_1, "ok", "v1"),
            (root / VERSION_2, "alt", "v2"),
        ):
            if self.isInterruptionRequested():
                raise RuntimeError("Generate cancelled.")
            if len(list_mergeable_mp4s(folder)) < 2:
                self.progressed.emit(f"Skip merge in {folder.name}: need at least two videos.")
                continue
            ref_id = f"create-merge:{tag}:{folder.name}"
            charge: dict | None = None
            try:
                charge = self._charge_local("video_merge", 1, ref_id)
                merge_version_folder(folder, role=role, on_progress=self.progressed.emit)
                self.files_changed.emit()
            except Exception as exc:
                self._refund_local(charge, reason=f"Create merge failed: {exc}")
                raise


class CreateClipDownloadWorker(QThread):
    """Download one clip/sidecar from an existing task. Never POSTs generate."""

    progressed = Signal(str)
    file_saved = Signal(str, str, str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        save_folder: str,
        task_id: str,
        title: str,
        kind: str,
        variant: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CreateClipDownloadWorker")
        self._api = api
        self._save_folder = save_folder
        self._task_id = task_id
        self._title = title
        self._kind = (kind or "mp3").strip().lower()
        self._variant = "alt" if (variant or "").strip().lower() == "alt" else "ok"

    def run(self) -> None:
        try:
            which = "v2" if self._variant == "alt" else "v1"
            folder_name = VERSION_2 if which == "v2" else VERSION_1
            dest_dir = Path(self._save_folder) / folder_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            stem = history_file_stem(self._title, self._task_id)
            ext = {"mp3": ".mp3", "wav": ".wav", "lrc": ".lrc", "srt": ".srt"}.get(
                self._kind, ".mp3"
            )
            dest = dest_dir / f"{stem}{ext}"
            self.progressed.emit(f"Downloading {folder_name}/{dest.name}…")
            data = self._fetch()
            if self._kind == "mp3" and is_encrypted_audio_bytes(data):
                raise RuntimeError("Download is still encrypted. Try Download MP3 again.")
            dest.write_bytes(data)
            self.file_saved.emit(self._task_id, which, str(dest) if ext == ".mp3" else "")
            self.succeeded.emit(str(dest))
        except PlatformApiError as exc:
            self.failed.emit(str(exc) or "Download failed.")
        except Exception as exc:
            self.failed.emit(str(exc) or "Download failed.")

    def _fetch(self) -> bytes:
        if self._kind == "wav":
            return self._api.download_web_music_wav(self._task_id, self._variant)
        if self._kind == "lrc":
            return self._api.download_web_music_lyrics(self._task_id, self._variant, fmt="lrc")
        if self._kind == "srt":
            return self._api.download_web_music_lyrics(self._task_id, self._variant, fmt="srt")
        return self._api.download_web_music_clip(self._task_id, self._variant)


class CreateHistoryWorker(QThread):
    """Load Create songs from GET /web-music/generations (database)."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CreateHistoryWorker")
        self._api = api

    def run(self) -> None:
        try:
            items: list[WebMusicGenerationResponse] = []
            offset = 0
            total = 0
            while len(items) < HISTORY_MAX_ITEMS:
                page = self._api.list_web_music_generations(
                    limit=HISTORY_PAGE_SIZE,
                    offset=offset,
                )
                total = int(page.total or 0)
                if not page.items:
                    break
                items.extend(page.items)
                if len(items) >= total:
                    break
                offset += len(page.items)
            self.succeeded.emit(items[:HISTORY_MAX_ITEMS])
        except PlatformApiError as exc:
            self.failed.emit(str(exc) or "Failed to load Create history.")
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load Create history.")


def _clips_ready(generation: WebMusicGenerationResponse) -> bool:
    if not generation.clips:
        return False
    needed = {"ok", "alt"}
    ready = {clip.variant for clip in generation.clips if clip.ready}
    return needed.issubset(ready)


def _clip_title(generation: WebMusicGenerationResponse, variant: str) -> str:
    for clip in generation.clips:
        if clip.variant == variant and clip.title.strip():
            return clip.title.strip()
    return generation.title.strip() or "Untitled"
