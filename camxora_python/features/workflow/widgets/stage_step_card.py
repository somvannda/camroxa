"""Stage board step cards — Create studio chrome."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.icons import create_icon
from features.create.widgets.studio_panel import NestedPanel
from features.workflow.lib.workflow_steps import (
    WorkflowStep,
    detail_looks_empty,
    state_label,
    step_empty_hint,
)
from shared.lib.ui_font import studio_font

STEP_ICON_KEYS = {
    "music": "music-4",
    "image": "image",
    "converter": "video",
    "merger": "video",
    "youtube": "youtube",
}

STATE_ICON_COLORS = {
    "done": "#00C878",
    "running": "#7C3AED",
    "partial": "#F59E0B",
    "failed": "#F43F5E",
    "inactive": "#8FA4BB",
}

STATE_BAR_COLORS = {
    "done": "#00C878",
    "running": "#7C3AED",
    "partial": "#F59E0B",
    "failed": "#F43F5E",
    "inactive": "#23415E",
}

STATE_BADGE_COLORS = {
    "done": "#00C878",
    "running": "#6335D9",
    "partial": "#F59E0B",
    "failed": "#F43F5E",
    "inactive": "#60758C",
}

STAGE_CARD_MIN_HEIGHT = 178


class StageStepCard(NestedPanel):
    def __init__(self, step: WorkflowStep, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(STAGE_CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        icon_name = STEP_ICON_KEYS.get(step.key, "video")
        icon_color = STATE_ICON_COLORS.get(step.state, STATE_ICON_COLORS["inactive"])
        icon = QLabel()
        icon.setPixmap(create_icon(icon_name, size=16, color=icon_color).pixmap(16, 16))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        title.setObjectName("PageSubtitle")
        title.setFont(studio_font(12))
        subtitle = QLabel(step.title)
        subtitle.setObjectName("FieldLabel")
        text.addWidget(title)
        text.addWidget(subtitle)

        badge = QLabel(state_label(step.state))
        badge.setObjectName("StatusBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(16)
        badge_color = STATE_BADGE_COLORS.get(step.state, STATE_BADGE_COLORS["inactive"])
        badge.setStyleSheet(
            "QLabel#StatusBadge {"
            f" background-color: {badge_color}; color: #ffffff; border: none;"
            " border-radius: 3px; padding: 0 7px;"
            " font-size: 10px; font-weight: 600;"
            "}"
        )

        header.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(text, stretch=1)
        header.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        percent_row = QHBoxLayout()
        percent = QLabel(f"{step.percent}%")
        percent.setObjectName("PageSubtitle")
        duration = QLabel(step.duration)
        duration.setObjectName("FieldLabel")
        percent_row.addWidget(percent)
        percent_row.addStretch()
        percent_row.addWidget(duration)
        layout.addLayout(percent_row)

        bar_color = STATE_BAR_COLORS.get(step.state, STATE_BAR_COLORS["inactive"])
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(step.percent)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setStyleSheet(
            "QProgressBar { background-color: #18304A; border: none; border-radius: 2px; }"
            f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 2px; }}"
        )
        layout.addWidget(bar)

        primary_text, secondary_text = _detail_lines(step)
        detail_label = QLabel(primary_text)
        detail_label.setObjectName("PageSubtitle")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)
        secondary_label = QLabel(secondary_text)
        secondary_label.setObjectName("FieldLabel")
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
