"""Stage board step cards — matches WorkflowPage stage cards."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from features.workflow.lib.workflow_steps import (
    WorkflowStep,
    detail_looks_empty,
    state_label,
    step_empty_hint,
)
from shared.icons.material_symbols import KPI_ICONS, material_symbol_pixmap
from shared.themes.badge_pills import STEP_STATE_BADGE_IDS, apply_badge_pill

STEP_ICON_KEYS = {
    "music": "music",
    "image": "image",
    "converter": "video",
    "merger": "merge",
    "youtube": "youtube",
}

STATE_OBJECT_NAMES = {
    "done": "workflow_step_done",
    "running": "workflow_step_running",
    "partial": "workflow_step_partial",
    "failed": "workflow_step_failed",
    "inactive": "workflow_step_inactive",
}

# Readable accents on dark surfaces — done uses theme success green (#00a86b).
STATE_ICON_COLORS = {
    "done": "#00c88b",
    "running": "#38bdf8",
    "partial": "#fbbf24",
    "failed": "#fb7185",
    "inactive": "#94a3b8",
}

STATE_BAR_COLORS = {
    "done": "#00a86b",
    "running": "#38bdf8",
    "partial": "#fbbf24",
    "failed": "#fb7185",
    "inactive": "#64748b",
}

# Keep all five stage cards visually aligned in the board row.
STAGE_CARD_MIN_HEIGHT = 178


class StageStepCard(QFrame):
    def __init__(self, step: WorkflowStep, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(STATE_OBJECT_NAMES.get(step.state, "workflow_step_inactive"))
        self.setMinimumHeight(STAGE_CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        icon_key = STEP_ICON_KEYS.get(step.key, "video")
        symbol, _default_accent = KPI_ICONS[icon_key]
        icon_color = STATE_ICON_COLORS.get(step.state, STATE_ICON_COLORS["inactive"])
        icon_wrap = QFrame()
        icon_wrap.setObjectName("workflow_step_icon_wrap")
        icon_wrap.setFixedSize(36, 36)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(material_symbol_pixmap(symbol, color=icon_color, size=18))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)

        text = QVBoxLayout()
        text.setSpacing(2)
        short_title = {
            "music": "Music",
            "image": "Image",
            "converter": "Convert",
            "merger": "Merger",
            "youtube": "YouTube",
        }.get(step.key, step.title)
        title = QLabel(short_title)
        title.setObjectName("workflow_step_title")
        subtitle = QLabel(step.title)
        subtitle.setObjectName("workflow_step_duration")
        text.addWidget(title)
        text.addWidget(subtitle)

        badge = QLabel()
        badge_id = STEP_STATE_BADGE_IDS.get(step.state, STEP_STATE_BADGE_IDS["inactive"])
        apply_badge_pill(badge, badge_id, label=state_label(step.state))

        header.addWidget(icon_wrap)
        header.addLayout(text, stretch=1)
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        percent_row = QHBoxLayout()
        percent = QLabel(f"{step.percent}%")
        percent.setObjectName("workflow_step_percent")
        duration = QLabel(step.duration)
        duration.setObjectName("workflow_step_duration")
        percent_row.addWidget(percent)
        percent_row.addStretch()
        percent_row.addWidget(duration)
        layout.addLayout(percent_row)

        bar_color = STATE_BAR_COLORS.get(step.state, STATE_BAR_COLORS["inactive"])
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(step.percent)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            "QProgressBar { background-color: rgba(255,255,255,0.1); border: none; border-radius: 4px; }"
            f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}"
        )
        layout.addWidget(bar)

        primary_text, secondary_text = _detail_lines(step)
        detail_label = QLabel(primary_text)
        detail_label.setObjectName("workflow_step_detail")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)
        secondary_label = QLabel(secondary_text)
        secondary_label.setObjectName("workflow_step_detail")
        secondary_label.setWordWrap(True)
        layout.addWidget(secondary_label)

        layout.addStretch(1)


def _detail_lines(step: WorkflowStep) -> tuple[str, str]:
    """Always return two concise detail lines so Music/Image match taller cards."""
    hint = step_empty_hint(step)
    primary = step.details[0] if step.details else ""
    secondary = step.details[1] if len(step.details) > 1 else ""
    status = state_label(step.state)
    show_awaiting = bool(hint) and (detail_looks_empty(primary) or step.state == "inactive")

    if show_awaiting and hint:
        return hint, status

    primary_text = hint if detail_looks_empty(primary) and hint else (
        "No detail yet" if detail_looks_empty(primary) else primary
    )
    if not detail_looks_empty(secondary) and secondary != primary_text:
        return primary_text, secondary
    return primary_text, status
