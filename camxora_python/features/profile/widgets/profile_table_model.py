"""Channel profile table model."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from features.profile.profile_format import profile_updated_label
from shared.lib.formatting import format_optional
from shared.models.auth import ProfileResponse
from shared.models.platform import profile_image_mode, profile_visibility

COLUMNS = (
    "Name",
    "Run Prefix",
    "Output resolution",
    "Image mode",
    "Visibility",
    "Updated",
    "",
)

COL_NAME = 0
COL_PREFIX = 1
COL_RESOLUTION = 2
COL_IMAGE_MODE = 3
COL_VISIBILITY = 4
COL_UPDATED = 5
COL_ACTIONS = 6


class ProfileTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[ProfileResponse] = []
        self._placeholder: str | None = None

    def set_placeholder(self, message: str) -> None:
        self.beginResetModel()
        self._rows = []
        self._placeholder = message
        self.endResetModel()

    def set_profiles(self, profiles: list[ProfileResponse]) -> None:
        self.beginResetModel()
        self._rows = list(profiles)
        self._placeholder = None
        self.endResetModel()

    def profile_at(self, row: int) -> ProfileResponse | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        if self._placeholder:
            return 1
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(COLUMNS):
                return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if self._placeholder:
            if role == Qt.ItemDataRole.DisplayRole and index.column() == COL_NAME:
                return self._placeholder
            return None
        if not (0 <= index.row() < len(self._rows)):
            return None
        profile = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(profile, index.column())
        if role == Qt.ItemDataRole.UserRole:
            return profile
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def _display(self, profile: ProfileResponse, column: int) -> str:
        if column == COL_NAME:
            return profile.name
        if column == COL_PREFIX:
            return format_optional(profile.run_prefix)
        if column == COL_RESOLUTION:
            return profile.output_resolution or "--"
        if column == COL_IMAGE_MODE:
            return profile_image_mode(profile)
        if column == COL_VISIBILITY:
            return profile_visibility(profile)
        if column == COL_UPDATED:
            return profile_updated_label(profile)
        if column == COL_ACTIONS:
            return ""
        return ""
