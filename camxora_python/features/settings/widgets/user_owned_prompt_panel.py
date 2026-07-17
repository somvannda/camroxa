"""User-owned music description/structure editor for Settings."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QWidget,
)

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SHELL_TEXT_EDIT_ID
from shared.widgets.settings_ui import SettingsPanel, form_row, note_box


class UserOwnedPromptPanel(QWidget):
    """Coordinates a user-catalog list card and a prompt editor card."""

    saved = Signal()
    deleted = Signal()
    default_requested = Signal(str)

    def __init__(
        self,
        *,
        list_title: str,
        editor_title: str,
        content_placeholder: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.hide()
        self._items: dict[str, dict[str, str]] = {}
        self._selected_id = ""
        self._creating = False
        self._actions_enabled = True

        self.list_card = SettingsPanel(
            list_title,
            subtitle="Your private prompts. Select one to edit or delete.",
            fill_available_height=True,
        )
        self.list_card.setMinimumWidth(320)
        self.list_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._new_btn = QPushButton("New")
        self._new_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self.list_card.add_action(self._new_btn)
        self.list_card.add_action(self._delete_btn)

        self._list = QListWidget()
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.list_card.add_widget(self._list, stretch=1)
        self.list_card.add_widget(note_box(
            "Prompts sync to the server and appear in Music dropdowns. "
            "Selecting one sets it as the active Music default (only one active at a time)."
        ))

        self.editor_card = SettingsPanel(
            editor_title,
            subtitle="Edit the name and content for your selected prompt.",
            fill_available_height=True,
        )
        self.editor_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._save_btn = QPushButton("Save")
        self.editor_card.add_action(self._save_btn)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Prompt name")
        self._content_input = QTextEdit()
        self._content_input.setObjectName(SHELL_TEXT_EDIT_ID)
        self._content_input.setPlaceholderText(content_placeholder)
        self._content_input.setMinimumHeight(160)
        self._content_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._empty_note = note_box("Select a prompt from User catalog or click New to create one.")
        self.editor_card.add_widget(form_row("Name", self._name_input))
        self.editor_card.add_widget(form_row("Content", self._content_input), stretch=1)
        self.editor_card.add_widget(self._empty_note)

        self._new_btn.clicked.connect(self._start_create)
        self._save_btn.clicked.connect(self.saved.emit)
        self._delete_btn.clicked.connect(self.deleted.emit)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._refresh_editor_state()

    def item_count(self) -> int:
        return len(self._items)

    def set_actions_enabled(self, enabled: bool) -> None:
        self._actions_enabled = enabled
        self._refresh_editor_state()

    def set_active_id(self, item_id: str) -> None:
        active = str(item_id or "").strip()
        for row in range(self._list.count()):
            list_item = self._list.item(row)
            if list_item is None:
                continue
            row_id = str(list_item.data(256) or "")
            stored = self._items.get(row_id, {})
            base_name = str(stored.get("name") or list_item.text().replace(" · active", "")).strip()
            list_item.setText(f"{base_name} · active" if row_id == active else base_name)

    def upsert_item(self, item: dict[str, str]) -> None:
        item_id = str(item.get("id") or "")
        if not item_id:
            return
        self._items[item_id] = item
        self._creating = False
        self._list.blockSignals(True)
        found_row = -1
        for row in range(self._list.count()):
            list_item = self._list.item(row)
            if list_item is not None and str(list_item.data(256) or "") == item_id:
                list_item.setText(str(item.get("name") or ""))
                found_row = row
                break
        if found_row < 0:
            list_item = QListWidgetItem(str(item.get("name") or ""))
            list_item.setData(256, item_id)
            self._list.addItem(list_item)
        self._list.blockSignals(False)
        self._select_id(item_id)
        self._refresh_editor_state()

    def set_items(self, items: list[dict[str, str]]) -> None:
        self._items = {item["id"]: item for item in items if item.get("id")}
        self._list.blockSignals(True)
        self._list.clear()
        for item in items:
            list_item = QListWidgetItem(str(item.get("name") or ""))
            list_item.setData(256, str(item.get("id") or ""))
            self._list.addItem(list_item)
        self._list.blockSignals(False)
        if not self._creating:
            if self._selected_id and self._selected_id in self._items:
                self._select_id(self._selected_id)
            elif items:
                self._select_id(str(items[0]["id"]))
            else:
                self._selected_id = ""
                self._name_input.clear()
                self._content_input.clear()
        self._refresh_editor_state()

    def _select_id(self, item_id: str) -> None:
        self._selected_id = item_id
        for row in range(self._list.count()):
            if self._list.item(row).data(256) == item_id:
                self._list.setCurrentRow(row)
                break
        item = self._items.get(item_id)
        if item:
            self._name_input.setText(str(item.get("name") or ""))
            self._content_input.setPlainText(str(item.get("content") or ""))

    def _on_row_changed(self, row: int) -> None:
        if row < 0:
            return
        self._creating = False
        item_id = str(self._list.item(row).data(256) or "")
        self._selected_id = item_id
        item = self._items.get(item_id)
        if item:
            self._name_input.setText(str(item.get("name") or ""))
            self._content_input.setPlainText(str(item.get("content") or ""))
        self._refresh_editor_state()
        if item_id:
            self.default_requested.emit(item_id)

    def _start_create(self) -> None:
        self._creating = True
        self._selected_id = ""
        self._list.clearSelection()
        self._name_input.clear()
        self._content_input.clear()
        self._name_input.setFocus()
        self._refresh_editor_state()

    def _refresh_editor_state(self) -> None:
        has_editor = self._creating or bool(self._selected_id)
        self._new_btn.setEnabled(self._actions_enabled)
        self._save_btn.setEnabled(self._actions_enabled and has_editor)
        self._delete_btn.setEnabled(self._actions_enabled and bool(self._selected_id) and not self._creating)
        self._empty_note.setVisible(not has_editor and not self._list.count())
        self._name_input.setEnabled(self._actions_enabled and (has_editor or self._creating))
        self._content_input.setEnabled(self._actions_enabled and (has_editor or self._creating))

    def draft(self) -> tuple[str, str, str, bool]:
        return (
            self._selected_id,
            self._name_input.text().strip(),
            self._content_input.toPlainText().strip(),
            self._creating,
        )
