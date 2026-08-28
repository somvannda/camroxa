"""Add / edit channel profile dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.studio_controls import StudioComboBox
from features.profile.profile_format import visibility_key
from features.profile.profile_styles import build_profile_page_qss
from shared.lib.settings_workspace import resolve_profile_folder_name
from shared.lib.ui_font import studio_font
from shared.models.auth import ProfileResponse
from shared.models.platform import profile_image_mode, profile_visibility

RESOLUTIONS = ("1920x1080", "1080x1920", "1080x1080", "1280x720")
IMAGE_MODES = (
    ("bg_thumb", "Background + Thumbnail"),
    ("bg_only", "Background only"),
    ("thumb_only", "Thumbnail only"),
)
VISIBILITIES = ("Unlisted", "Public", "Private")


def _image_mode_key(profile: ProfileResponse | None) -> str:
    if profile is None:
        return "bg_thumb"
    label = profile_image_mode(profile)
    for key, text in IMAGE_MODES:
        if text == label:
            return key
    return "bg_thumb"


class ProfileDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        profile: ProfileResponse | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profile_dialog")
        self.setStyleSheet(build_profile_page_qss())
        self.setFont(studio_font(12))
        self._profile = profile
        self.setWindowTitle("Edit Profile" if profile else "Add Profile")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self._name = QLineEdit(profile.name if profile else "")
        self._name.setPlaceholderText("Channel name")
        self._prefix = QLineEdit((profile.run_prefix or "") if profile else "")
        self._prefix.setPlaceholderText("Run prefix")
        self._resolution = StudioComboBox()
        self._resolution.addItems(RESOLUTIONS)
        if profile and profile.output_resolution:
            self._resolution.setCurrentText(profile.output_resolution)
        else:
            self._resolution.setCurrentText("1920x1080")
        self._image_mode = StudioComboBox()
        for key, label in IMAGE_MODES:
            self._image_mode.addItem(label, key)
        self._image_mode.setCurrentIndex(max(0, self._image_mode.findData(_image_mode_key(profile))))
        self._visibility = StudioComboBox()
        self._visibility.addItems(VISIBILITIES)
        if profile:
            self._visibility.setCurrentText(visibility_key(profile_visibility(profile)).title())
        self._folder = QLineEdit((profile.folder_name or "") if profile else "")
        self._folder.setPlaceholderText("Output folder")
        form.addRow("Name", self._name)
        form.addRow("Run prefix", self._prefix)
        form.addRow("Resolution", self._resolution)
        form.addRow("Image mode", self._image_mode)
        form.addRow("Visibility", self._visibility)
        form.addRow("Folder", self._folder)
        layout.addLayout(form)

        buttons = QDialogButtonBox()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryButton")
        save = QPushButton("Save" if profile else "Create Profile")
        save.setObjectName("TransportPrimary")
        save.setDefault(True)
        buttons.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        layout.addWidget(buttons)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    def payload(self) -> dict[str, object]:
        name = self._name.text().strip()
        prefix = self._prefix.text().strip() or None
        folder = self._folder.text().strip() or None
        return {
            "name": name,
            "folder_name": resolve_profile_folder_name(name, folder),
            "run_prefix": prefix,
            "output_resolution": self._resolution.currentText(),
            "image_config": {"mode": self._image_mode.currentData()},
            "youtube_config": {"visibility": self._visibility.currentText().lower()},
        }
