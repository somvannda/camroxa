from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QSize


class AspectRatioBox(QWidget):
    """Container that maintains aspect ratio for its child widget.

    The child always fills the full width of this box, with height
    calculated from the aspect ratio. Works correctly at any DPI scaling.
    """

    def __init__(self, child: QWidget, ratio_w: int = 16, ratio_h: int = 9, parent=None):
        super().__init__(parent)
        self._child = child
        self._ratio = float(ratio_w) / float(ratio_h)
        self._child.setParent(self)
        from python_app.views.helpers.style_helper import set_panel_role
        set_panel_role(self, "videoPreview")
        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.setMinimumHeight(100)

    def _apply_child_geometry(self) -> None:
        w = max(1, int(self.width()))
        h = max(1, int(self.height()))
        # Fit child maintaining aspect ratio within available space
        cw = w
        ch = int(round(w / self._ratio))
        if ch > h:
            # Height-constrained: fit by height
            ch = h
            cw = int(round(h * self._ratio))
        x = (w - cw) // 2
        y = (h - ch) // 2
        self._child.setGeometry(x, y, cw, ch)

    def set_ratio(self, ratio_w: int, ratio_h: int) -> None:
        try:
            w = max(1, int(ratio_w))
            h = max(1, int(ratio_h))
            self._ratio = float(w) / float(h)
        except Exception:
            self._ratio = 16.0 / 9.0
        self.updateGeometry()
        self._apply_child_geometry()
        self.update()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        width = max(1, int(w))
        return int(round(width / self._ratio))

    def sizeHint(self):
        w = max(1, int(self.width())) if self.width() > 0 else 480
        return QSize(w, self.heightForWidth(w))

    def minimumSizeHint(self):
        return QSize(200, int(round(200 / self._ratio)))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._apply_child_geometry()
