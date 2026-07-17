"""Marketplace feature — browse, install, and manage marketplace templates."""

from .coordinator import MarketplaceCoordinator
from .delete_confirm_dialog import MarketplaceDeleteConfirmDialog
from .template_badges import (
    get_template_badge_style,
    get_template_badge_text,
    should_confirm_delete,
)
from .template_protection import (
    can_save_template,
    is_marketplace_template,
    prepare_save_as_copy,
    validate_save_as_name,
)

__all__ = [
    "MarketplaceCoordinator",
    "MarketplaceDeleteConfirmDialog",
    "can_save_template",
    "get_template_badge_style",
    "get_template_badge_text",
    "is_marketplace_template",
    "prepare_save_as_copy",
    "should_confirm_delete",
    "validate_save_as_name",
]
