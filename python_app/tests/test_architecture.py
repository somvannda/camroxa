"""
Architecture enforcement test suite.

Scans all Python files and verifies import rules from the dependency matrix.
Uses AST parsing to extract imports and resolve relative paths to absolute
top-level package references.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
"""

import ast
from pathlib import Path

PYTHON_APP = Path(__file__).resolve().parent.parent

# Dependency matrix: for each package (key), the set of packages it must NOT import.
FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "views": {"database", "services"},
    "services": {"views", "app"},
    "database": {"views", "app"},
    "features": {"views", "app", "PyQt6"},
    "models": {"views", "app", "services", "database", "features", "controllers", "visualizer"},
    "visualizer": {"database", "services", "app"},
    "utils": {"views", "app", "services", "database", "features", "controllers", "visualizer", "models"},
}

# Temporary allowlist: files exempt from certain forbidden-import rules pending full decoupling.
# Remove entries as each module is properly refactored.
_FORBIDDEN_IMPORT_ALLOWLIST: dict[str, set[str]] = {
    # Pre-existing views/app imports from features/ (existed before this spec)
    "features/image_prompts/management.py": {"app"},
    "features/music/coordinator.py": {"views"},
    "features/music/settings.py": {"app"},
    "features/profiles/management.py": {"app"},
    "features/progress/coordinator.py": {"views"},
    "features/templates/management.py": {"app"},
    "features/video_export/coordinator.py": {"app"},
    "features/video_export/video_page_controller.py": {"views"},

    # Relocated page controllers — pre-existing database/services deps kept on allowlist
    "views/dashboard_page_controller.py": {"database"},
    "views/music_page_controller.py": {"database"},
    "views/progress_page_controller.py": {"database", "services"},
}

# Top-level packages inside python_app that we track
INTERNAL_PACKAGES = {
    "app", "views", "services", "database", "models",
    "features", "visualizer", "utils", "controllers",
    "PyQt6",
}


def _resolve_relative_import(filepath: Path, module: str, level: int) -> str | None:
    """Resolve a relative import to an absolute dotted path within python_app.

    Given a file like python_app/features/music/coordinator.py with:
        from ...services.music_generation import X  (level=3, module='services.music_generation')

    Python's relative import semantics:
      - level=1 (from .X): current package (file's parent directory)
      - level=2 (from ..X): parent package (one dir up from parent)
      - level=3 (from ...X): grandparent package (two dirs up from parent)

    So we go up (level - 1) directories from the file's parent directory,
    then prepend that base's path relative to PYTHON_APP.

    Returns the resolved dotted path or None if it resolves outside python_app.
    """
    current = filepath.parent
    for _ in range(level - 1):
        current = current.parent
        if current == current.parent:
            # Hit filesystem root
            return None

    # Build the path relative to PYTHON_APP
    try:
        rel = current.relative_to(PYTHON_APP)
    except ValueError:
        return None

    parts = list(rel.parts)
    if module:
        parts.extend(module.split("."))
    return ".".join(parts) if parts else (module or None)


def collect_imports(filepath: Path) -> list[str]:
    """Parse a Python file and return all imported module paths as dotted strings.

    For absolute imports: returns the module path directly.
    For relative imports: resolves to absolute path within python_app.

    Only returns imports that reference internal packages.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                # Absolute import: from X.Y import Z
                if node.module:
                    imports.append(node.module)
            else:
                # Relative import: from ..X import Z
                resolved = _resolve_relative_import(
                    filepath, node.module or "", node.level
                )
                if resolved:
                    imports.append(resolved)

    return imports


def _get_top_package(import_path: str) -> str | None:
    """Extract the top-level package name from a dotted import path.

    Only returns packages that are known internal packages.
    """
    top = import_path.split(".")[0]
    if top in INTERNAL_PACKAGES:
        return top
    return None


def test_no_forbidden_imports():
    """For any package with rules, no file imports from a forbidden package."""
    violations = []

    for package, forbidden in FORBIDDEN_IMPORTS.items():
        package_dir = PYTHON_APP / package
        if not package_dir.is_dir():
            continue

        for py_file in package_dir.rglob("*.py"):
            imports = collect_imports(py_file)
            for imp in imports:
                top_package = _get_top_package(imp)
                if top_package and top_package in forbidden:
                    rel_path = py_file.relative_to(PYTHON_APP)
                    rel_str = str(rel_path).replace("\\", "/")
                    # Skip temporarily allowlisted violations
                    allowed = _FORBIDDEN_IMPORT_ALLOWLIST.get(rel_str, set())
                    if top_package in allowed:
                        continue
                    violations.append(
                        f"  {rel_path} imports '{imp}' "
                        f"(rule: {package}/ must not import {top_package}/)"
                    )

    assert not violations, (
        "Forbidden import violations found:\n" + "\n".join(sorted(violations))
    )


def test_no_cross_feature_internals():
    """features/X must not import features/Y internals.

    Cross-feature imports are only allowed to the shared interface at
    features/ports.py, features/__init__.py, or the target feature's
    __init__.py facade (e.g., features.merge). Importing deeper into
    features/Y/submodule.py is forbidden.
    """
    features_dir = PYTHON_APP / "features"
    if not features_dir.is_dir():
        return

    # Collect feature subdirectories
    feature_names = {
        d.name
        for d in features_dir.iterdir()
        if d.is_dir() and not d.name.startswith(("__", "."))
    }

    violations = []

    for feature_name in sorted(feature_names):
        feature_dir = features_dir / feature_name
        for py_file in feature_dir.rglob("*.py"):
            imports = collect_imports(py_file)
            for imp in imports:
                # Check if this import references features.X where X != current feature
                parts = imp.split(".")
                if len(parts) >= 2 and parts[0] == "features":
                    target = parts[1]
                    # Allow imports of shared top-level files: features.ports
                    if target not in feature_names:
                        continue
                    if target == feature_name:
                        continue
                    # Allow facade imports: features.X (only 2 parts = __init__.py)
                    # Forbid internal imports: features.X.submodule (3+ parts)
                    if len(parts) > 2:
                        rel_path = py_file.relative_to(PYTHON_APP)
                        violations.append(
                            f"  {rel_path} imports '{imp}' "
                            f"(cross-feature: {feature_name}/ must not import "
                            f"{target}/ internals)"
                        )

    assert not violations, (
        "Cross-feature internal import violations found:\n"
        + "\n".join(sorted(violations))
    )
