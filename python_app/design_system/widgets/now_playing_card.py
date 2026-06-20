"""Now Playing Card composite widget for the design system.

Provides NowPlayingCard — a composite widget that displays track metadata
(album art, title, artist, duration) in a card layout with an accent-colored
left border highlight.
"""

import os.path

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from python_app.design_system.widgets.labels import TypedLabel


class NowPlayingCard(QWidget):
    """A card displaying current track information with album art.

    Layout structure:
        - Outer container with accent left border, rounded corners, raised surface bg
        - Internal QHBoxLayout: [album_art_area | text_info_area]
        - album_art_area: fixed-size QLabel showing QPixmap or placeholder
        - text_info_area: QVBoxLayout with title, artist, and duration labels

    Usage:
        card = NowPlayingCard()
        card.setTrackInfo("My Song", "Artist Name", "3:45", "/path/to/art.png")
    """

    _ALBUM_ART_SIZE = 56

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Apply card styling: accent left border, raised surface, rounded corners
        self.setStyleSheet(
            "NowPlayingCard {"
            "  background-color: #0f1538;"
            "  border-left: 3px solid #00d4ff;"
            "  border-radius: 8px;"
            "  padding: 8px;"
            "}"
        )

        # Main horizontal layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # Album art area
        self._album_art_label = QLabel(self)
        self._album_art_label.setFixedSize(self._ALBUM_ART_SIZE, self._ALBUM_ART_SIZE)
        self._album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_placeholder()
        main_layout.addWidget(self._album_art_label)

        # Text info area
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_label = TypedLabel("", level="section_title")
        self._artist_label = TypedLabel("", level="caption")
        self._duration_label = TypedLabel("", level="muted")

        text_layout.addWidget(self._title_label)
        text_layout.addWidget(self._artist_label)
        text_layout.addWidget(self._duration_label)
        text_layout.addStretch()

        main_layout.addLayout(text_layout, 1)

    def setTrackInfo(
        self,
        title: str,
        artist: str,
        duration: str = "",
        album_art_path: str = "",
    ) -> None:
        """Update the displayed track information.

        Args:
            title: Track title displayed at section_title level.
            artist: Artist name displayed at caption level.
            duration: Duration string (e.g. "3:45") displayed at muted level.
            album_art_path: Path to album art image file. Shows placeholder if
                empty or file doesn't exist.
        """
        self._title_label.setText(title)
        self._artist_label.setText(artist)
        self._duration_label.setText(duration)

        if album_art_path and os.path.isfile(album_art_path):
            pixmap = QPixmap(album_art_path)
            scaled = pixmap.scaled(
                self._ALBUM_ART_SIZE,
                self._ALBUM_ART_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._album_art_label.setPixmap(scaled)
            self._album_art_label.setStyleSheet("")
        else:
            self._show_placeholder()

    def _show_placeholder(self) -> None:
        """Display a muted placeholder with a music note icon."""
        self._album_art_label.setPixmap(QPixmap())  # Clear any existing pixmap
        self._album_art_label.setText("\u266b")  # Music note character ♫
        self._album_art_label.setStyleSheet(
            "QLabel {"
            "  background-color: #1a2538;"
            "  border-radius: 4px;"
            "  color: #8ea4c7;"
            "  font-size: 24px;"
            "}"
        )
