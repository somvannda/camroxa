"""Enumerations for the Platform API domain layer."""

from enum import StrEnum


class UserRole(StrEnum):
    """Roles assigned to user accounts."""

    USER = "user"
    ADMIN = "admin"


class UserStatus(StrEnum):
    """Account lifecycle statuses."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class LicenseStatus(StrEnum):
    """License lifecycle statuses."""

    UNASSIGNED = "unassigned"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PlanType(StrEnum):
    """Subscription plan types."""

    MONTHLY = "monthly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"


class TaskStatus(StrEnum):
    """Status of an AI generation task (Suno)."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class ImageKind(StrEnum):
    """Types of generated images."""

    BACKGROUND = "background"
    THUMBNAIL = "thumbnail"


class ChannelRole(StrEnum):
    """Role of a channel profile within a batch (OK/ALT pairing)."""

    OK = "OK"
    ALT = "ALT"


class TransactionDirection(StrEnum):
    """Direction of a credit wallet transaction."""

    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"


class KeyStatus(StrEnum):
    """Status of an API key entry in the pool."""

    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    DISABLED = "disabled"


class SelectionStrategy(StrEnum):
    """Key selection algorithm for a provider pool."""

    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"


class AIService(StrEnum):
    """External AI service providers integrated with the platform."""

    SUNO = "suno"
    FAL = "fal"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    SLAI = "slai"
    CALA = "cala"


class OperationType(StrEnum):
    """Categories of AI operations for pricing and usage tracking."""

    MUSIC_GENERATION = "music_generation"
    IMAGE_GENERATION = "image_generation"
    TEXT_GENERATION = "text_generation"
    CHANNEL_SETUP = "channel_setup"


class ServiceAvailability(StrEnum):
    """Operational status of an AI service based on Key Pool state."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
