"""Video template feature coordination entrypoints."""

from .coordinator import VideoTemplateCoordinator
from .management import (
    TemplateManagementCoordinator,
    create_reel_template,
    delete_reel_template,
    list_reel_templates,
    update_reel_template,
)

__all__ = [
    "VideoTemplateCoordinator",
    "TemplateManagementCoordinator",
    "create_reel_template",
    "update_reel_template",
    "delete_reel_template",
    "list_reel_templates",
]
