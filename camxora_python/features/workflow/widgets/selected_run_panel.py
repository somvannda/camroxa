"""Selected run header, stage board, and detail panels."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_panel import NestedPanel, StudioPanel
from features.workflow.lib.workflow_steps import (
    WorkflowStep,
    build_current_focus,
    format_role_label,
    format_upload_status,
    resolve_run_status_label,
    run_includes_reel,
)
from features.workflow.widgets.stage_step_card import StageStepCard
from shared.lib.ui_font import studio_font
from shared.lib.video_runtime_inspection import ProgressRuntimePresentation
from shared.models.platform import ProgressRow

STAGE_BOARD_SUBTITLE = "Pipeline strip plus per-stage progress and readiness."

_PILL_COLORS = {
    "primary": "#6335D9",
    "secondary": "#60758C",
    "ok": "#6335D9",
    "alt": "#60758C",
    "done": "#00C878",
    "in progress": "#6335D9",
    "running": "#6335D9",
    "error": "#F43F5E",
    "failed": "#F43F5E",
    "pending": "#60758C",
}


def _studio_pill(widget: QLabel, label: str, *, color: str) -> None:
    widget.setText(label)
    widget.setObjectName("StatusBadge")
    widget.setFixedHeight(16)
    widget.setStyleSheet(
        "QLabel#StatusBadge {"
        f" background-color: {color}; color: #ffffff; border: none;"
        " border-radius: 3px; padding: 0 7px;"
        " font-size: 10px; font-weight: 600;"
        "}"
    )


class DetailPanel(NestedPanel):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        heading = QLabel(title.upper())
        heading.setObjectName("SectionLabel")
        heading.setFont(studio_font(11, uppercase=True, letter_spacing=110))
        layout.addWidget(heading)
        self._body = QVBoxLayout()
        self._body.setSpacing(4)
        layout.addLayout(self._body)

    def clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def set_paragraph(self, text: str, *, object_name: str = "PageSubtitle") -> None:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        self._body.addWidget(label)

    def add_line(self, text: str, *, object_name: str = "PageSubtitle") -> None:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        self._body.addWidget(label)


class SelectedRunPanel(StudioPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._stage_cards: list[StageStepCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        eyebrow = QLabel("SELECTED RUN")
        eyebrow.setObjectName("SectionLabel")
        eyebrow.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        root.addWidget(eyebrow)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._channel = QLabel("No run selected")
        self._channel.setObjectName("PageTitle")
        self._channel.setFont(studio_font(20))
        title_row.addWidget(self._channel)
        self._role_pill = QLabel()
        self._stage_pill = QLabel()
        self._status_pill = QLabel()
        title_row.addWidget(self._role_pill)
        title_row.addWidget(self._stage_pill)
        title_row.addWidget(self._status_pill)
        title_row.addStretch()
        root.addLayout(title_row)

        self._run_meta = QLabel("Select a run from the left to see the stage board.")
        self._run_meta.setObjectName("FieldLabel")
        root.addWidget(self._run_meta)

        self._focus = QLabel("Choose a lane to inspect its stage progression and current focus.")
        self._focus.setObjectName("PageSubtitle")
        self._focus.setWordWrap(True)
        root.addWidget(self._focus)

        board_title = QLabel("STAGE BOARD")
        board_title.setObjectName("SectionLabel")
        board_title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        board_subtitle = QLabel(STAGE_BOARD_SUBTITLE)
        board_subtitle.setObjectName("PageSubtitle")
        board_subtitle.setWordWrap(True)
        root.addWidget(board_title)
        root.addWidget(board_subtitle)

        self._stage_grid = QGridLayout()
        self._stage_grid.setSpacing(10)
        self._stage_grid.setRowStretch(0, 1)
        root.addLayout(self._stage_grid, 1)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(10)
        self._notes_panel = DetailPanel("Notes")
        self._assets_panel = DetailPanel("Asset Readiness")
        self._upload_panel = DetailPanel("Upload")
        detail_row.addWidget(self._notes_panel, stretch=14)
        detail_row.addWidget(self._assets_panel, stretch=10)
        detail_row.addWidget(self._upload_panel, stretch=10)
        root.addLayout(detail_row)

    def show_loading(self) -> None:
        self._reset_header(loading=True)

    def show_no_selection(self, *, loading: bool = False) -> None:
        self._reset_header(loading=loading)

    def _reset_header(self, *, loading: bool) -> None:
        self._channel.setText("No run selected")
        self._role_pill.hide()
        self._stage_pill.hide()
        self._status_pill.hide()
        self._run_meta.setText("Select a run from the left to see the stage board.")
        self._focus.setText(
            "Loading workflow details..." if loading else
            "Choose a lane to inspect its stage progression and current focus."
        )
        self._clear_stage_cards()
        self._render_detail_panels(None, None, loading=loading)

    def apply(
        self,
        row: ProgressRow,
        runtime: ProgressRuntimePresentation | None,
        steps: list[WorkflowStep],
    ) -> None:
        effective_stage = runtime.stage if runtime else row.stage
        effective_status = runtime.status if runtime else row.status
        status_label = resolve_run_status_label(
            effective_stage,
            effective_status,
            row,
            runtime.converter if runtime else row.converter,
            runtime.merge if runtime else row.merge,
        )

        self._channel.setText(row.channel)
        _studio_pill(
            self._role_pill,
            format_role_label(row.meta.role),
            color=_PILL_COLORS.get(str(row.meta.role).lower(), "#6335D9"),
        )
        self._role_pill.show()
        _studio_pill(
            self._stage_pill,
            effective_stage,
            color=_PILL_COLORS.get(str(effective_stage).lower(), "#60758C"),
        )
        self._stage_pill.show()
        _studio_pill(
            self._status_pill,
            status_label,
            color=_PILL_COLORS.get(str(status_label).lower(), "#6335D9"),
        )
        self._status_pill.show()
        self._run_meta.setText(f"Run date {row.run_date} · Last updated {row.updated}")
        self._focus.setText(build_current_focus(row, runtime))

        self._clear_stage_cards()
        for index, step in enumerate(steps):
            card = StageStepCard(step)
            self._stage_cards.append(card)
            self._stage_grid.addWidget(card, 0, index)
            self._stage_grid.setColumnStretch(index, 1)

        self._render_detail_panels(row, runtime, loading=False)

    def _clear_stage_cards(self) -> None:
        for card in self._stage_cards:
            self._stage_grid.removeWidget(card)
            card.deleteLater()
        self._stage_cards.clear()

    def _render_detail_panels(
        self,
        row: ProgressRow | None,
        runtime: ProgressRuntimePresentation | None,
        *,
        loading: bool,
    ) -> None:
        for panel in (self._notes_panel, self._assets_panel, self._upload_panel):
            panel.clear_body()

        if row is None:
            self._notes_panel.set_paragraph(
                "Loading…" if loading else "Select a run."
            )
            self._assets_panel.add_line("No run selected.")
            self._upload_panel.add_line("No run selected.")
            return

        notes = str((runtime.notes if runtime else row.notes) or "").strip()
        self._notes_panel.set_paragraph(notes or "No operator notes for this lane.")
        self._assets_panel.add_line(f"Long {'ready' if row.meta.long_ready else 'waiting'}")
        if run_includes_reel(row, runtime):
            self._assets_panel.add_line(f"Reel {'ready' if row.meta.reel_ready else 'waiting'}")

        upload_status = format_upload_status(row)
        self._upload_panel.add_line(upload_status)
        if row.meta.youtube_success > 0 or row.meta.youtube_url:
            self._upload_panel.add_line(
                f"Success {row.meta.youtube_success}",
                object_name="FieldLabel",
            )
        elif row.meta.youtube_failed > 0:
            self._upload_panel.add_line(
                f"Failed {row.meta.youtube_failed}",
                object_name="FieldLabel",
            )
        elif row.meta.youtube_pending > 0:
            self._upload_panel.add_line(
                f"Pending {row.meta.youtube_pending}",
                object_name="FieldLabel",
            )
        else:
            self._upload_panel.add_line("No upload yet", object_name="FieldLabel")
        if row.meta.youtube_url:
            self._upload_panel.add_line(
                row.meta.youtube_url,
                object_name="FieldLabel",
            )
