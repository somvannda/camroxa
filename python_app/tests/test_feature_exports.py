"""
Export-consistency test suite.

Dynamically discovers all sub-packages under features/ and verifies:
  1. Each sub-package __init__.py exports at least one public symbol.
  2. Sub-packages with coordinator.py export at least one class ending in 'Coordinator'.
  3. The top-level features/__init__.py re-exports at least one symbol from each sub-package.

Uses AST-based parsing (no runtime imports) to avoid PyQt6 dependency requirements.

Validates: Requirements 5.4
"""

import ast
from pathlib import Path

PYTHON_APP = Path(__file__).resolve().parent.parent
FEATURES_DIR = PYTHON_APP / "features"


def _get_feature_subpackages() -> list[str]:
    """Discover all sub-packages under features/ (directories with __init__.py)."""
    subpackages = []
    for entry in sorted(FEATURES_DIR.iterdir()):
        if (
            entry.is_dir()
            and not entry.name.startswith(("__", "."))
            and (entry / "__init__.py").exists()
        ):
            subpackages.append(entry.name)
    return subpackages


def _get_exported_names(init_path: Path) -> list[str]:
    """Parse an __init__.py and return its exported public names.

    Checks for an explicit __all__ list first. If not present, collects
    all names imported at module level (from ... import X) that don't
    start with an underscore.
    """
    if not init_path.exists():
        return []

    source = init_path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(init_path))
    except SyntaxError:
        return []

    # Look for __all__ assignment
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant)
                            and isinstance(elt.value, str)
                        ]

    # No __all__; collect all imported names that are public
    names: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                if not name.startswith("_"):
                    names.append(name)

    return names


def _get_import_sources(init_path: Path) -> dict[str, list[str]]:
    """Parse features/__init__.py and map sub-package names to imported symbols.

    Returns a dict like {'auto_video': ['AutoVideoCoordinator'], ...}
    Only considers relative imports (from .subpackage import X).
    """
    if not init_path.exists():
        return {}

    source = init_path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(init_path))
    except SyntaxError:
        return {}

    result: dict[str, list[str]] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            # Relative import: from .subpackage import X
            # The module might be dotted (e.g., .video_export.workspace),
            # so we take the top-level sub-package name
            subpkg = node.module.split(".")[0]
            names = [
                alias.asname if alias.asname else alias.name
                for alias in node.names
            ]
            result.setdefault(subpkg, []).extend(names)

    return result


def test_subpackages_export_public_symbols():
    """Each feature sub-package __init__.py exports at least one public symbol."""
    subpackages = _get_feature_subpackages()
    assert subpackages, "No feature sub-packages found"

    failures = []
    for pkg in subpackages:
        init_path = FEATURES_DIR / pkg / "__init__.py"
        exports = _get_exported_names(init_path)
        if not exports:
            failures.append(f"  features/{pkg}/__init__.py exports no public symbols")

    assert not failures, (
        "Sub-packages missing public exports:\n" + "\n".join(failures)
    )


def test_coordinator_subpackages_export_coordinator_class():
    """Sub-packages with coordinator.py export at least one *Coordinator class."""
    subpackages = _get_feature_subpackages()
    failures = []

    for pkg in subpackages:
        coordinator_path = FEATURES_DIR / pkg / "coordinator.py"
        if not coordinator_path.exists():
            continue

        init_path = FEATURES_DIR / pkg / "__init__.py"
        exports = _get_exported_names(init_path)
        coordinator_exports = [
            name for name in exports if name.endswith("Coordinator")
        ]
        if not coordinator_exports:
            failures.append(
                f"  features/{pkg}/__init__.py has coordinator.py but exports "
                f"no class ending with 'Coordinator' (exports: {exports})"
            )

    assert not failures, (
        "Coordinator sub-packages missing Coordinator export:\n"
        + "\n".join(failures)
    )


def test_non_coordinator_subpackages_export_public_class():
    """Sub-packages without coordinator.py export at least one public class."""
    subpackages = _get_feature_subpackages()
    failures = []

    for pkg in subpackages:
        coordinator_path = FEATURES_DIR / pkg / "coordinator.py"
        if coordinator_path.exists():
            continue

        init_path = FEATURES_DIR / pkg / "__init__.py"
        exports = _get_exported_names(init_path)
        # Check that at least one export looks like a class name (starts uppercase)
        public_classes = [
            name for name in exports
            if name[0].isupper() and not name.startswith("_")
        ]
        if not public_classes:
            failures.append(
                f"  features/{pkg}/__init__.py has no coordinator.py and exports "
                f"no public class (exports: {exports})"
            )

    assert not failures, (
        "Non-coordinator sub-packages missing public class export:\n"
        + "\n".join(failures)
    )


def test_features_init_reexports_from_all_subpackages():
    """features/__init__.py re-exports at least one symbol from each sub-package."""
    subpackages = _get_feature_subpackages()
    features_init = FEATURES_DIR / "__init__.py"
    import_sources = _get_import_sources(features_init)

    missing = []
    for pkg in subpackages:
        if pkg not in import_sources or not import_sources[pkg]:
            missing.append(
                f"  features/__init__.py does not re-export any symbol "
                f"from sub-package '{pkg}'"
            )

    assert not missing, (
        "Top-level features/__init__.py missing re-exports:\n"
        + "\n".join(missing)
    )
