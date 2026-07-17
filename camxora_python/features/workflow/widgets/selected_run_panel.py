"""Selected run header, stage board, and detail panels."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.workflow.lib.workflow_steps import (
    WorkflowStep,
    build_current_focus,
    format_role_label,
    format_upload_status,
    resolve_run_status_label,
    run_includes_reel,
)
from features.workflow.widgets.stage_step_card import StageStepCard
from shared.lib.video_runtime_inspection import ProgressRuntimePresentation
from shared.models.platform import ProgressRow
from shared.themes.badge_pills import (
    apply_badge_pill,
    role_pill_object_name,
    stage_pill_object_name,
    status_pill_object_name,
)

STAGE_BOARD_SUBTITLE = "Pipeline strip plus per-stage progress and readiness."


class DetailPanel(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workflow_detail_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("workflow_section_label")
        layout.addWidget(heading)
        self._body = QVBoxLayout()
        self._body.setSpacing(4)
        layout.addLayout(self._body)

    def clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def set_paragraph(self, text: str, *, object_name: str = "workflow_detail_text") -> None:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        self._body.addWidget(label)

    def add_line(self, text: str, *, object_name: str = "workflow_detail_text") -> None:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        self._body.addWidget(label)


class SelectedRunPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workflow_selected_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._stage_cards: list[StageStepCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("workflow_selected_header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(8)

        eyebrow = QLabel("Selected Run")
        eyebrow.setObjectName("workflow_eyebrow")
        header_layout.addWidget(eyebrow)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._channel = QLabel("No run selected")
        self._channel.setObjectName("workflow_channel_title")
        title_row.addWidget(self._channel)
        self._role_pill = QLabel()
        apply_badge_pill(self._role_pill, role_pill_object_name())
        self._stage_pill = QLabel()
        self._status_pill = QLabel()
        title_row.addWidget(self._role_pill)
        title_row.addWidget(self._stage_pill)
        title_row.addWidget(self._status_pill)
        title_row.addStretch()
        header_layout.addLayout(title_row)

        self._run_meta = QLabel("Select a run from the left to see the stage board.")
        self._run_meta.setObjectName("workflow_run_meta")
        header_layout.addWidget(self._run_meta)

        self._focus = QLabel("Choose a lane to inspect its stage progression and current focus.")
        self._focus.setObjectName("workflow_focus_text")
        self._focus.setWordWrap(True)
        header_layout.addWidget(self._focus)
        root.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 16)
        body.setSpacing(10)

        board_title = QLabel("Stage Board")
        board_title.setObjectName("workflow_eyebrow")
        board_subtitle = QLabel(STAGE_BOARD_SUBTITLE)
        board_subtitle.setObjectName("workflow_run_meta")
        board_subtitle.setWordWrap(True)
        body.addWidget(board_title)
        body.addWidget(board_subtitle)

        self._stage_grid = QGridLayout()
        self._stage_grid.setSpacing(12)
        self._stage_grid.setRowStretch(0, 1)
        body.addLayout(self._stage_grid)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(12)
        self._notes_panel = DetailPanel("Notes")
        self._assets_panel = DetailPanel("Asset Readiness")
        self._upload_panel = DetailPanel("Upload")
        detail_row.addWidget(self._notes_panel, stretch=14)
        detail_row.addWidget(self._assets_panel, stretch=10)
        detail_row.addWidget(self._upload_panel, stretch=10)
        body.addLayout(detail_row)
        root.addLayout(body)

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
        apply_badge_pill(
            self._role_pill,
            role_pill_object_name(row.meta.role),
            label=format_role_label(row.meta.role),
        )
        self._role_pill.show()
        apply_badge_pill(
            self._stage_pill,
            stage_pill_object_name(effective_stage),
            label=effective_stage,
        )
        self._stage_pill.show()
        apply_badge_pill(
            self._status_pill,
            status_pill_object_name(status_label),
            label=status_label,
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
                object_name="workflow_detail_muted",
            )
        elif row.meta.youtube_failed > 0:
            self._upload_panel.add_line(
                f"Failed {row.meta.youtube_failed}",
                object_name="workflow_detail_muted",
            )
        elif row.meta.youtube_pending > 0:
            self._upload_panel.add_line(
                f"Pending {row.meta.youtube_pending}",
                object_name="workflow_detail_muted",
            )
        else:
            self._upload_panel.add_line("No upload yet", object_name="workflow_detail_muted")
        if row.meta.youtube_url:
            self._upload_panel.add_line(
                row.meta.youtube_url,
                object_name="workflow_detail_muted",
            )
