from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


class TimelineConnector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = "#31435d"
        self.setFixedSize(70, 220)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_color(self, color: str) -> None:
        self._color = str(color or "#31435d")
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._color))
        pen.setWidth(6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        y = int(10 + 98 // 2)
        p.drawLine(6, y, int(self.width() - 6), y)
        p.end()


class ProgressRingStep(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._details: list[str] = []
        self._duration_text = ""
        self._percent = 0
        self._state = "inactive"
        self._icon = None
        self._base_ring = "#31435d"
        self._active_ring = "#2d71df"
        self._text = "#eef4ff"
        self._text_muted = "#8ea4c7"
        self._icon_color = "#d9e5fb"
        self.setMinimumHeight(220)
        self.setMinimumWidth(180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_data(self, *, title: str, percent: int, state: str, icon, details: list[str] | None = None, duration_text: str = "", icon_color: str | None = None) -> None:
        self._title = str(title or "")
        self._percent = int(max(0, min(100, int(percent))))
        self._state = str(state or "inactive").strip().lower()
        self._icon = icon
        self._details = [str(x or "").strip() for x in (details or []) if str(x or "").strip()]
        self._duration_text = str(duration_text or "").strip()
        if icon_color is not None:
            self._icon_color = str(icon_color or self._icon_color)

        if self._state == "done":
            self._active_ring = "#45c887"
        elif self._state == "failed":
            self._active_ring = "#d65a5a"
        elif self._state == "cancelled":
            self._active_ring = "#5e7598"
        elif self._state == "running":
            self._active_ring = "#2d71df"
        else:
            self._active_ring = "#2d71df" if self._percent > 0 else "#31435d"
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = int(self.width())
        h = int(self.height())

        circle_d = 98
        ring_w = 9
        top_pad = 10

        cx = w // 2
        cy = top_pad + circle_d // 2

        rect = QRectF(float(cx - circle_d // 2), float(cy - circle_d // 2), float(circle_d), float(circle_d))

        pen_bg = QPen(QColor(self._base_ring))
        pen_bg.setWidth(ring_w)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_bg)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(rect, 0, 360 * 16)

        if self._percent > 0 and self._state in {"running", "done", "failed", "cancelled"}:
            pen_fg = QPen(QColor(self._active_ring))
            pen_fg.setWidth(ring_w)
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_fg)
            span = int(-360.0 * float(self._percent) / 100.0 * 16.0)
            p.drawArc(rect, 90 * 16, span)
        elif self._percent > 0:
            pen_fg = QPen(QColor(self._active_ring))
            pen_fg.setWidth(ring_w)
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_fg)
            span = int(-360.0 * float(self._percent) / 100.0 * 16.0)
            p.drawArc(rect, 90 * 16, span)

        if self._icon is not None:
            try:
                pm = self._icon.pixmap(QSize(26, 26))
                p.drawPixmap(int(cx - pm.width() // 2), int(cy - 20), pm)
            except Exception:
                pass

        p.setPen(QColor(self._text if self._state != "inactive" else self._text_muted))
        f = QFont("Open Sans", 10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(0, top_pad + circle_d + 14, w, 22, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self._title)

        sub_y = top_pad + circle_d + 38
        p.setPen(QColor(self._text_muted))
        f2 = QFont("Open Sans", 9)
        p.setFont(f2)

        if self._duration_text:
            p.drawText(0, sub_y, w, 18, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self._duration_text)
            sub_y += 20

        for line in (self._details or [])[:3]:
            p.drawText(0, sub_y, w, 18, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, line)
            sub_y += 18

        p.end()


class WorkflowTimeline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list[dict] = []
        self._step_widgets: list[ProgressRingStep] = []
        self._connector_widgets: list[TimelineConnector] = []
        self._keys: list[str] = []
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(10, 10, 10, 10)
        self._row.setSpacing(0)
        self.setMinimumHeight(240)

    def set_steps(self, steps: list[dict]) -> None:
        steps2 = [dict(s) for s in (steps or []) if isinstance(s, dict)]
        keys2 = [str(s.get("key", "") or str(s.get("title", "") or "")).strip() for s in steps2]

        if not steps2:
            self._steps = []
            self._keys = []
            self._step_widgets = []
            self._connector_widgets = []
            while self._row.count():
                item = self._row.takeAt(0)
                w = item.widget() if item is not None else None
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            self.update()
            return

        can_update = bool(self._keys) and len(self._keys) == len(keys2) and all(a == b for a, b in zip(self._keys, keys2))
        if not can_update:
            self._steps = steps2
            self._keys = keys2
            self._step_widgets = []
            self._connector_widgets = []
            while self._row.count():
                item = self._row.takeAt(0)
                w = item.widget() if item is not None else None
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

            for i, step in enumerate(steps2):
                ring = ProgressRingStep(self)
                self._row.addWidget(ring)
                self._step_widgets.append(ring)

                if i < len(steps2) - 1:
                    conn = TimelineConnector(self)
                    self._row.addWidget(conn)
                    self._connector_widgets.append(conn)
        else:
            self._steps = steps2
            self._keys = keys2

        for i, step in enumerate(steps2):
            ring = self._step_widgets[i]
            ring.set_data(
                title=str(step.get("title", "")),
                percent=int(step.get("percent", 0)),
                state=str(step.get("state", "inactive")),
                icon=step.get("icon"),
                details=step.get("details"),
                duration_text=str(step.get("duration_text", "")),
                icon_color=step.get("icon_color"),
            )

        for conn in self._connector_widgets:
            conn.update()

    def update_step(self, key: str, *, title: str | None = None, percent: int | None = None, state: str | None = None, icon=None, details: list[str] | None = None, duration_text: str | None = None, icon_color: str | None = None) -> None:
        idx = -1
        for i, s in enumerate(self._steps):
            if str(s.get("key", "")).strip() == str(key).strip():
                idx = i
                break
        if idx < 0 or idx >= len(self._step_widgets):
            return
        if title is not None:
            self._steps[idx]["title"] = title
        if percent is not None:
            self._steps[idx]["percent"] = percent
        if state is not None:
            self._steps[idx]["state"] = state
        if icon is not None:
            self._steps[idx]["icon"] = icon
        if details is not None:
            self._steps[idx]["details"] = details
        if duration_text is not None:
            self._steps[idx]["duration_text"] = duration_text
        if icon_color is not None:
            self._steps[idx]["icon_color"] = icon_color
        ring = self._step_widgets[idx]
        step = self._steps[idx]
        ring.set_data(
            title=str(step.get("title", "")),
            percent=int(step.get("percent", 0)),
            state=str(step.get("state", "inactive")),
            icon=step.get("icon"),
            details=step.get("details"),
            duration_text=str(step.get("duration_text", "")),
            icon_color=step.get("icon_color"),
        )

        start_idx = max(0, idx - 1)
        end_idx = min(len(self._connector_widgets) - 1, idx)
        for ci in range(start_idx, end_idx + 1):
            if 0 <= ci < len(self._connector_widgets):
                conn = self._connector_widgets[ci]
                c_state = str(self._steps[ci].get("state", "inactive"))
                n_state = str(self._steps[ci + 1].get("state", "inactive"))
                ccol = "#31435d"
                if c_state in {"done"} and n_state in {"done"}:
                    ccol = "#45c887"
                elif c_state in {"done"} and n_state in {"running"}:
                    ccol = "#2d71df"
                elif c_state in {"done"} and n_state in {"failed"}:
                    ccol = "#d65a5a"
                elif c_state in {"done"} and n_state in {"cancelled"}:
                    ccol = "#5e7598"
                elif c_state in {"failed"}:
                    ccol = "#d65a5a"
                if state in {"failed"}:
                    ccol = "#d65a5a"
                if state in {"cancelled"}:
                    ccol = "#5e7598"
                conn.set_color(ccol)
        self.update()
