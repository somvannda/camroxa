"""Background pipeline failure recovery — shell-level helper agent."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, QTimer

from shared.lib.qt_signals import disconnect_quietly
from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.services.shell_status import emit_shell_status
from shared.workers.data_workers import PipelineRecoveryScanResult, PipelineRecoveryScanWorker

_IDLE_POLL_MS = 45_000
_ACTIVE_POLL_MS = 20_000
_SONG_COOLDOWN_SEC = 15 * 60
_MAX_TARGETS_PER_CYCLE = 3
_MAX_SESSION_ATTEMPTS_PER_SONG = 2
_BUSY_DEFAULT_SEC = 180.0
_SAME_HASH_SUNO_RETRY_LIMIT = 1

_bound_coordinator: PipelineRecoveryCoordinator | None = None


def bind_pipeline_recovery_coordinator(coordinator: PipelineRecoveryCoordinator | None) -> None:
    global _bound_coordinator
    _bound_coordinator = coordinator


def mark_pipeline_song_busy(song_id: str | None, *, seconds: float = _BUSY_DEFAULT_SEC) -> None:
    if _bound_coordinator is not None:
        _bound_coordinator.mark_song_busy(song_id, seconds=seconds)


def clear_pipeline_song_busy(song_id: str | None) -> None:
    if _bound_coordinator is not None:
        _bound_coordinator.clear_song_busy(song_id)


@dataclass
class _SongAttemptState:
    attempts: int = 0
    last_attempt_at: float = 0.0
    last_kind: str = ""
    last_lyrics_hash: str = ""
    suno_retry_same_hash: int = 0


class PipelineRecoveryCoordinator(QObject):
    """Poll music history and auto-recover failed draft/Suno songs.

    Complements server-side Suno reject rewrite. This client helper also
    catches draft failures and stuck Suno rows that never got a callback.
    """

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: PipelineRecoveryScanWorker | None = None
        self._active = False
        self._song_state: dict[str, _SongAttemptState] = {}
        self._busy_until: dict[str, float] = {}
        self._enabled = True
        self._auth_notice_shown = False

    def start(self) -> None:
        self._active = True
        bind_pipeline_recovery_coordinator(self)
        self._timer.start(_IDLE_POLL_MS)
        # Delay first scan so login/bootstrap isn't competing for API.
        QTimer.singleShot(20_000, self._poll)

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        if _bound_coordinator is self:
            bind_pipeline_recovery_coordinator(None)
        worker = self._worker
        if worker is not None:
            disconnect_quietly(worker.succeeded, self._on_succeeded)
            disconnect_quietly(worker.failed, self._on_failed)
            disconnect_quietly(worker.finished, self._on_worker_finished)
            if worker.isRunning():
                worker.wait(1_500)
            self._worker = None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def mark_song_busy(self, song_id: str | None, *, seconds: float = _BUSY_DEFAULT_SEC) -> None:
        sid = str(song_id or "").strip()
        if not sid:
            return
        self._busy_until[sid] = time.time() + max(30.0, float(seconds))

    def clear_song_busy(self, song_id: str | None) -> None:
        sid = str(song_id or "").strip()
        if sid:
            self._busy_until.pop(sid, None)

    def _is_busy(self, song_id: str, *, now: float) -> bool:
        until = self._busy_until.get(song_id)
        if until is None:
            return False
        if until <= now:
            self._busy_until.pop(song_id, None)
            return False
        return True

    def _maybe_escalate(self, target: object) -> object | None:
        """Escalate/skip when plain Suno retry already tried the same lyrics."""
        from features.music.lib.pipeline_recovery import RecoveryTarget

        kind = str(getattr(target, "kind", "") or "")
        if kind == "skip":
            return target
        song_id = str(getattr(target, "song_id", "") or "").strip()
        lyrics_hash = str(getattr(target, "lyrics_hash", "") or "").strip()
        state = self._song_state.get(song_id)
        if state is None or not lyrics_hash:
            return target

        same_hash = bool(state.last_lyrics_hash and state.last_lyrics_hash == lyrics_hash)
        if (
            kind == "suno_retry"
            and same_hash
            and state.last_kind == "suno_retry"
            and state.suno_retry_same_hash >= _SAME_HASH_SUNO_RETRY_LIMIT
        ):
            try:
                return replace(target, kind="suno_rewrite", reason="escalate_after_same_hash_retry")  # type: ignore[arg-type]
            except TypeError:
                return target

        if kind == "suno_rewrite" and same_hash and state.last_kind == "suno_rewrite":
            return RecoveryTarget(
                batch_id=str(getattr(target, "batch_id", "") or ""),
                song_id=song_id,
                kind="skip",
                reason="same_lyrics_after_rewrite",
                lyrics_hash=lyrics_hash,
                channel_profile_id=getattr(target, "channel_profile_id", None),
                title=getattr(target, "title", None),
                album=getattr(target, "album", None),
                lyrics=getattr(target, "lyrics", None),
                mood_id=getattr(target, "mood_id", None),
                structure_id=getattr(target, "structure_id", None),
            )
        return target

    def _filter_targets(self, targets: list) -> list:
        now = time.time()
        selected: list = []
        for target in targets:
            song_id = str(getattr(target, "song_id", "") or "").strip()
            if not song_id:
                continue
            if self._is_busy(song_id, now=now):
                continue
            escalated = self._maybe_escalate(target)
            if escalated is None:
                continue
            target = escalated
            kind = str(getattr(target, "kind", "") or "")
            # Skips still consume a slot so we surface them and mark attempted.
            state = self._song_state.get(song_id) or _SongAttemptState()
            if kind != "skip":
                if state.attempts >= _MAX_SESSION_ATTEMPTS_PER_SONG:
                    continue
                if state.last_attempt_at and (now - state.last_attempt_at) < _SONG_COOLDOWN_SEC:
                    continue
            else:
                # Don't keep re-reporting the same skip every poll.
                if state.last_kind == "skip" and state.last_lyrics_hash == str(
                    getattr(target, "lyrics_hash", "") or ""
                ):
                    if state.last_attempt_at and (now - state.last_attempt_at) < _SONG_COOLDOWN_SEC:
                        continue
            selected.append(target)
            if len(selected) >= _MAX_TARGETS_PER_CYCLE:
                break
        return selected

    def _mark_attempted(self, targets: tuple | list) -> None:
        now = time.time()
        for target in targets:
            song_id = str(getattr(target, "song_id", "") or "").strip()
            if not song_id:
                continue
            kind = str(getattr(target, "kind", "") or "")
            lyrics_hash = str(getattr(target, "lyrics_hash", "") or "").strip()
            state = self._song_state.get(song_id) or _SongAttemptState()
            if kind != "skip":
                state.attempts += 1
            if kind == "suno_retry" and lyrics_hash and lyrics_hash == state.last_lyrics_hash:
                state.suno_retry_same_hash += 1
            elif kind == "suno_retry":
                state.suno_retry_same_hash = 1
            else:
                state.suno_retry_same_hash = 0
            state.last_attempt_at = now
            state.last_kind = kind
            if lyrics_hash:
                state.last_lyrics_hash = lyrics_hash
            self._song_state[song_id] = state
            if kind in {"suno_rewrite", "suno_retry", "draft"}:
                # Avoid racing manual rewrite / duplicate helper cycles.
                self.mark_song_busy(song_id, seconds=120 if kind == "draft" else 180)

    def _poll(self) -> None:
        if not self._active or not self._enabled:
            return
        from shared.services.auto_pipeline_pause import is_auto_pipeline_paused

        if is_auto_pipeline_paused():
            return
        from shared.services.platform_client import api_has_access_token

        if not api_has_access_token(self._api):
            return
        self._auth_notice_shown = False
        if self._worker is not None and self._worker.isRunning():
            return
        worker = PipelineRecoveryScanWorker(
            self._api,
            history_limit=25,
            max_targets=_MAX_TARGETS_PER_CYCLE,
            target_filter=self._filter_targets,
            parent=None,
        )
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_succeeded(self, payload: object) -> None:
        if not isinstance(payload, PipelineRecoveryScanResult):
            self._timer.setInterval(_IDLE_POLL_MS)
            return
        if payload.attempted_targets:
            self._mark_attempted(payload.attempted_targets)
        actioned = int(payload.draft) + int(payload.rewrite) + int(payload.suno)
        skipped = int(getattr(payload, "skipped", 0) or 0)
        if actioned > 0 or skipped > 0:
            bits = [
                f"draft {payload.draft}",
                f"rewrite {payload.rewrite}",
                f"Suno {payload.suno}",
            ]
            if skipped:
                bits.append(f"skipped {skipped}")
            verb = "acted on" if actioned else "reviewed"
            emit_shell_status(
                f"Pipeline helper {verb} {actioned + skipped} song(s) ({', '.join(bits)}).",
                tone="success" if actioned else "warning",
            )
            self._timer.setInterval(_ACTIVE_POLL_MS)
            return
        if payload.candidate_count > 0:
            self._timer.setInterval(_ACTIVE_POLL_MS)
            return
        self._timer.setInterval(_IDLE_POLL_MS)

    def _on_failed(self, message: str) -> None:
        from shared.services.platform_client import is_auth_failure_message

        text = str(message or "").strip()
        if is_auth_failure_message(text):
            if not self._auth_notice_shown:
                self._auth_notice_shown = True
                emit_shell_status("Pipeline helper paused: sign in to continue.", tone="warning")
            self._timer.setInterval(_IDLE_POLL_MS)
            return
        if text and "No failed songs" not in text:
            emit_shell_status(f"Pipeline helper paused: {text}", tone="warning")
        self._timer.setInterval(_IDLE_POLL_MS)

    def _on_worker_finished(self) -> None:
        self._worker = None
