"""Feature package exports for application-level coordination boundaries."""

from .auto_video import AutoVideoCoordinator
from .image import ImageGenerationCoordinator
from .image_prompts import ImagePromptPresetCoordinator
from .merge import MergeWorker
from .music import MusicHistoryCoordinator, MusicSettingsCoordinator
from .persistence import PersistenceCoordinator
from .profiles import MusicProfileManagementCoordinator, ProfileCoordinator
from .progress import ProgressCoordinator
from .templates import TemplateManagementCoordinator, VideoTemplateCoordinator
from .text_presets import TextPresetManagerCoordinator
from .video_export import ExportBatch, ExportCoordinator, VideoWorkspaceStateCoordinator
from .video_workspace import VideoWorkspaceCoordinator
from .youtube import YouTubeCoordinator

__all__ = [
    "AutoVideoCoordinator",
    "ExportBatch",
    "ExportCoordinator",
    "ImageGenerationCoordinator",
    "ImagePromptPresetCoordinator",
    "MergeWorker",
    "MusicHistoryCoordinator",
    "MusicProfileManagementCoordinator",
    "MusicSettingsCoordinator",
    "PersistenceCoordinator",
    "ProfileCoordinator",
    "ProgressCoordinator",
    "TemplateManagementCoordinator",
    "TextPresetManagerCoordinator",
    "VideoTemplateCoordinator",
    "VideoWorkspaceCoordinator",
    "VideoWorkspaceStateCoordinator",
    "YouTubeCoordinator",
]
