"""Template protection logic — enforces read-only policy on marketplace templates.

Marketplace-installed templates (source='marketplace') cannot be saved directly.
Users must "Save As" to create an editable copy with source='user'.
"""

from __future__ import annotations

import uuid
from typing import Any


def is_marketplace_template(template_data: dict[str, Any]) -> bool:
    """Check if the given template data represents a marketplace-installed template.

    Args:
        template_data: Template record dict containing at least a 'source' field.

    Returns:
        True if source is 'marketplace', False otherwise.
    """
    return str(template_data.get("source", "")).strip().lower() == "marketplace"


def can_save_template(template_data: dict[str, Any]) -> bool:
    """Determine whether the "Save" action is allowed for a template.

    Marketplace templates are read-only and cannot be saved directly.
    Templates with source='user' or source='builtin' can be saved.

    Args:
        template_data: Template record dict containing at least a 'source' field.

    Returns:
        False if the template is from the marketplace, True otherwise.
    """
    return not is_marketplace_template(template_data)


def validate_save_as_name(name: str) -> tuple[bool, str]:
    """Validate a name for the "Save As" operation.

    Rules:
        - Must not be empty
        - Must not be whitespace-only
        - Must be at most 100 characters

    Args:
        name: The user-provided template name.

    Returns:
        A tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    if not name:
        return False, "Name cannot be empty."
    if name.strip() == "":
        return False, "Name cannot be whitespace only."
    if len(name) > 100:
        return False, "Name must be at most 100 characters."
    return True, ""


def prepare_save_as_copy(
    original: dict[str, Any],
    new_name: str,
    user_id: str,
) -> dict[str, Any]:
    """Create a new template dict for the "Save As" copy.

    Generates a new uid, sets source='user', applies the user-provided name,
    and copies the template JSON from the original.

    Args:
        original: The original template record dict (must contain 'template' key
                  with the template JSON payload).
        new_name: The user-provided name for the copy.
        user_id: The authenticated user's ID.

    Returns:
        A new template dict suitable for insertion into the video_templates table.
    """
    template_json = original.get("template")
    if not isinstance(template_json, dict):
        template_json = {}

    return {
        "uid": str(uuid.uuid4()),
        "name": new_name,
        "source": "user",
        "template": dict(template_json),
        "kind": str(original.get("kind", "video")),
        "user_id": user_id,
        "marketplace_item_id": original.get("marketplace_item_id"),
    }
