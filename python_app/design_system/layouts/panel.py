"""Panel layout component for the design system.

Provides a container with optional header area, content area,
and configurable border/separator between sections.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFrame

from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.widgets.labels import TypedLabel

# Token defaults
_BORDER_COLOR = DEFAULT_DARK_THEME.colors.border  # #27354b
_SEPARATOR_COLOR = DEFAULT_DARK_THEME.colors.separator  # #27354b
_BORDER_WIDTH = DEFAULT_DARK_THEME.shape.border_width_thin  # 1
_PADDING = DEFAULT_DARK_THEME.spacing.padding_lg  # 16
_GAP = DEFAULT_DARK_THEME.spacing.gap_md  # 8


class Panel(QWidget):
    """A panel container with optional header, content area, and configurable border.

    The Panel provides structural separation of header and content areas with
    an optional border and separator line between them.

    Parameters
    ----------
    header : str
        Optional header text rendered with section_title styling.
    show_border : bool
        Whether to show a border around the panel. Defaults to True.
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        header: str = "",
        show_border: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._show_border = show_border

        # Apply border styling if enabled
        if show_border:
            self.setStyleSheet(
                f"Panel {{ border: {_BORDER_WIDTH}px solid {_BORDER_COLOR}; }}"
            )
        self.setObjectName("Panel")

        # Main layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(_PADDING, _PADDING, _PADDING, _PADDING)
        self._main_layout.setSpacing(0)

        # Header area
        self._header_widget: QWidget | None = None
        self._default_header_label = TypedLabel("", level="section_title")
        self._default_header_label.setVisible(False)
        self._main_layout.addWidget(self._default_header_label)

        # Separator between header and content
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        self._separator.setStyleSheet(
            f"QFrame {{ color: {_SEPARATOR_COLOR}; background: {_SEPARATOR_COLOR}; "
            f"max-height: {_BORDER_WIDTH}px; }}"
        )
        self._separator.setVisible(False)
        self._main_layout.addWidget(self._separator)

        # Content area
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(_GAP)
        self._main_layout.addLayout(self._content_layout)

        if header:
            self._default_header_label.setText(header)
            self._default_header_label.setVisible(True)
            self._separator.setVisible(True)

    def setHeaderWidget(self, widget: QWidget) -> None:
        """Replace the header area with a custom widget.

        Removes the default header label and inserts the provided widget
        at the top of the panel, with a separator below it.

        Parameters
        ----------
        widget : QWidget
            The widget to use as the panel header.
        """
        # Remove the existing header widget or default label
        if self._header_widget is not None:
            self._main_layout.removeWidget(self._header_widget)
            self._header_widget.setParent(None)
        else:
            self._default_header_label.setVisible(False)

        self._header_widget = widget
        # Insert at position 0 (before separator)
        self._main_layout.insertWidget(0, widget)
        self._separator.setVisible(True)

    def addContent(self, widget: QWidget) -> None:
        """Add a widget to the panel's content area.

        Parameters
        ----------
        widget : QWidget
            The widget to add to the content section below the header/separator.
        """
        self._content_layout.addWidget(widget)
