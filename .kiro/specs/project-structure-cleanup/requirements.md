# Requirements Document

## Introduction

This specification defines the structural cleanup and modernization of the MusicGenerator Python desktop application (`python_app/`). The application is a PyQt6-based music generation, video export, and YouTube upload tool currently transitioning from a monolithic MainWindow architecture toward coordinators with dependency injection. These requirements address packaging, stale artifacts, layer violations, UI coupling in coordinators, and inconsistent feature exports — all aimed at enforcing clean layering, reproducible builds, and consistent conventions across the 14 feature sub-packages.

## Glossary

- **Build_System**: The `pyproject.toml` configuration file that declares project metadata, dependencies, tool settings, and entry points for the python_app package.
- **Stale_Artifact**: A file that no longer serves a purpose in the current codebase — including orphaned `.pyc` files, one-off refactoring scripts, duplicate configuration files, and temporary files left by interrupted processes.
- **Cleanup_Tool**: The automated or manual process that identifies and removes Stale_Artifacts from the repository.
- **View_Layer**: The `views/` package responsible for all UI widget construction, layout, and rendering via PyQt6.
- **Feature_Layer**: The `features/` package containing domain-logic coordinators that must not directly construct or own UI widgets.
- **View_Mixin**: A mixin class that constructs PyQt6 widgets and belongs in the View_Layer, not in the Feature_Layer.
- **YouTubeCoordinator**: The coordinator class at `features/youtube/coordinator.py` that orchestrates YouTube upload workflows.
- **UI_Interaction_Protocol**: A set of callable parameters (e.g., `confirm_fn`, `input_fn`, `timer_factory`) injected into a coordinator to mediate user interaction without direct PyQt6 imports.
- **Feature_Export**: The public API of a feature sub-package, declared via its `__init__.py` module.
- **Architecture_Test**: The existing `tests/test_architecture.py` suite that enforces import boundary rules between packages.
- **Coordinator**: A class that owns domain orchestration logic for a feature, receiving dependencies via constructor injection.

## Requirements

### Requirement 1: Add pyproject.toml with Full Dependency Management

**User Story:** As a developer, I want a single `pyproject.toml` file that declares all project dependencies, tool configurations, and entry points, so that I can reproducibly install, build, and develop the application.

#### Acceptance Criteria

1. THE Build_System SHALL declare the project name, version, description, Python version constraint (`requires-python = ">=3.11"`), and license in the `[project]` table, and SHALL specify a `[build-system]` table declaring the build backend and its requirements.
2. THE Build_System SHALL list all runtime dependencies in the `[project.dependencies]` array using exact version pins (e.g., `package==X.Y.Z`), including PyQt6, psutil, moderngl, google-auth, google-auth-oauthlib, and google-api-python-client.
3. THE Build_System SHALL declare optional dependency groups `[project.optional-dependencies]` for "dev" (pytest, hypothesis, mypy, ruff, pytest-qt) and "test" (pytest, hypothesis, pytest-qt).
4. THE Build_System SHALL define a `[project.scripts]` entry point named "music-generator" that invokes `python_app.app.bootstrap:run`.
5. THE Build_System SHALL include a `[tool.pytest.ini_options]` section specifying `testpaths = ["tests"]` and `pythonpath = ["."]`.
6. THE Build_System SHALL include a `[tool.mypy]` section with `strict = true` and `python_version = "3.11"`.
7. WHEN `pip install -e .` is executed in the `python_app/` directory, THE Build_System SHALL install all runtime dependencies listed in criterion 2 and register the "music-generator" console script such that running `music-generator` on the command line invokes `python_app.app.bootstrap:run`.
8. WHEN `pip install -e ".[dev]"` is executed in the `python_app/` directory, THE Build_System SHALL install all runtime dependencies plus all packages listed in the "dev" optional dependency group.

### Requirement 2: Clean Stale Artifacts

**User Story:** As a developer, I want orphaned build artifacts, one-off scripts, duplicate files, and temporary files removed from the repository, so that the working tree contains only meaningful, referenced code.

#### Acceptance Criteria

1. THE Cleanup_Tool SHALL remove all `__pycache__/` directories (and their contents) under `python_app/` whose parent directory no longer contains the corresponding `.py` source file for at least one `.pyc` entry within.
2. THE Cleanup_Tool SHALL remove the `python_app/tools/` directory and all contained files (`extract_components.py`, `extract_views.py`, `refactor_imports.py`, `remove_components.py`, `remove_methods.py`, `__init__.py`).
3. THE Cleanup_Tool SHALL remove the duplicate `python_app/SLAI-IMG.json` file while preserving the copy at the repository root (`SLAI-IMG.json`).
4. THE Cleanup_Tool SHALL remove all files under `python_app/` matching the glob pattern `**/video_templates_local.json.*.tmp`.
5. THE Cleanup_Tool SHALL verify that the project `.gitignore` already contains `**/__pycache__/` and `*.py[cod]` patterns (both are present); no modification to `.gitignore` is required.
6. WHEN the Cleanup_Tool completes, THE Architecture_Test suite SHALL pass with zero failures and the full test suite SHALL produce no new failures.

### Requirement 3: Move View Mixins from Feature Layer to View Layer

**User Story:** As a developer, I want all UI-construction mixins consolidated in the `views/` package, so that the layering rule "views/ owns widget construction, features/ owns domain logic" is consistently enforced.

#### Acceptance Criteria

1. WHEN the `features/progress/view.py` module contains or re-exports a View_Mixin class, THE Feature_Layer SHALL delete that module file and remove any re-export of that View_Mixin from `features/progress/__init__.py`, leaving the canonical definition in `views/progress_view.py`.
2. WHEN the `features/video_export/view.py` module contains or re-exports a View_Mixin class, THE Feature_Layer SHALL delete that module file and remove any re-export of that View_Mixin from `features/video_export/__init__.py`, leaving the canonical definition in `views/video_view.py`.
3. WHEN a View_Mixin is relocated, all Python import statements (detected via AST parsing) across the codebase that referenced the old `features/.../view` path SHALL be updated to import directly from the corresponding module in the View_Layer.
4. WHEN the relocation is complete, THE Architecture_Test suite SHALL pass with zero failures, confirming no forbidden cross-layer imports exist.
5. WHEN the relocation is complete, THE full test suite SHALL pass with zero failures without modification to test assertions or test logic (only import paths may change).
6. WHEN the relocation is complete, no `view.py` module SHALL exist in any sub-package of the Feature_Layer.

### Requirement 4: Remove Direct PyQt6 Imports from YouTubeCoordinator

**User Story:** As a developer, I want the YouTubeCoordinator to receive UI interaction capabilities through injected callables rather than importing PyQt6 directly, so that the coordinator follows the dependency-injection pattern used by other coordinators and remains testable without a running Qt event loop.

#### Acceptance Criteria

1. THE YouTubeCoordinator SHALL NOT contain any import statement referencing `PyQt6.QtCore`, `PyQt6.QtWidgets`, or any other `PyQt6` sub-module.
2. WHEN the YouTubeCoordinator requires user confirmation (currently `QMessageBox.warning` or `QMessageBox.information`), THE YouTubeCoordinator SHALL invoke an injected callable with signature `confirm_fn(title: str, message: str) -> None` provided via its constructor or host protocol.
3. WHEN the YouTubeCoordinator requires text input from the user (currently `QInputDialog.getItem`), THE YouTubeCoordinator SHALL invoke an injected callable with signature `input_fn(title: str, label: str, items: list[str], current: int) -> tuple[str, bool]` provided via its constructor or host protocol.
4. WHEN the YouTubeCoordinator requires a periodic timer (currently `QTimer`), THE YouTubeCoordinator SHALL use a `timer_factory` callable with signature `timer_factory(interval_ms: int, callback: Callable[[], None]) -> TimerHandle` provided via its constructor or host protocol, where `TimerHandle` exposes `start()`, `stop()`, and `is_active() -> bool` methods.
5. WHEN the YouTubeCoordinator is instantiated in tests without PyQt6, THE YouTubeCoordinator SHALL accept mock implementations of `confirm_fn`, `input_fn`, and `timer_factory` and operate without raising import errors or requiring a QApplication instance.
6. WHEN the refactoring is complete, THE Architecture_Test suite SHALL pass with zero failures and a new architecture rule SHALL forbid `features/` from importing `PyQt6` directly.

### Requirement 5: Standardize Feature Sub-Package Exports

**User Story:** As a developer, I want every feature sub-package to export its primary coordinator via `__init__.py`, so that feature discovery and application wiring follow a single consistent pattern.

#### Acceptance Criteria

1. THE Feature_Layer `features/auto_video/__init__.py` module SHALL export the `AutoVideoCoordinator` class from `features/auto_video/coordinator.py`.
2. FOR EACH feature sub-package under `features/` that contains a module named `coordinator.py`, THE sub-package `__init__.py` SHALL export at least one class whose name ends with `Coordinator`. FOR EACH feature sub-package that does not contain a `coordinator.py` module, THE sub-package `__init__.py` SHALL export at least one public class (a class whose name does not start with an underscore).
3. THE top-level `features/__init__.py` SHALL import and re-export at least one public symbol from every immediate sub-package directory that contains an `__init__.py`, including `auto_video`, `image`, `image_prompts`, `merge`, `music`, `persistence`, `profiles`, `progress`, `templates`, `text_presets`, `video_export`, `video_workspace`, and `youtube`.
4. WHEN a new feature sub-package directory containing an `__init__.py` is added under `features/`, THE Architecture_Test or a dedicated export-consistency test SHALL verify that the sub-package `__init__.py` exports at least one public symbol (a name listed in `__all__` or importable without underscore prefix) and that the top-level `features/__init__.py` re-exports at least one symbol from the new sub-package.
5. WHEN the standardization is complete, THE existing test suite SHALL pass with zero test failures and zero new import errors when running the full test suite.
