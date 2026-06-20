# Implementation Plan: Features PyQt6 Decoupling

## Overview

Incrementally remove all PyQt6 imports from the `features/` layer by relocating page controllers to `views/` and refactoring coordinators to use injected callables. Each module is addressed independently with its own verification step (removing its allowlist entry and running the architecture test). The final task removes any remaining allowlist entries and confirms full enforcement.

## Tasks

- [x] 1. Extend ports and adapters infrastructure
  - [x] 1.1 Add new Port type aliases to `features/ports.py`
    - Add `ConfirmQuestionFn = Callable[[str, str], bool]`
    - Add `WarningFn = Callable[[str, str], None]` (rename existing `ConfirmFn` usage or keep both — existing one is fire-and-forget)
    - Add `FileDialogFn = Callable[[str, str], str]`
    - Add `DirDialogFn = Callable[[str, str], str]`
    - Add `TablePopulateFn = Callable[[list[list[tuple[int, str, str]]]], None]`
    - Add `ListItemsFn = Callable[[], list[tuple[str, str]]]`
    - Add `ListPopulateFn = Callable[[list[tuple[str, str]]], None]`
    - Add `ListSelectedItemsFn = Callable[[], list[str]]`
    - Add `ProcessEventsFn = Callable[[], None]`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.2 Add new adapter factories to `views/helpers/qt_ui_adapter.py`
    - Implement `make_confirm_question_fn(parent)` → wraps `QMessageBox.question`, returns `bool`
    - Implement `make_warning_fn(parent)` → wraps `QMessageBox.warning`
    - Implement `make_file_dialog_fn(parent)` → wraps `QFileDialog.getOpenFileName`
    - Implement `make_dir_dialog_fn(parent)` → wraps `QFileDialog.getExistingDirectory`
    - Implement `make_table_populate_fn(table_widget)` → creates QTableWidgetItem rows
    - Implement `make_list_items_fn(list_widget)` → reads (text, data) pairs from QListWidget
    - Implement `make_list_populate_fn(list_widget)` → populates QListWidget
    - Implement `make_process_events_fn()` → wraps `QApplication.processEvents`
    - _Requirements: 8.5_

  - [ ]* 1.3 Write unit tests for new port types and adapter factories
    - Verify each type alias exists in `features/ports.py` with correct signature
    - Verify each adapter factory returns callable with expected signature
    - Test `make_confirm_question_fn` returns `bool` (mock QMessageBox)
    - Test `make_table_populate_fn` creates correct items (mock QTableWidget)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 2. Relocate page controllers to views layer
  - [x] 2.1 Relocate `features/progress/progress_page_controller.py` to `views/progress_page_controller.py`
    - Move file to `views/progress_page_controller.py`
    - Update all import statements across the codebase to reference `views.progress_page_controller`
    - Remove `features/progress/progress_page_controller.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 1.1, 1.4, 1.5_

  - [x] 2.2 Relocate `features/progress/dashboard_page_controller.py` to `views/dashboard_page_controller.py`
    - Move file to `views/dashboard_page_controller.py`
    - Update all import statements across the codebase to reference `views.dashboard_page_controller`
    - Remove `features/progress/dashboard_page_controller.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 1.2, 1.4, 1.5_

  - [x] 2.3 Relocate `features/music/music_page_controller.py` to `views/music_page_controller.py`
    - Move file to `views/music_page_controller.py`
    - Update all import statements across the codebase to reference `views.music_page_controller`
    - Remove `features/music/music_page_controller.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 1.3, 1.4, 1.5_

- [x] 3. Checkpoint - Verify page controller relocations
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Decouple templates/management.py from PyQt6
  - [x] 4.1 Refactor `features/templates/management.py` to use injected `confirm_question_fn`
    - Add `confirm_question_fn: ConfirmQuestionFn | None = None` constructor parameter
    - Replace `QMessageBox.question` call in `delete_current_template()` with `self.confirm_question_fn(title, msg)` call
    - Add no-op fallback: if `confirm_question_fn is None`, default to `False` (don't proceed)
    - Remove PyQt6 imports from the file
    - Remove `features/templates/management.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 6.1, 6.2, 10.1, 10.2_

  - [ ]* 4.2 Write unit test for templates/management.py decoupling
    - Test `delete_current_template()` calls `confirm_question_fn` with correct args
    - Test that when `confirm_question_fn` returns `False`, deletion does not proceed
    - Test that when `confirm_question_fn is None`, method returns without action
    - _Requirements: 6.1, 6.2_

- [x] 5. Decouple music/settings.py from PyQt6
  - [x] 5.1 Refactor `features/music/settings.py` to use injected `table_populate_fn`
    - Add `table_populate_fn: TablePopulateFn | None = None` constructor parameter
    - Replace `QTableWidgetItem` + `Qt.ItemDataRole.UserRole` creation in `refresh_music_pool_table()` with `table_populate_fn(rows)` call
    - Add no-op fallback: if `table_populate_fn is None`, method is a no-op
    - Remove PyQt6 imports from the file
    - Remove `features/music/settings.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 4.1, 4.2, 4.3, 10.1, 10.2_

  - [ ]* 5.2 Write unit test for music/settings.py decoupling
    - Test `refresh_music_pool_table()` calls `table_populate_fn` with correctly structured rows
    - Test that `table_populate_fn is None` results in a no-op
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 6. Decouple video_export/workspace.py from PyQt6
  - [x] 6.1 Refactor `features/video_export/workspace.py` to use injected callables
    - Add `file_dialog_fn: FileDialogFn | None = None` constructor parameter
    - Add `dir_dialog_fn: DirDialogFn | None = None` constructor parameter
    - Add `list_items_fn: ListItemsFn | None = None` constructor parameter
    - Replace `QFileDialog.getOpenFileName` in `pick_ffmpeg()` with `file_dialog_fn(title, filter)` call
    - Replace `QFileDialog.getExistingDirectory` in `prompt_output_dir_for_export()` with `dir_dialog_fn(title, default)` call
    - Replace `Qt.ItemDataRole.UserRole` reads in `iter_mp3_paths()` and `current_selected_mp3_path()` with `list_items_fn()` call
    - Add no-op fallbacks: `file_dialog_fn`/`dir_dialog_fn` return `""`, `list_items_fn` returns `[]`
    - Remove PyQt6 imports from the file
    - Remove `features/video_export/workspace.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 5.1, 5.2, 5.3, 10.1, 10.2_

  - [ ]* 6.2 Write unit test for video_export/workspace.py decoupling
    - Test `pick_ffmpeg()` calls `file_dialog_fn` and uses returned path
    - Test `prompt_output_dir_for_export()` calls `dir_dialog_fn`
    - Test `iter_mp3_paths()` delegates to `list_items_fn` and returns paths correctly
    - Test no-op fallbacks when callables are None
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 7. Checkpoint - Verify simple module decouplings
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Decouple youtube/oauth_controller.py from PyQt6
  - [x] 8.1 Refactor `features/youtube/oauth_controller.py` to use injected callables
    - Add `warning_fn: WarningFn | None = None` constructor parameter
    - Add `confirm_question_fn: ConfirmQuestionFn | None = None` constructor parameter
    - Add `table_populate_fn: TablePopulateFn | None = None` constructor parameter
    - Replace `QMessageBox.warning` calls with `warning_fn(title, msg)`
    - Replace `QMessageBox.question` calls with `confirm_question_fn(title, msg)`
    - Replace `QTableWidgetItem` + `Qt.ItemDataRole.UserRole` in `refresh_youtube_oauth_apps_table()` with `table_populate_fn(rows)`
    - Add no-op fallbacks for all None callables
    - Remove PyQt6 imports from the file
    - Remove `features/youtube/oauth_controller.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 10.1, 10.2_

  - [ ]* 8.2 Write unit test for youtube/oauth_controller.py decoupling
    - Test `refresh_youtube_oauth_apps_table()` calls `table_populate_fn` with correct row data
    - Test CRUD methods call `warning_fn` / `confirm_question_fn` with expected arguments
    - Test no-op fallbacks
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 9. Decouple profiles/management.py from PyQt6
  - [x] 9.1 Refactor `features/profiles/management.py` to use injected callables
    - Add `confirm_question_fn: ConfirmQuestionFn | None = None` constructor parameter
    - Add `warning_fn: WarningFn | None = None` constructor parameter
    - Add `list_populate_fn: ListPopulateFn | None = None` constructor parameter
    - Replace `QListWidgetItem` + `Qt.ItemDataRole.UserRole` in `refresh_list()` with `list_populate_fn(items)` call
    - Replace `Qt.CheckState` reads in `_refresh_profile_image_random()` and `save_profile_details()` with Python `bool` values received through widget accessor callables
    - Replace `QDate` usage in `_refresh_profile_youtube_publish_date()` with Python `datetime.date`
    - Replace `QMessageBox` calls with `confirm_question_fn` / `warning_fn`
    - Add no-op fallbacks for all None callables
    - Remove PyQt6 imports from the file
    - Remove `features/profiles/management.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 10.1, 10.2_

  - [ ]* 9.2 Write unit test for profiles/management.py decoupling
    - Test `refresh_list()` calls `list_populate_fn` with (display_text, user_role_data) tuples
    - Test save/create/delete methods call `confirm_question_fn` and respect its return value
    - Test date handling uses Python `datetime.date` instead of QDate
    - Test checkbox state uses Python `bool` instead of Qt.CheckState
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 10. Decouple progress/coordinator.py from PyQt6
  - [x] 10.1 Refactor `features/progress/coordinator.py` to use injected callables
    - Add `confirm_question_fn: ConfirmQuestionFn | None = None` constructor parameter
    - Add `warning_fn: WarningFn | None = None` constructor parameter
    - Add `table_populate_fn: TablePopulateFn | None = None` constructor parameter
    - Add `process_events_fn: ProcessEventsFn | None = None` constructor parameter
    - Replace `QTableWidgetItem` + `Qt.ItemDataRole.UserRole` + `Qt.AlignmentFlag` in `apply_rows()`, `mark_visible_rows_cancelling()` with `table_populate_fn(rows)` call
    - Replace `QMessageBox` calls in `cancel_row()` and other action methods with `confirm_question_fn` / `warning_fn`
    - Replace `QApplication.processEvents` calls with `process_events_fn()` (no-op if None)
    - Ensure all timer usage goes through existing `TimerFactory` port
    - Add no-op fallbacks for all None callables
    - Remove PyQt6 imports from the file
    - Remove `features/progress/coordinator.py` entry (`PyQt6` key) from `_FORBIDDEN_IMPORT_ALLOWLIST`
    - Run architecture test to verify it passes
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 10.1, 10.2_

  - [ ]* 10.2 Write unit test for progress/coordinator.py decoupling
    - Test `apply_rows()` calls `table_populate_fn` with correctly structured data
    - Test `cancel_row()` calls `confirm_question_fn` and respects its return value
    - Test `process_events_fn` is called at appropriate points
    - Test no-op fallbacks when callables are None
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 11. Checkpoint - Verify all coordinator decouplings
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Wire adapters at construction sites and final enforcement
  - [x] 12.1 Update coordinator construction sites to pass adapter callables
    - In `main_window.py` or relevant view files, pass `make_confirm_question_fn(self)`, `make_warning_fn(self)`, etc. when constructing each coordinator
    - Wire `make_table_populate_fn(table_widget)` for coordinators that need it
    - Wire `make_file_dialog_fn(self)` and `make_dir_dialog_fn(self)` for workspace coordinator
    - Wire `make_list_items_fn(list_widget)` and `make_list_populate_fn(list_widget)` where needed
    - Wire `make_process_events_fn()` for progress coordinator
    - _Requirements: 8.5, 10.2, 10.3_

  - [x] 12.2 Remove all remaining PyQt6 allowlist entries and verify full enforcement
    - Remove any remaining PyQt6 entries from `_FORBIDDEN_IMPORT_ALLOWLIST` in `test_architecture.py`
    - Run `pytest tests/test_architecture.py` to confirm the architecture test passes with no allowlist entries for PyQt6 in features/
    - Verify `test_no_forbidden_imports` detects any new PyQt6 import in `features/` as a failure
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 12.3 Write property-based tests for architecture enforcement and data round-trip
    - **Property 1: Architecture enforcement detects PyQt6 imports in features/**
    - **Validates: Requirements 9.2, 9.3**
    - Use hypothesis to generate file paths and import statements, verify detection
    - **Property 4: List/table data round-trip fidelity**
    - **Validates: Requirements 5.3, 7.4**
    - Use hypothesis to generate lists of `(str, str)` tuples, verify coordinator returns same data
    - _Requirements: 9.2, 9.3, 5.3, 7.4_

- [x] 13. Final checkpoint - Full test suite passes
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each module decoupling (tasks 4–10) is independent — they can be done in any order
- Each decoupling task includes removing its own allowlist entry and running the architecture test as verification
- The injection pattern follows the existing `features/youtube/coordinator.py` example: constructor params with `None` defaults and no-op fallbacks
- Property-based tests use the `hypothesis` library already configured in the project
- Page controller relocations (task 2) are simple file moves with import path updates
- Task 12 wires everything together at the end, ensuring runtime behavior is preserved

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 3, "tasks": ["4.1", "5.1", "6.1"] },
    { "id": 4, "tasks": ["4.2", "5.2", "6.2", "8.1"] },
    { "id": 5, "tasks": ["8.2", "9.1"] },
    { "id": 6, "tasks": ["9.2", "10.1"] },
    { "id": 7, "tasks": ["10.2"] },
    { "id": 8, "tasks": ["12.1"] },
    { "id": 9, "tasks": ["12.2"] },
    { "id": 10, "tasks": ["12.3"] }
  ]
}
```
