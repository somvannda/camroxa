# Implementation Plan: Project Structure Cleanup

## Overview

This plan modernizes the MusicGenerator `python_app/` packaging, removes stale artifacts, enforces clean layer boundaries between `features/` and `views/`, decouples the `YouTubeCoordinator` from PyQt6, and standardizes feature sub-package exports. Each task builds incrementally, with earlier tasks establishing infrastructure that later tasks depend on.

## Tasks

- [x] 1. Add pyproject.toml with full dependency management
  - [x] 1.1 Create `python_app/pyproject.toml` with project metadata, build-system, dependencies, optional-dependencies, entry point, pytest, and mypy configuration
    - Declare `name = "music-generator"`, `version = "1.0.0"`, `description`, `requires-python = ">=3.11"`, `license`
    - Declare `[build-system]` with `setuptools>=68.0` backend
    - List all runtime dependencies with exact version pins: PyQt6, psutil, moderngl, google-auth, google-auth-oauthlib, google-api-python-client (pin versions from current environment)
    - Add `[project.optional-dependencies]` for "dev" (pytest, hypothesis, mypy, ruff, pytest-qt) and "test" (pytest, hypothesis, pytest-qt)
    - Add `[project.scripts]` entry: `music-generator = "python_app.app.bootstrap:run"`
    - Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `pythonpath = ["."]`
    - Add `[tool.mypy]` with `strict = true` and `python_version = "3.11"`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 1.2 Write unit tests verifying pyproject.toml field correctness
    - Parse the TOML file and assert all required fields are present
    - Verify dependency pins format and required packages
    - Verify entry point, testpaths, mypy config
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 2. Clean stale artifacts
  - [x] 2.1 Remove the `python_app/tools/` directory and all contained files
    - Delete `extract_components.py`, `extract_views.py`, `refactor_imports.py`, `remove_components.py`, `remove_methods.py`, `__init__.py`
    - _Requirements: 2.2_

  - [x] 2.2 Remove the duplicate `python_app/SLAI-IMG.json` file
    - Verify the repository-root `SLAI-IMG.json` exists before deleting the duplicate
    - _Requirements: 2.3_

  - [x] 2.3 Remove temp files matching `**/video_templates_local.json.*.tmp` under `python_app/`
    - Use glob to find and delete all matching temp files
    - _Requirements: 2.4_

  - [x] 2.4 Remove orphaned `__pycache__/` directories under `python_app/`
    - A `__pycache__/` is orphaned when every `.pyc` inside lacks a corresponding `.py` source in the parent directory
    - Implement the identification logic from the design
    - _Requirements: 2.1_

  - [x] 2.5 Verify `.gitignore` contains `**/__pycache__/` and `*.py[cod]` patterns
    - Read and assert patterns are present; no modification needed
    - _Requirements: 2.5_

  - [ ]* 2.6 Write property test for orphaned cache directory identification
    - **Property 1: Orphaned cache directory identification**
    - Generate random directory structures with varying `.py`/`.pyc` combinations
    - Verify the cleanup predicate correctly identifies orphaned directories and preserves non-orphaned ones
    - **Validates: Requirements 2.1**

- [x] 3. Checkpoint - Verify test suite after artifact cleanup
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Move view mixins from feature layer to view layer
  - [x] 4.1 Delete `features/progress/view.py` and remove any re-export of the View_Mixin from `features/progress/__init__.py`
    - The canonical definition must remain in `views/progress_view.py`
    - _Requirements: 3.1_

  - [x] 4.2 Delete `features/video_export/view.py` and remove any re-export of the View_Mixin from `features/video_export/__init__.py`
    - The canonical definition must remain in `views/video_view.py`
    - _Requirements: 3.2_

  - [x] 4.3 Update all import statements referencing old `features/.../view` paths to import from `views/` directly
    - Use AST-based scanning to find all imports referencing `features.progress.view` or `features.video_export.view`
    - Rewrite to import from `views.progress_view` or `views.video_view`
    - Verify each modified file passes `ast.parse()` after rewriting
    - _Requirements: 3.3_

  - [x] 4.4 Verify no `view.py` module exists in any sub-package of the Feature_Layer
    - Scan all `features/*/` directories and assert no `view.py` file remains
    - _Requirements: 3.6_

  - [ ]* 4.5 Write property test for import rewriting correctness
    - **Property 2: Import rewriting preserves valid Python**
    - Generate random Python source strings containing feature-view imports
    - Verify rewriting produces parseable Python with correct new import paths
    - **Validates: Requirements 3.3**

- [x] 5. Checkpoint - Verify architecture tests pass after view mixin relocation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Remove direct PyQt6 imports from YouTubeCoordinator
  - [x] 6.1 Define `TimerHandle` protocol and `UIInteractionPort` protocol in `features/ports.py`
    - Add `TimerHandle` with `start()`, `stop()`, and `is_active() -> bool` methods
    - Add type aliases or protocol for `confirm_fn`, `input_fn`, and `timer_factory` signatures
    - _Requirements: 4.4_

  - [x] 6.2 Create Qt-side adapter `views/helpers/qt_ui_adapter.py`
    - Implement `QtTimerHandle` wrapping `QTimer`
    - Implement `make_confirm_fn(parent)` wrapping `QMessageBox.warning`
    - Implement `make_input_fn(parent)` wrapping `QInputDialog.getItem`
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 6.3 Refactor `YouTubeCoordinator.__init__` to accept `confirm_fn`, `input_fn`, and `timer_factory` as injected callables
    - Remove all `PyQt6` imports from `features/youtube/coordinator.py`
    - Replace `QMessageBox.warning`/`QMessageBox.information` calls with `self._confirm(title, msg)`
    - Replace `QInputDialog.getItem` calls with `self._input(title, label, items, current)`
    - Replace `QTimer` usage with `self._timer_factory(interval_ms, callback)` returning a `TimerHandle`
    - Provide no-op fallbacks when callables are `None`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 6.4 Update the call site that instantiates `YouTubeCoordinator` to pass Qt adapters
    - Wire `make_confirm_fn`, `make_input_fn`, and `QtTimerHandle`-based timer_factory at coordinator construction
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 6.5 Add `PyQt6` to the forbidden imports set for `features/` in `tests/test_architecture.py`
    - Update the architecture test to forbid `features/` from importing `PyQt6` directly
    - _Requirements: 4.6_

  - [ ]* 6.6 Write property test for confirm_fn invocation
    - **Property 3: confirm_fn replaces all QMessageBox calls**
    - Verify coordinator calls injected `confirm_fn` with `(title: str, message: str)` and never references `QMessageBox`
    - **Validates: Requirements 4.2**

  - [ ]* 6.7 Write property test for input_fn invocation
    - **Property 4: input_fn replaces all QInputDialog calls**
    - Generate random channel lists and verify `input_fn` is called with correct arguments
    - **Validates: Requirements 4.3**

  - [ ]* 6.8 Write property test for timer_factory usage
    - **Property 5: timer_factory replaces all QTimer usage**
    - Generate random interval/callback pairs and verify `timer_factory` is used and `TimerHandle` methods are called
    - **Validates: Requirements 4.4**

  - [ ]* 6.9 Write unit test for YouTubeCoordinator instantiation without PyQt6
    - Instantiate coordinator with mock `confirm_fn`, `input_fn`, `timer_factory`
    - Verify no import errors or QApplication dependency
    - _Requirements: 4.5_

- [x] 7. Checkpoint - Verify all tests pass after YouTubeCoordinator decoupling
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Standardize feature sub-package exports
  - [x] 8.1 Update `features/auto_video/__init__.py` to export `AutoVideoCoordinator`
    - Import and re-export the coordinator class
    - _Requirements: 5.1_

  - [x] 8.2 Ensure every feature sub-package with `coordinator.py` exports its `*Coordinator` class from `__init__.py`
    - Audit and fix: `image`, `merge`, `text_presets`, `video_workspace`, and any others missing exports
    - Sub-packages without `coordinator.py` must export at least one public class
    - _Requirements: 5.2_

  - [x] 8.3 Update `features/__init__.py` to re-export at least one public symbol from every sub-package
    - Add imports for `auto_video`, `image`, `merge`, `text_presets`, `video_workspace`, and any others not currently re-exported
    - Ensure all 14 sub-packages are covered: `auto_video`, `image`, `image_prompts`, `merge`, `music`, `persistence`, `profiles`, `progress`, `templates`, `text_presets`, `video_export`, `video_workspace`, `youtube`
    - _Requirements: 5.3_

  - [x] 8.4 Add export-consistency test to verify the convention dynamically
    - Write a test that scans all sub-packages under `features/` and asserts each exports at least one public symbol
    - Assert `features/__init__.py` re-exports at least one symbol from each sub-package
    - Integrate into `tests/test_architecture.py` or create `tests/test_feature_exports.py`
    - _Requirements: 5.4_

  - [ ]* 8.5 Write property test for feature export consistency
    - **Property 6: Feature export consistency**
    - Verify that for any feature sub-package with `coordinator.py`, its `__init__.py` exports at least one `*Coordinator` class
    - Verify top-level `features/__init__.py` imports at least one symbol from each sub-package
    - **Validates: Requirements 5.2, 5.3**

- [x] 9. Final checkpoint - Verify full test suite passes
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major phase
- Property tests validate universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- The project uses Python 3.11+, pytest, and hypothesis for testing
- All code changes target the `python_app/` directory

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "2.2", "2.3", "2.4", "2.5"] },
    { "id": 1, "tasks": ["1.2", "2.6"] },
    { "id": 2, "tasks": ["4.1", "4.2"] },
    { "id": 3, "tasks": ["4.3", "4.4"] },
    { "id": 4, "tasks": ["4.5", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3"] },
    { "id": 6, "tasks": ["6.4", "6.5"] },
    { "id": 7, "tasks": ["6.6", "6.7", "6.8", "6.9"] },
    { "id": 8, "tasks": ["8.1", "8.2"] },
    { "id": 9, "tasks": ["8.3"] },
    { "id": 10, "tasks": ["8.4", "8.5"] }
  ]
}
```
