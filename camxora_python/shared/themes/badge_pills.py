"""Global badge/pill object names and tone helpers (deep_blue).

One visual family: non-clickable QLabel chips with soft tonal fills
(no border, no glow), colored text, ~5px radius. Tone object names keep
semantic mapping; chrome lives in deep_blue QSS. No unicode status icons.

"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QWidget

# Canonical object names — styled in deep_blue.MAIN_STYLESHEET
BADGE_ROLE = "badge_role"
BADGE_STAGE = "badge_stage"
BADGE_SUCCESS = "badge_success"
BADGE_WARNING = "badge_warning"
BADGE_DANGER = "badge_danger"
BADGE_INFO = "badge_info"
BADGE_MUTED = "badge_muted"
BADGE_SOLID_SUCCESS = "badge_solid_success"
BADGE_SOLID_DANGER = "badge_solid_danger"

# Legacy aliases still accepted by QSS (same geometry + colors)
STATUS_PILL = "status_pill"
STATUS_PILL_SUCCESS = "status_pill_success"
STATUS_PILL_WARNING = "status_pill_warning"
WORKFLOW_HEADER_PILL = "workflow_header_pill"
WORKFLOW_PILL_DONE = "workflow_pill_done"
WORKFLOW_PILL_RUNNING = "workflow_pill_running"
WORKFLOW_PILL_PARTIAL = "workflow_pill_partial"
WORKFLOW_PILL_FAILED = "workflow_pill_failed"
WORKFLOW_PILL_NEUTRAL = "workflow_pill_neutral"
WORKFLOW_STEP_BADGE_DONE = "workflow_step_badge_done"
WORKFLOW_STEP_BADGE_RUNNING = "workflow_step_badge_running"
WORKFLOW_STEP_BADGE_PARTIAL = "workflow_step_badge_partial"
WORKFLOW_STEP_BADGE_FAILED = "workflow_step_badge_failed"
WORKFLOW_STEP_BADGE_INACTIVE = "workflow_step_badge_inactive"

# Chip inset — horizontal ~12–14px; vertical kept short for compact chips.
# Enforced via QWidget contents margins: QLabel app-QSS padding alone is not a
# reliable text inset (sizeHint can grow while chrome stays flush to glyphs).
BADGE_PAD_H = 14
BADGE_PAD_V = 3

PIPELINE_STAGES = frozenset({"music", "image", "converter", "merger", "youtube"})
ACTIVE_VERB_STATUSES = frozenset(
    {
        "running",
        "rendering",
        "generating",
        "downloading",
        "converting",
        "merging",
        "uploading",
        "processing",
        "queued",
        "in progress",
    }
)
SUCCESS_STATUSES = frozenset(
    {"completed", "uploaded", "done", "success", "connected", "verified"}
)
IDLE_STATUSES = frozenset(
    {"ready", "waiting", "not started", "pending", "idle", "not connected", "—", "-"}
)

STEP_STATE_BADGE_IDS: dict[str, str] = {
    "done": WORKFLOW_STEP_BADGE_DONE,
    "running": WORKFLOW_STEP_BADGE_RUNNING,
    "partial": WORKFLOW_STEP_BADGE_PARTIAL,
    "failed": WORKFLOW_STEP_BADGE_FAILED,
    "inactive": WORKFLOW_STEP_BADGE_INACTIVE,
}


def normalize_badge_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def role_pill_object_name(_role: str | None = None) -> str:
    """Channel role chips (Primary / Secondary) — neutral family."""
    return BADGE_ROLE


def stage_pill_object_name(stage: str | None) -> str:
    """Pipeline focus chips (Converter, Merger, Music, …)."""
    key = normalize_badge_key(stage)
    if key == "error":
        return BADGE_DANGER
    if key == "done":
        return BADGE_SUCCESS
    if key in PIPELINE_STAGES:
        return BADGE_STAGE
    return BADGE_MUTED


def status_pill_object_name(status: str | None) -> str:
    """Run/step status chips (Partial, Completed, Failed, Ready, Connected, …)."""
    key = normalize_badge_key(status)
    if key == "failed" or key == "error":
        return BADGE_DANGER
    if key in SUCCESS_STATUSES:
        return BADGE_SUCCESS
    if key == "partial":
        return BADGE_WARNING
    if key in IDLE_STATUSES:
        return BADGE_MUTED
    if key in ACTIVE_VERB_STATUSES or key.replace("-", " ") in ACTIVE_VERB_STATUSES:
        return BADGE_INFO
    return BADGE_MUTED


def stage_tone_object_name(stage: str | None, status: str | None) -> str:
    """Legacy combined tone — prefer status when it carries meaning, else stage.

    Prefer ``stage_pill_object_name`` / ``status_pill_object_name`` for new UI.
    """
    status_key = normalize_badge_key(status)
    if status_key in {
        "failed",
        "partial",
        *SUCCESS_STATUSES,
        *IDLE_STATUSES,
        *ACTIVE_VERB_STATUSES,
    }:
        return status_pill_object_name(status)
    if status_key.replace("-", " ") in ACTIVE_VERB_STATUSES:
        return status_pill_object_name(status)
    return stage_pill_object_name(stage)


def format_badge_text(label: str | None, object_name: str, *, with_icon: bool = False) -> str:
    """Return chip label text with no unicode status prefixes.

    ``with_icon`` is retained for call-site compatibility and is ignored.
    """
    del object_name, with_icon
    return str(label or "").strip()


def apply_badge_pill(
    widget: QWidget,
    object_name: str,
    *,
    label: str | None = None,
    with_icon: bool = False,
) -> None:
    """Set object name (and optional labeled text) and force Qt style refresh.

    Applies soft tonal-fill chrome via QSS object names. Keeps widgets as
    non-interactive labels (arrow cursor, no text interaction).

    Horizontal Fixed keeps width at the padded sizeHint (no stretch, no shrink
    under Maximum). Contents margins are set *after* polish so they replace
    fragile QLabel QSS padding as the real glyph inset — never zeroed.
    """
    widget.setObjectName(object_name)
    if label is not None and hasattr(widget, "setText"):
        widget.setText(format_badge_text(label, object_name, with_icon=with_icon))

    # Fixed H: pad-aware sizeHint is exact width. Do not use setFixedWidth(text).
    widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    widget.setMinimumHeight(0)
    widget.setMinimumWidth(0)
    widget.setMaximumWidth(16777215)

    widget.setCursor(Qt.CursorShape.ArrowCursor)
    if hasattr(widget, "setAlignment"):
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if hasattr(widget, "setIndent"):
        widget.setIndent(0)
    # Do not call setMargin(0) / setContentsMargins(0,…): that was wiping inset.
    if hasattr(widget, "setTextInteractionFlags"):
        widget.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)

    # After polish: QSS padding lands in contentsMargins on some styles, but is
    # unreliable for QLabel painting. Force the compact 14×3 inset.
    widget.setContentsMargins(BADGE_PAD_H, BADGE_PAD_V, BADGE_PAD_H, BADGE_PAD_V)

    text = ""
    if hasattr(widget, "text"):
        text = str(widget.text() or "")
    if text:
        advance = widget.fontMetrics().horizontalAdvance(text)
        widget.setMinimumWidth(advance + BADGE_PAD_H * 2)

    widget.updateGeometry()
