# Requirements Document

## Introduction

This spec covers the complete decoupling of all remaining `features/` modules from direct PyQt6 imports. The project already established the pattern by decoupling `features/youtube/coordinator.py` using injected callables and protocols defined in `features/ports.py`. Nine files remain on the temporary allowlist in `test_architecture.py`. After this work is complete, the `_FORBIDDEN_IMPORT_ALLOWLIST` entries for PyQt6 violations will be removed, and the architecture test will fully enforce the "no PyQt6 in features/" rule.

The decoupling strategy uses two approaches based on file responsibility:
- **Page controllers** (files that directly construct/manipulate widgets) are relocated to `views/` since they ARE view-layer code.
- **Coordinators and management modules** (files with business logic that incidentally use Qt types) are refactored to accept injected callables/protocols, keeping them in `features/`.

## Glossary

- **Coordinator**: A module in `features/` that orchestrates business logic and delegates UI interaction through injected dependencies.
- **Page_Controller**: A module that directly constructs, configures, and manipulates Qt widgets — effectively view-layer code.
- **Port**: A Protocol or type alias in `features/ports.py` defining an abstract interface that coordinators depend on.
- **Adapter**: A concrete implementation in `views/helpers/` that bridges a Port to actual PyQt6 widget APIs.
- **Allowlist**: The `_FORBIDDEN_IMPORT_ALLOWLIST` dict in `test_architecture.py` that temporarily exempts specific files from the PyQt6 forbidden-import rule.
- **Injected_Callable**: A function parameter (e.g., `confirm_fn`, `file_dialog_fn`) passed to a coordinator at construction time, replacing direct Qt widget calls.
- **Architecture_Test**: The `test_no_forbidden_imports` test in `test_architecture.py` that enforces the dependency matrix.
- **Widget_Accessor**: A `dict[str, Callable[[], object]]` pattern used by controllers (e.g., `YouTubeOAuthController`) to access widgets without importing Qt types.

## Requirements

### Requirement 1: Relocate page controllers to views layer

**User Story:** As a developer, I want page controllers that directly manipulate widgets to live in `views/` rather than `features/`, so that the architectural boundary between business logic and UI is clear and enforceable.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/progress/progress_page_controller.py` in the Allowlist
2. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/progress/dashboard_page_controller.py` in the Allowlist
3. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/music/music_page_controller.py` in the Allowlist
4. WHEN a Page_Controller is relocated, THE relocated module SHALL preserve all existing public method signatures and behavior
5. WHEN a Page_Controller is relocated, THE import statements in all calling modules SHALL be updated to reference the new `views/` path

### Requirement 2: Decouple profiles management from PyQt6

**User Story:** As a developer, I want `features/profiles/management.py` to have no PyQt6 imports, so that profile CRUD logic is testable without a Qt application instance.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/profiles/management.py` in the Allowlist for PyQt6
2. WHEN the MusicProfileManagementCoordinator needs to display a confirmation dialog, THE Coordinator SHALL call an Injected_Callable (`confirm_fn`) instead of importing QMessageBox
3. WHEN the MusicProfileManagementCoordinator needs to create list widget items, THE Coordinator SHALL delegate to a Port callback (`list_populate_fn`) instead of importing QListWidgetItem
4. WHEN the MusicProfileManagementCoordinator needs to read checkbox state, THE Coordinator SHALL receive boolean values through a Port callback instead of importing Qt.CheckState
5. WHEN the MusicProfileManagementCoordinator needs to work with dates, THE Coordinator SHALL use Python standard library datetime types instead of importing QDate

### Requirement 3: Decouple progress coordinator from PyQt6

**User Story:** As a developer, I want `features/progress/coordinator.py` to have no PyQt6 imports, so that progress orchestration logic can be tested without a running Qt event loop.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/progress/coordinator.py` in the Allowlist for PyQt6
2. WHEN the ProgressCoordinator needs to create table widget items, THE Coordinator SHALL delegate to a Port callback (`table_item_factory`) instead of importing QTableWidgetItem
3. WHEN the ProgressCoordinator needs to show a confirmation dialog, THE Coordinator SHALL call an Injected_Callable (`confirm_fn`) instead of importing QMessageBox
4. WHEN the ProgressCoordinator needs to show a progress dialog, THE Coordinator SHALL call an Injected_Callable (`progress_dialog_fn`) instead of importing QProgressDialog
5. WHEN the ProgressCoordinator needs timer functionality, THE Coordinator SHALL use the existing TimerFactory Port instead of importing QTimer
6. WHEN the ProgressCoordinator needs to process application events, THE Coordinator SHALL call an Injected_Callable (`process_events_fn`) instead of importing QApplication

### Requirement 4: Decouple music settings from PyQt6

**User Story:** As a developer, I want `features/music/settings.py` to have no PyQt6 imports, so that settings gathering and population logic is testable in isolation.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/music/settings.py` in the Allowlist for PyQt6
2. WHEN the MusicSettingsCoordinator needs to create table widget items, THE Coordinator SHALL delegate to a Port callback instead of importing QTableWidgetItem
3. WHEN the MusicSettingsCoordinator needs Qt enum values, THE Coordinator SHALL use plain Python constants or Port abstractions instead of importing Qt

### Requirement 5: Decouple video export workspace from PyQt6

**User Story:** As a developer, I want `features/video_export/workspace.py` to have no PyQt6 imports, so that workspace state logic can be unit tested without a display server.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/video_export/workspace.py` in the Allowlist for PyQt6
2. WHEN the VideoWorkspaceStateCoordinator needs to open a file dialog, THE Coordinator SHALL call an Injected_Callable (`file_dialog_fn`) instead of importing QFileDialog
3. WHEN the VideoWorkspaceStateCoordinator needs to read list widget item data, THE Coordinator SHALL receive data through a Port callback (`list_items_fn`) instead of importing Qt.ItemDataRole

### Requirement 6: Decouple templates management from PyQt6

**User Story:** As a developer, I want `features/templates/management.py` to have no PyQt6 imports, so that template CRUD logic is testable without Qt dependencies.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/templates/management.py` in the Allowlist for PyQt6
2. WHEN the TemplateManagementCoordinator needs to show a confirmation dialog, THE Coordinator SHALL call an Injected_Callable (`confirm_fn`) instead of importing QMessageBox

### Requirement 7: Decouple YouTube OAuth controller from PyQt6

**User Story:** As a developer, I want `features/youtube/oauth_controller.py` to have no PyQt6 imports, so that OAuth CRUD and credential logic is testable without Qt.

#### Acceptance Criteria

1. WHEN the architecture test runs, THE Architecture_Test SHALL pass without `features/youtube/oauth_controller.py` in the Allowlist for PyQt6
2. WHEN the YouTubeOAuthController needs to create table items, THE Controller SHALL delegate to a Port callback instead of importing QTableWidgetItem
3. WHEN the YouTubeOAuthController needs to show a warning dialog, THE Controller SHALL call an Injected_Callable (`warning_fn`) instead of importing QMessageBox
4. WHEN the YouTubeOAuthController needs Qt enum values for item data roles, THE Controller SHALL use plain string keys or Port abstractions instead of importing Qt

### Requirement 8: Extend ports and adapters infrastructure

**User Story:** As a developer, I want the shared protocol definitions in `features/ports.py` extended with new Port types, so that all decoupled coordinators have well-typed injectable interfaces.

#### Acceptance Criteria

1. WHEN a Coordinator requires a confirmation dialog, THE `features/ports.py` module SHALL export a `ConfirmQuestionFn` type alias with signature `(title: str, message: str) -> bool`
2. WHEN a Coordinator requires a file open dialog, THE `features/ports.py` module SHALL export a `FileDialogFn` type alias with appropriate signature
3. WHEN a Coordinator requires a directory selection dialog, THE `features/ports.py` module SHALL export a `DirDialogFn` type alias with appropriate signature
4. WHEN a Coordinator requires table population, THE `features/ports.py` module SHALL export a `TablePopulateFn` Protocol or type alias
5. WHEN new Port types are added, THE `views/helpers/qt_ui_adapter.py` module SHALL provide concrete Qt-based Adapter implementations for each new Port

### Requirement 9: Remove allowlist and enforce full rule

**User Story:** As a developer, I want the `_FORBIDDEN_IMPORT_ALLOWLIST` in `test_architecture.py` to contain no PyQt6 exemptions for `features/` files, so that the architecture rule is fully enforced going forward.

#### Acceptance Criteria

1. WHEN all decoupling is complete, THE Architecture_Test SHALL pass with all PyQt6 entries removed from the Allowlist
2. WHEN the architecture test runs after cleanup, THE Architecture_Test SHALL detect any new PyQt6 import in `features/` as a test failure
3. IF a developer adds a new PyQt6 import to any file under `features/`, THEN THE Architecture_Test SHALL fail with a clear violation message

### Requirement 10: Preserve runtime behavior

**User Story:** As a user, I want the application to behave identically after the refactoring, so that no functionality is lost or broken during the decoupling work.

#### Acceptance Criteria

1. THE refactored modules SHALL preserve all existing public method signatures without breaking changes
2. WHEN a Coordinator method is called through the new injected interface, THE Coordinator SHALL produce the same observable side effects as the original PyQt6-coupled implementation
3. WHEN Page_Controllers are relocated to `views/`, THE relocated modules SHALL maintain identical widget manipulation behavior
