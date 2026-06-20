"""Protocol interfaces (ports) for dependency injection.

All service protocols and their associated data types are exported from this
package. Consumers should import directly from `platform_api.ports`.
"""

from platform_api.ports.auth_port import AuthServicePort, TokenPair, TokenPayload
from platform_api.ports.credit_port import CreditServicePort
from platform_api.ports.generation_port import (
    DraftRequest,
    GenerationServicePort,
    ImageRequest,
    SongDraft,
    SunoRequest,
)
from platform_api.ports.key_pool_port import KeyPoolRepositoryPort
from platform_api.ports.notification_port import NotificationServicePort

__all__ = [
    # Auth
    "AuthServicePort",
    "TokenPair",
    "TokenPayload",
    # Credit
    "CreditServicePort",
    # Generation
    "GenerationServicePort",
    "SunoRequest",
    "ImageRequest",
    "DraftRequest",
    "SongDraft",
    # Key Pool
    "KeyPoolRepositoryPort",
    # Notification
    "NotificationServicePort",
]
