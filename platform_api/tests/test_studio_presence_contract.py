"""The shared-presence writer may only touch columns migration 198 creates.

The endpoint answered 500 on every call because the service wrote `last_seen`,
`playhead_seconds` and `selected_lane_id` and matched on `(project_id, user_id)`,
none of which exist: revision 198 creates `client_id`, `cursor_time`, `playhead`
and `updated_at` with a `(project_id, client_id)` key.

This test reads both files, so the pair cannot drift apart again silently.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "platform_api" / "migrations" / "versions" / "198_studio_editor_presence.py"
SERVICE = ROOT / "platform_api" / "services" / "web_music_service.py"

# SQL keywords and functions that appear in the statements alongside column names.
SQL_WORDS = {
    "INSERT",
    "INTO",
    "VALUES",
    "SELECT",
    "FROM",
    "WHERE",
    "AND",
    "OR",
    "ON",
    "CONFLICT",
    "DO",
    "UPDATE",
    "SET",
    "DELETE",
    "ORDER",
    "BY",
    "DESC",
    "ASC",
    "NOW",
    "EXCLUDED",
    "INTERVAL",
    "SECONDS",
    "PRIMARY",
    "KEY",
    "STUDIO_EDITOR_PRESENCE",
}


def migration_columns() -> set[str]:
    text = MIGRATION.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if "CREATE TABLE IF NOT EXISTS studio_editor_presence (" in line
    )
    columns: set[str] = set()
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith(")"):
            break
        if not stripped or stripped.startswith(("PRIMARY", "--")):
            continue
        columns.add(stripped.split()[0].strip(","))
    return columns


def presence_statements() -> list[str]:
    """Every string literal inside the shared-presence method that names the table."""
    source = SERVICE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "touch_studio_shared_presence":
            literals = [
                child.value
                for child in ast.walk(node)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            ]
            return [value for value in literals if "studio_editor_presence" in value]
    raise AssertionError("touch_studio_shared_presence not found")


def test_shared_presence_sql_only_uses_existing_columns() -> None:
    columns = migration_columns()
    assert {"project_id", "client_id", "user_id", "display_name", "playhead", "updated_at"} <= columns

    statements = presence_statements()
    assert statements, "the writer must reference studio_editor_presence"

    referenced: set[str] = set()
    for statement in statements:
        cleaned = re.sub(r"\$\d+", " ", statement)
        referenced.update(
            token.lower() for token in re.findall(r"[a-z_][a-z0-9_]*", cleaned.lower())
        )

    unknown = referenced - {word.lower() for word in SQL_WORDS} - columns
    assert unknown == set(), f"shared presence SQL uses columns the table lacks: {sorted(unknown)}"
