# Requirements Document

## Introduction

This document defines requirements for evolving the Python desktop application (PyQt6) from its current state — where `MainWindow` remains a ~7,200-line god object and modules are misplaced across layers — into a team-scalable enterprise-grade structure. The refactoring strictly follows the governance documents in `python_app/docs/enterprise-architecture-audit/`, corrects layer violations introduced by the earlier `main-window-refactor` spec, migrates transitional controllers into feature coordinators, extracts remaining orchestration from `MainWindow`, and establishes enforceable layer boundaries. All changes preserve existing runtime behavior.

## Glossary

- **MainWindow**: The central `QMainWindow` subclass in `app/main_window.py` that currently owns composition, signal wiring, and residual orchestration logic.
- **App_Shell**: The `app/` package responsible exclusively for bootstrap, window composition, dependency wiring, signal registration, and theme/logging setup.
- **View_Layer**: The `views/` package responsible for widget construction, page layout, UI-only behavior, and reusable controls.
- **Feature_Coordinator**: A class in `features/<feature>/coordinator.py` that owns use-case orchestration, state transitions, validation, and workflow decisions for a single feature boundary.
- **Controller**: A transitional orchestration module in `controllers/` that should be absorbed into the corresponding Feature_Coordinator.
- **Service_Layer**: The `services/` package for external integrations, provider clients, and ffmpeg helpers. Must remain UI-independent.
- **Database_Layer**: The `database/` package for persistence, queries, and migrations. Must not know about UI.
- **Models_Layer**: The `models/` package for pure data shapes and normalization using stdlib only.
- **Visualizer_Subsystem**: The `visualizer/` package for rendering internals. Must not depend on App_Shell or Database_Layer.
- **Dependency_Injection**: A pattern where coordinators receive collaborators (services, database adapters, event bus) via constructor parameters instead of holding references to MainWindow.
- **Thin_Delegator**: A 1–3 line method in MainWindow that forwards a call to a Feature_Coordinator, preserving the public entrypoint.
- **DTO**: Data Transfer Object — a plain data structure used to communicate across layer boundaries without coupling.
- **Refactor_Slice**: A single coherent extraction unit that moves logic without changing visible behavior.
- **Governance_Documents**: The architecture audit files in `python_app/docs/enterprise-architecture-audit/` that define ownership, dependencies, conventions, and policy.

## Requirements

### Requirement 1: Relocate UI Utilities to Views Layer

**User Story:** As a senior developer, I want all UI helper utilities in the `views/` layer (not `app/`), so layer ownership is predictable and follows the ownership map.

#### Acceptance Criteria

1. WHEN the refactor is complete, THE App_Shell SHALL NOT contain `style_helper.py`, `widget_factory.py`, or `footer_controller.py` modules.
2. WHEN the refactor is complete, THE View_Layer SHALL contain a `views/helpers/` subpackage that owns `style_helper.py`, `widget_factory.py`, and `footer_controller.py`.
3. WHEN modules are relocated, THE System SHALL update all import statements across the codebase to reference the new `views/helpers/` paths.
4. IF any module outside `views/` or `app/` imports a relocated UI helper, THEN THE System SHALL raise an import-lint violation warning.
5. WHEN modules are relocated, THE System SHALL preserve all existing public function signatures and return values without modification.

### Requirement 2: Migrate Controllers to Feature Coordinators

**User Story:** As a senior developer, I want `controllers/` absorbed into `features/` coordinators, so orchestration has one canonical home following coordinator conventions.

#### Acceptance Criteria

1. WHEN the migration is complete, THE System SHALL have a `features/music/coordinator.py` module containing a `MusicGenerationCoordinator` class that absorbs all orchestration logic from `controllers/music_controller.py`.
2. WHEN the migration is complete, THE System SHALL have a `features/image/coordinator.py` module containing an `ImageGenerationCoordinator` class that absorbs all orchestration logic from `controllers/image_controller.py`.
3. WHEN a Feature_Coordinator is created, THE Feature_Coordinator SHALL receive user intents, validate inputs, call services and database modules, and decide workflow sequencing per coordinator conventions.
4. WHEN migration is complete, THE System SHALL remove the `controllers/music_controller.py` and `controllers/image_controller.py` files.
5. WHEN migration is complete, THE System SHALL update all callers that previously referenced the controller modules to reference the new Feature_Coordinator modules.
6. IF the `controllers/` package becomes empty after migration, THEN THE System SHALL remove the `controllers/` package.

### Requirement 3: Reduce MainWindow to Composition Shell

**User Story:** As a senior developer, I want MainWindow to be a thin composition shell that only wires signals and delegates, not a logic warehouse.

#### Acceptance Criteria

1. WHEN the refactor is complete, THE MainWindow SHALL contain only bootstrap, page composition, signal-to-coordinator wiring, shared application state injection, and Thin_Delegator methods.
2. WHEN orchestration logic is extracted, THE MainWindow SHALL delegate to the appropriate Feature_Coordinator via a Thin_Delegator of 1–3 lines.
3. WHEN a Feature_Coordinator exists for a domain, THE MainWindow SHALL NOT contain inline workflow logic, DB query calls, or service integration calls for that domain.
4. WHEN the refactor is complete, THE MainWindow SHALL have reduced by at least 2,000 lines compared to the current ~7,200-line state.
5. IF new feature logic is proposed for MainWindow, THEN THE System SHALL reject the addition and direct it to the appropriate Feature_Coordinator.

### Requirement 4: Extract Remaining Orchestration into Feature Coordinators

**User Story:** As a senior developer, I want all remaining MainWindow orchestration extracted into feature coordinators, so each feature domain has a clear owner.

#### Acceptance Criteria

1. WHEN extraction is complete, THE System SHALL have a `MusicGenerationCoordinator` that owns music enqueue, provider selection, callback handling, and batch state transitions.
2. WHEN extraction is complete, THE System SHALL have an `ImageGenerationCoordinator` that owns image job enqueue, sample selection, generation refresh, and result handling.
3. WHEN extraction is complete, THE System SHALL have a `VideoWorkspaceCoordinator` or equivalent that owns video preview state, resolution/template/background/logo coordination, and export handoff preparation.
4. WHEN extraction is complete, THE System SHALL have a `SettingsCoordinator` or equivalent that owns settings persistence flows and app configuration state transitions.
5. WHEN each extraction slice is applied, THE System SHALL preserve all existing visible behavior including page flows, keyboard/mouse interactions, status text, and error messages.
6. WHEN each extraction slice is applied, THE System SHALL follow the delegate-before-deleting pattern: add coordinator method, make host delegate, validate, then optionally remove old implementation.

### Requirement 5: Transfer Timer and Polling Ownership to Feature Coordinators

**User Story:** As a senior developer, I want each feature coordinator to own its timer/polling policy, so background task management is explicit per feature.

#### Acceptance Criteria

1. WHEN timer ownership is transferred, THE Feature_Coordinator SHALL define when polling starts and stops for its domain.
2. WHEN timer ownership is transferred, THE Feature_Coordinator SHALL define concurrency limits, retry policy, and cancellation semantics for its background tasks.
3. WHEN timer ownership is transferred, THE MainWindow SHALL retain only the timer attribute names needed for shutdown lifecycle management.
4. WHEN timer policy is moved, THE System SHALL preserve existing timer intervals, polling frequencies, and auto-start behavior without modification.
5. IF a feature requires cross-feature timer coordination, THEN THE System SHALL use a stable public facade method on the target Feature_Coordinator rather than reaching into internal timer state.

### Requirement 6: Apply Dependency Injection to All Coordinators

**User Story:** As a senior developer, I want all coordinators to receive dependencies via constructor injection, so they are testable in isolation without referencing MainWindow.

#### Acceptance Criteria

1. WHEN Dependency_Injection is applied, THE Feature_Coordinator SHALL receive collaborators (services, database adapters, event bus, configuration) as constructor parameters.
2. WHEN Dependency_Injection is applied, THE Feature_Coordinator SHALL NOT hold a reference to MainWindow or any `host` field typed as MainWindow.
3. WHEN Dependency_Injection is applied, THE Feature_Coordinator SHALL be instantiable in a unit test with mock collaborators and no Qt application instance.
4. WHEN the App_Shell bootstraps coordinators, THE App_Shell SHALL construct each Feature_Coordinator by passing concrete service, database, and event bus instances.
5. IF a coordinator currently uses `self.host` to access MainWindow methods, THEN THE System SHALL replace that access with an injected interface or callback.

### Requirement 7: Preserve Runtime Behavior

**User Story:** As a QA engineer, I want the refactored app to behave identically at runtime, so no user-facing functionality breaks.

#### Acceptance Criteria

1. WHEN any Refactor_Slice is applied, THE System SHALL preserve all page flows, navigation order, and page transitions.
2. WHEN any Refactor_Slice is applied, THE System SHALL preserve all keyboard shortcuts and mouse interactions.
3. WHEN any Refactor_Slice is applied, THE System SHALL preserve all error messages, status text, and loading states.
4. WHEN any Refactor_Slice is applied, THE System SHALL preserve all queue operations, progress page actions, export behavior, and upload behavior.
5. WHEN any Refactor_Slice is applied, THE System SHALL pass `python -m py_compile` on all changed files without errors.
6. IF a Refactor_Slice causes a regression, THEN THE System SHALL revert the slice and diagnose the root cause before retrying.

### Requirement 8: Enforce Layer Boundaries via Import Rules

**User Story:** As a new team member, I want clear layer boundaries enforced by import rules, so I know where to put new code.

#### Acceptance Criteria

1. THE System SHALL enforce that `views/` modules do not import from `database/` or `services/` directly.
2. THE System SHALL enforce that `services/` modules do not import from `views/` or `app/` modules.
3. THE System SHALL enforce that `database/` modules do not import from `views/` or `app/` modules.
4. THE System SHALL enforce that `models/` modules do not import from any other internal package except stdlib.
5. THE System SHALL enforce that `visualizer/` modules do not import from `database/`, `services/`, or `app/` modules.
6. THE System SHALL enforce that one `features/X` module does not import internals from a different `features/Y` module — cross-feature access uses only the facade.
7. WHEN a forbidden import is detected, THE System SHALL report the violation with the specific rule violated and the offending file path.

### Requirement 9: Fix the Removed Variable Bug

**User Story:** As a developer, I want the `removed` variable bug fixed, so `_delete_music_saved_text` does not raise NameError at runtime.

#### Acceptance Criteria

1. WHEN `_delete_music_saved_text` is called, THE System SHALL define the `removed` variable before it is referenced in the control flow.
2. WHEN the bug fix is applied, THE System SHALL preserve the existing behavior of the method for all non-buggy execution paths.
3. WHEN the bug fix is applied, THE System SHALL apply the fix in a separate Refactor_Slice that does not include structural changes per Rule 5 of the refactor policy.

### Requirement 10: Consolidate and Clean Imports

**User Story:** As a developer, I want all imports consolidated at module level with duplicates removed, so the codebase is clean and predictable.

#### Acceptance Criteria

1. WHEN import consolidation is complete, THE `main_window.py` module SHALL have all imports declared at module level with no inline imports inside method bodies.
2. WHEN import consolidation is complete, THE `main_window.py` module SHALL have no duplicate import statements.
3. WHEN imports are consolidated, THE System SHALL preserve all runtime dependencies — no previously reachable module import shall be removed.
4. WHEN imports are consolidated, THE System SHALL order imports following PEP 8 conventions: stdlib, third-party, local application imports, each group separated by a blank line.

### Requirement 11: Add Type Annotations

**User Story:** As a developer, I want type annotations on all public and protected methods, so IDE tooling catches errors early.

#### Acceptance Criteria

1. WHEN type annotation work is complete, THE System SHALL have type annotations on all public methods (no leading underscore) across feature coordinators, services, database, and models modules.
2. WHEN type annotation work is complete, THE System SHALL have type annotations on all protected methods (single leading underscore) across feature coordinators, services, database, and models modules.
3. WHEN type annotations are added, THE System SHALL use standard Python typing constructs (`Optional`, `Union`, `list`, `dict`, `tuple`, `Any`) from the `typing` module or built-in generics for Python 3.10+.
4. WHEN type annotations are added, THE System SHALL pass `mypy --ignore-missing-imports` on annotated modules without type errors.
5. WHEN type annotations are added to existing methods, THE System SHALL NOT change method behavior or signatures — only add return type and parameter type hints.

### Requirement 12: Harden the Visualizer Boundary

**User Story:** As a developer, I want the visualizer boundary hardened with explicit DTO contracts, so rendering changes do not break the app shell.

#### Acceptance Criteria

1. WHEN the visualizer boundary is hardened, THE Visualizer_Subsystem SHALL communicate with the App_Shell and Feature_Coordinators exclusively through defined DTO interfaces.
2. WHEN the visualizer boundary is hardened, THE Visualizer_Subsystem SHALL NOT import from `app/`, `database/`, or `services/` packages.
3. WHEN the DTO interface is defined, THE System SHALL place DTO definitions in a shared location accessible to both the visualizer and its callers (e.g., `models/visualizer_contracts.py` or `visualizer/contracts.py`).
4. WHEN the visualizer boundary is hardened, THE System SHALL preserve all existing preview rendering, export rendering, and audio-reactive visualization behavior.
5. IF the Visualizer_Subsystem requires data currently obtained via App_Shell internals, THEN THE System SHALL pass that data through the DTO interface at the call site rather than importing app-shell modules.
