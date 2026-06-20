# Implementation Plan: Enterprise Architecture Refactor

## Overview

This plan decomposes the 12-phase migration sequence from the design into independently executable coding tasks. Each task follows the delegate-before-deleting pattern and produces a validated Refactor_Slice. Tasks that modify `main_window.py` are serialized to avoid merge conflicts. Property-based tests validate architectural invariants; unit tests verify behavioral equivalence.

## Tasks

- [ ] 1. Phase 1 — Fix the `removed` variable bug (separate slice)
  - [x] 1.1 Fix `_delete_music_saved_text` NameError
    - In `python_app/app/main_window.py`, locate `_delete_music_saved_text` and initialize `removed = []` before the conditional branch
    - Ensure both the `if` and `else` paths have `removed` defined before it is referenced
    - Run `python -m py_compile python_app/app/main_window.py` to verify
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 1.2 Write unit test for the bug fix
    - Create `python_app/tests/test_delete_saved_text_bug.py`
    - Test that calling `_delete_music_saved_text` with a condition that skips the `if` branch does not raise NameError
    - Test the happy path still returns expected results
    - _Requirements: 9.1, 9.2_

- [x] 2. Phase 2 — Relocate UI helpers to `views/helpers/`
  - [x] 2.1 Create `views/helpers/` subpackage and move modules
    - Create `python_app/views/helpers/__init__.py` with re-exports
    - Move `python_app/app/style_helper.py` → `python_app/views/helpers/style_helper.py`
    - Move `python_app/app/widget_factory.py` → `python_app/views/helpers/widget_factory.py`
    - Move `python_app/app/footer_controller.py` → `python_app/views/helpers/footer_controller.py`
    - Update internal cross-reference: `widget_factory.py` imports `style_helper` via relative import `from . import style_helper`
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 2.2 Update all import references to relocated helpers
    - Search entire codebase for `from app.style_helper`, `from app.widget_factory`, `from app.footer_controller` (and `import app.style_helper` etc.)
    - Replace with `from views.helpers.style_helper`, `from views.helpers.widget_factory`, `from views.helpers.footer_controller` respectively
    - Verify no remaining references to old paths
    - Run `python -m py_compile` on all changed files
    - _Requirements: 1.3, 1.5_

  - [ ]* 2.3 Write property test for import path migration (Property 2)
    - Create `python_app/tests/test_import_migration.py`
    - **Property 2: Import Path Migration Completeness**
    - Scan all `.py` files and assert zero imports reference `app.style_helper`, `app.widget_factory`, `app.footer_controller`, `controllers.music_controller`, or `controllers.image_controller`
    - **Validates: Requirements 1.3, 2.5**

- [x] 3. Checkpoint — Phase 1 & 2 validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `python -m py_compile` passes on all files
  - Verify app launches without import errors

- [x] 4. Phase 3 — Create coordinator skeletons with DI
  - [x] 4.1 Create shared protocol definitions
    - Create `python_app/features/ports.py` with `EventBusPort`, `LoggerPort`, `DbCfgAccessor`, `SettingsAccessor` Protocol interfaces
    - All protocols use `typing.Protocol` with proper method signatures and type annotations
    - _Requirements: 6.1, 6.2_

  - [x] 4.2 Create `MusicGenerationCoordinator` skeleton
    - Create `python_app/features/music/__init__.py`
    - Create `python_app/features/music/coordinator.py` with `MusicGenerationCoordinator` class
    - Define `MusicDbPort` and `MusicServicePort` Protocol interfaces
    - Implement `__init__` with constructor injection of all dependencies (db, service, bus, settings_accessor, db_cfg_accessor, logger)
    - Add constructor validation (raise `ValueError` for None dependencies)
    - Stub all method signatures from the design with `pass` bodies and full type annotations
    - _Requirements: 4.1, 6.1, 6.2, 6.3_

  - [x] 4.3 Create `ImageGenerationCoordinator` skeleton
    - Create `python_app/features/image/__init__.py`
    - Create `python_app/features/image/coordinator.py` with `ImageGenerationCoordinator` class
    - Define `ImageDbPort` and `ImageServicePort` Protocol interfaces
    - Implement `__init__` with constructor injection of all dependencies
    - Add constructor validation
    - Stub all method signatures from the design with `pass` bodies and full type annotations
    - _Requirements: 4.2, 6.1, 6.2, 6.3_

  - [x] 4.4 Create `VideoWorkspaceCoordinator` skeleton
    - Create `python_app/features/video_workspace/__init__.py`
    - Create `python_app/features/video_workspace/coordinator.py` with `VideoWorkspaceCoordinator` class
    - Implement `__init__` with constructor injection (template_coordinator, export_coordinator, bus, settings_accessor)
    - Stub all method signatures from the design
    - _Requirements: 4.3, 6.1, 6.2_

  - [x] 4.5 Create coordinator types in models layer
    - Create `python_app/models/coordinator_types.py` with `GenerationRequest`, `ImageJobRequest`, `PollResult` dataclasses
    - All types use `@dataclass(frozen=True)` for immutability
    - _Requirements: 4.1, 4.2_

  - [ ]* 4.6 Write property test for coordinator independence (Property 3)
    - Create `python_app/tests/test_coordinator_independence.py`
    - **Property 3: Coordinator Independence from MainWindow**
    - For each coordinator in `features/`, parse source with AST and assert: zero `self.host` references, zero `MainWindow` type annotations, instantiable with mock dependencies without `QApplication`
    - **Validates: Requirements 6.2, 6.3, 6.5**

- [x] 5. Phase 4 — Migrate controllers to feature coordinators
  - [x] 5.1 Absorb `music_controller.py` into `MusicGenerationCoordinator`
    - Copy all method bodies from `python_app/controllers/music_controller.py` into the corresponding stubs in `features/music/coordinator.py`
    - Replace all `self.host.db_cfg` with `self._db_cfg_accessor()`
    - Replace all `self.host.e_settings` with `self._settings_accessor()`
    - Replace all `self.host._log(...)` with `self._logger.info(...)`/`self._logger.error(...)`
    - Replace all `self.host.music_data` with `self._music_data` (coordinator-owned)
    - Ensure all method signatures match the original controller exactly
    - _Requirements: 2.1, 2.3, 6.5_

  - [x] 5.2 Absorb `image_controller.py` into `ImageGenerationCoordinator`
    - Copy all method bodies from `python_app/controllers/image_controller.py` into the corresponding stubs in `features/image/coordinator.py`
    - Replace all `self.host.*` references with injected dependencies
    - Ensure all method signatures match the original controller exactly
    - _Requirements: 2.2, 2.3, 6.5_

  - [x] 5.3 Update callers and remove old controller files
    - Update `main_window.py` to instantiate `MusicGenerationCoordinator` and `ImageGenerationCoordinator` instead of old controllers
    - Update all references from `self.music_controller.method()` to `self._music_coordinator.method()`
    - Update all references from `self.image_controller.method()` to `self._image_coordinator.method()`
    - Remove `python_app/controllers/music_controller.py`
    - Remove `python_app/controllers/image_controller.py`
    - Remove `python_app/controllers/` package if empty
    - Run `python -m py_compile` on all changed files
    - _Requirements: 2.4, 2.5, 2.6_

  - [ ]* 5.4 Write unit tests for coordinator behavioral equivalence
    - Create `python_app/tests/test_music_coordinator.py`
    - Create `python_app/tests/test_image_coordinator.py`
    - Test key methods (submit_song_to_suno, trigger_image_poll, etc.) with mock dependencies
    - Verify return values and side effects match original controller behavior
    - _Requirements: 2.1, 2.2, 7.4_

- [x] 6. Checkpoint — Phase 3 & 4 validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify app launches without import errors
  - Verify music generation and image generation features still work

- [x] 7. Phase 5 — Extract MainWindow music domain
  - [x] 7.1 Delegate music orchestration methods from MainWindow to MusicGenerationCoordinator
    - Identify all music-domain methods in `main_window.py` (generation clicks, history refresh, music event handling, profile management, pool operations)
    - For each method: add coordinator method implementation, then replace MainWindow body with thin delegator (1-3 lines)
    - Preserve all signal/slot connections by keeping the public method name in MainWindow
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.5, 4.6_

  - [ ]* 7.2 Write property test for thin delegator constraint (Property 4)
    - Create `python_app/tests/test_delegator_thickness.py`
    - **Property 4: Thin Delegator Constraint**
    - Parse `main_window.py` AST, identify methods that call a coordinator, assert body ≤ 3 executable statements
    - **Validates: Requirements 3.2**

- [x] 8. Phase 6 — Extract MainWindow image domain
  - [x] 8.1 Delegate image orchestration methods from MainWindow to ImageGenerationCoordinator
    - Identify all image-domain methods in `main_window.py` (generate now, generate thumbnails, refresh jobs, retry failed, poll handling)
    - For each method: add coordinator method implementation, then replace MainWindow body with thin delegator (1-3 lines)
    - Preserve all signal/slot connections by keeping the public method name in MainWindow
    - _Requirements: 3.1, 3.2, 3.3, 4.2, 4.5, 4.6_

- [x] 9. Phase 7 — Transfer timer policy to coordinators
  - [x] 9.1 Move timer start/stop decisions to feature coordinators
    - For each feature coordinator that uses timers (music polling, image polling): move the timer start/stop/interval logic into the coordinator
    - MainWindow retains only the timer attributes needed for shutdown lifecycle (`timer.stop()` in `closeEvent`)
    - Coordinator exposes `start_polling()` / `stop_polling()` methods that MainWindow calls during setup/teardown
    - Preserve existing timer intervals and polling frequencies exactly
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 10. Checkpoint — Phase 5, 6 & 7 validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `python -m py_compile` passes on all files
  - Verify music generation, image generation, and timer-based polling work correctly
  - Confirm MainWindow line count reduced by at least 2,000 lines

- [x] 11. Phase 8 — Remove `self.host` pattern from existing coordinators
  - [x] 11.1 Refactor existing coordinators to use injected dependencies
    - Audit all coordinators in `python_app/features/` (youtube, progress, persistence, profiles, templates, video_export, auto_video)
    - For each coordinator that still references `self.host`: replace with injected protocol interfaces
    - Update `main_window.py` bootstrap to pass concrete dependencies at construction time
    - Verify each coordinator is instantiable with mock dependencies in isolation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 11.2 Write integration test for coordinator instantiation
    - Create `python_app/tests/test_coordinator_instantiation.py`
    - For each coordinator class in `features/`, instantiate with mock dependencies (no QApplication)
    - Verify no ImportError, no AttributeError, no reference to MainWindow
    - _Requirements: 6.3_

- [x] 12. Phase 9 — Consolidate imports in MainWindow
  - [x] 12.1 Clean up `main_window.py` imports
    - Move all inline/method-body imports to module level
    - Remove duplicate import statements
    - Order imports per PEP 8: stdlib → third-party (PyQt6) → local application
    - Separate each group with a blank line
    - Remove unused imports left over from extracted methods
    - Run `python -m py_compile python_app/app/main_window.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 12.2 Write property test for import hygiene (Property 5)
    - Create `python_app/tests/test_import_hygiene.py`
    - **Property 5: Import Hygiene in MainWindow**
    - Parse `main_window.py` AST: assert all imports at module level, no duplicates, PEP 8 ordering
    - **Validates: Requirements 10.1, 10.2, 10.4**

- [x] 13. Phase 10 — Add type annotations
  - [x] 13.1 Add type annotations to feature coordinators
    - Annotate all public and protected methods in `features/music/coordinator.py`, `features/image/coordinator.py`, `features/video_workspace/coordinator.py`
    - Annotate all public and protected methods in existing coordinators (youtube, progress, persistence, profiles, templates, video_export, auto_video)
    - Use `from __future__ import annotations` for forward references
    - Use standard typing constructs (`Optional`, `list`, `dict`, `tuple`, `Any`, `Callable`)
    - _Requirements: 11.1, 11.2, 11.3, 11.5_

  - [x] 13.2 Add type annotations to services and database modules
    - Annotate all public and protected methods in `python_app/services/` modules
    - Annotate all public and protected methods in `python_app/database/` modules
    - Annotate all public and protected methods in `python_app/models/` modules
    - _Requirements: 11.1, 11.2, 11.3, 11.5_

  - [ ]* 13.3 Write property test for type annotation coverage (Property 6)
    - Create `python_app/tests/test_type_annotations.py`
    - **Property 6: Type Annotation Coverage**
    - Parse AST of all coordinators, services, database, and models modules; assert all public/protected methods have parameter and return type annotations
    - **Validates: Requirements 11.1, 11.2**

  - [x] 13.4 Run mypy validation
    - Run `mypy --ignore-missing-imports` on all annotated modules
    - Fix any type errors without changing method behavior
    - _Requirements: 11.4_

- [x] 14. Checkpoint — Phase 8, 9 & 10 validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `python -m py_compile` passes on all files
  - Verify app launches and all features work correctly

- [x] 15. Phase 11 — Harden visualizer boundary
  - [x] 15.1 Create visualizer DTO contracts
    - Create `python_app/visualizer/contracts.py` with `RenderRequest`, `PreviewConfig`, `RenderProgress`, `RenderResult` dataclasses
    - All DTOs use `@dataclass(frozen=True)` for immutability
    - _Requirements: 12.1, 12.3_

  - [x] 15.2 Update visualizer callers to use DTO contracts
    - Update `main_window.py` and coordinators to construct `RenderRequest`/`PreviewConfig` DTOs when calling visualizer
    - Update visualizer entry points to accept DTOs instead of raw dicts/kwargs
    - Ensure visualizer modules do not import from `app/`, `database/`, or `services/`
    - Preserve all existing rendering behavior
    - _Requirements: 12.1, 12.2, 12.4, 12.5_

  - [ ]* 15.3 Write unit tests for visualizer DTO contracts
    - Create `python_app/tests/test_visualizer_contracts.py`
    - Test DTO construction, field access, immutability (frozen)
    - Test that DTOs are importable without circular dependencies
    - _Requirements: 12.1, 12.3_

- [x] 16. Phase 12 — Enable import-lint enforcement
  - [x] 16.1 Create architecture test suite
    - Create `python_app/tests/test_architecture.py`
    - Implement `collect_imports()` using AST parsing to extract all import paths from a file
    - Implement `test_no_forbidden_imports()` covering all rules from the dependency matrix
    - Implement `test_no_cross_feature_internals()` ensuring features/X doesn't import features/Y internals
    - Run the test suite and fix any violations found
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ]* 16.2 Write property test for dependency rule compliance (Property 1)
    - Create or extend `python_app/tests/test_architecture.py`
    - **Property 1: Dependency Rule Compliance**
    - Use Hypothesis to generate random file selections from the codebase and verify import rules hold
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 12.2**

- [x] 17. Compile-all smoke test
  - [x] 17.1 Create compile-all validation test
    - Create `python_app/tests/test_compile_all.py`
    - Walk all `.py` files under `python_app/` and run `py_compile.compile()` on each
    - Assert zero compilation failures
    - **Property 8: Compilation Validity**
    - **Validates: Requirements 7.5**

- [x] 18. Final checkpoint — Full validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `python -m py_compile` passes on all files
  - Verify app launches without errors
  - Verify all features work: music generation, image generation, video workspace, YouTube upload, profiles, templates
  - Confirm MainWindow reduced by at least 2,000 lines
  - Confirm no `controllers/` package remains
  - Confirm all import-lint rules pass

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation per the refactor policy
- Property tests validate universal correctness properties from the design
- Unit tests validate specific behavioral equivalence
- Tasks that modify `main_window.py` are serialized (Phases 5-9) to avoid merge conflicts
- The delegate-before-deleting pattern is enforced: add coordinator method → delegate → validate → then optionally remove
- All phases follow the Non-Breaking Refactor Policy from `python_app/docs/enterprise-architecture-audit/refactor-policy.md`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "4.5"] },
    { "id": 5, "tasks": ["4.6", "5.1", "5.2"] },
    { "id": 6, "tasks": ["5.3"] },
    { "id": 7, "tasks": ["5.4", "7.1"] },
    { "id": 8, "tasks": ["7.2", "8.1"] },
    { "id": 9, "tasks": ["9.1"] },
    { "id": 10, "tasks": ["11.1"] },
    { "id": 11, "tasks": ["11.2", "12.1"] },
    { "id": 12, "tasks": ["12.2", "13.1"] },
    { "id": 13, "tasks": ["13.2"] },
    { "id": 14, "tasks": ["13.3", "13.4"] },
    { "id": 15, "tasks": ["15.1"] },
    { "id": 16, "tasks": ["15.2"] },
    { "id": 17, "tasks": ["15.3", "16.1"] },
    { "id": 18, "tasks": ["16.2", "17.1"] }
  ]
}
```
