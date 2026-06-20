"""Music prompt management service.

Provides create/update/delete for song descriptions and structures,
matchKey pairing logic, and cycle/shuffle structure assignment for
batch generation.

Requirements: 9.1, 9.2, 9.3, 9.6, 9.7
"""

from __future__ import annotations

import logging
import random
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.models.domain import MusicDescription, MusicStructure

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_MIN_NAME_LENGTH: int = 1
_MAX_NAME_LENGTH: int = 100
_MIN_CONTENT_LENGTH: int = 1
_MAX_CONTENT_LENGTH: int = 5000


# ---------------------------------------------------------------------------
# Dependency Protocols
# ---------------------------------------------------------------------------


class PromptRepositoryPort(Protocol):
    """Protocol for the prompt repository dependency."""

    async def create_description(self, desc: MusicDescription) -> MusicDescription: ...
    async def get_description_by_id(self, desc_id: UUID) -> MusicDescription | None: ...
    async def get_description_by_name(self, name: str) -> MusicDescription | None: ...
    async def list_descriptions(self) -> list[MusicDescription]: ...
    async def update_description(
        self, desc_id: UUID, **fields: Any
    ) -> MusicDescription | None: ...
    async def delete_description(self, desc_id: UUID) -> bool: ...

    async def create_structure(self, struct: MusicStructure) -> MusicStructure: ...
    async def get_structure_by_id(self, struct_id: UUID) -> MusicStructure | None: ...
    async def get_structure_by_name(self, name: str) -> MusicStructure | None: ...
    async def list_structures(self) -> list[MusicStructure]: ...
    async def update_structure(
        self, struct_id: UUID, **fields: Any
    ) -> MusicStructure | None: ...
    async def delete_structure(self, struct_id: UUID) -> bool: ...

    async def get_descriptions_with_match_key(self) -> list[MusicDescription]: ...
    async def get_structures_with_match_key(self) -> list[MusicStructure]: ...
    async def get_matched_pairs(
        self,
    ) -> list[tuple[MusicDescription, MusicStructure]]: ...


# ---------------------------------------------------------------------------
# Prompt Service
# ---------------------------------------------------------------------------


class PromptService:
    """Application service for music prompt management.

    Handles CRUD for song descriptions and structures, enforces validation
    rules (name 1-100 chars unique, content 1-5000 chars), provides matchKey
    pairing logic, and implements cyclic/shuffle structure assignment for
    batch generation.

    Args:
        prompt_repo: Repository for prompt persistence operations.
    """

    def __init__(self, prompt_repo: PromptRepositoryPort) -> None:
        self._prompt_repo = prompt_repo

    # -----------------------------------------------------------------------
    # Validation helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_name(name: str, entity_type: str) -> str:
        """Validate and normalize a prompt name.

        Args:
            name: The name string to validate.
            entity_type: 'description' or 'structure' for error messages.

        Returns:
            The stripped name string.

        Raises:
            ValidationError: If name is empty, too short, or too long.
        """
        if not name or not name.strip():
            raise ValidationError(
                f"{entity_type.capitalize()} name is required.",
                details={"field": "name"},
            )
        name = name.strip()
        if len(name) < _MIN_NAME_LENGTH or len(name) > _MAX_NAME_LENGTH:
            raise ValidationError(
                f"{entity_type.capitalize()} name must be between "
                f"{_MIN_NAME_LENGTH} and {_MAX_NAME_LENGTH} characters.",
                details={
                    "field": "name",
                    "length": len(name),
                    "min": _MIN_NAME_LENGTH,
                    "max": _MAX_NAME_LENGTH,
                },
            )
        return name

    @staticmethod
    def _validate_content(content: str, entity_type: str) -> str:
        """Validate prompt content length.

        Args:
            content: The content string to validate.
            entity_type: 'description' or 'structure' for error messages.

        Returns:
            The content string (not stripped — whitespace may be significant).

        Raises:
            ValidationError: If content is empty or exceeds max length.
        """
        if not content:
            raise ValidationError(
                f"{entity_type.capitalize()} content is required.",
                details={"field": "content"},
            )
        if len(content) < _MIN_CONTENT_LENGTH or len(content) > _MAX_CONTENT_LENGTH:
            raise ValidationError(
                f"{entity_type.capitalize()} content must be between "
                f"{_MIN_CONTENT_LENGTH} and {_MAX_CONTENT_LENGTH} characters.",
                details={
                    "field": "content",
                    "length": len(content),
                    "min": _MIN_CONTENT_LENGTH,
                    "max": _MAX_CONTENT_LENGTH,
                },
            )
        return content

    # -----------------------------------------------------------------------
    # Music Description CRUD
    # -----------------------------------------------------------------------

    async def create_description(
        self,
        name: str,
        content: str,
        match_key: str | None = None,
    ) -> MusicDescription:
        """Create a new song description.

        Validates name (1-100 chars, unique), content (1-5000 chars),
        and optional match_key.

        Args:
            name: Unique description name.
            content: Genre/mood/energy description text.
            match_key: Optional key for pairing with structures.

        Returns:
            The created MusicDescription.

        Raises:
            ValidationError: If name or content validation fails.
            DuplicateError: If a description with the same name exists.
        """
        name = self._validate_name(name, "description")
        content = self._validate_content(content, "description")

        # Check uniqueness
        existing = await self._prompt_repo.get_description_by_name(name)
        if existing is not None:
            raise DuplicateError(
                f"A description named '{name}' already exists.",
                details={"name": name},
            )

        desc = MusicDescription(
            id=uuid4(),
            name=name,
            content=content,
            match_key=match_key.strip() if match_key else None,
        )

        created = await self._prompt_repo.create_description(desc)
        logger.info("Created description '%s' (id=%s).", name, created.id)
        return created

    async def update_description(
        self, desc_id: UUID, **fields: Any
    ) -> MusicDescription:
        """Update an existing song description.

        Validates any changed fields. If name is changed, checks uniqueness.
        Clearing match_key dissociates from pairings.

        Args:
            desc_id: The UUID of the description to update.
            **fields: Fields to update (name, content, match_key).

        Returns:
            The updated MusicDescription.

        Raises:
            NotFoundError: If the description does not exist.
            ValidationError: If name or content validation fails.
            DuplicateError: If the new name conflicts with another.
        """
        # Validate name if provided
        if "name" in fields:
            fields["name"] = self._validate_name(fields["name"], "description")
            # Check uniqueness of new name
            existing = await self._prompt_repo.get_description_by_name(fields["name"])
            if existing is not None and existing.id != desc_id:
                raise DuplicateError(
                    f"A description named '{fields['name']}' already exists.",
                    details={"name": fields["name"]},
                )

        # Validate content if provided
        if "content" in fields:
            fields["content"] = self._validate_content(fields["content"], "description")

        # Normalize match_key
        if "match_key" in fields:
            mk = fields["match_key"]
            fields["match_key"] = mk.strip() if mk else None

        updated = await self._prompt_repo.update_description(desc_id, **fields)
        if updated is None:
            raise NotFoundError(
                f"Description {desc_id} not found.",
                details={"description_id": str(desc_id)},
            )

        logger.info("Updated description %s.", desc_id)
        return updated

    async def delete_description(self, desc_id: UUID) -> None:
        """Delete a song description.

        Removes the description and dissociates it from any match key
        pairings and songs.

        Args:
            desc_id: The UUID of the description to delete.

        Raises:
            NotFoundError: If the description does not exist.
        """
        deleted = await self._prompt_repo.delete_description(desc_id)
        if not deleted:
            raise NotFoundError(
                f"Description {desc_id} not found.",
                details={"description_id": str(desc_id)},
            )
        logger.info("Deleted description %s.", desc_id)

    async def get_description(self, desc_id: UUID) -> MusicDescription:
        """Get a description by ID.

        Args:
            desc_id: The UUID of the description.

        Returns:
            The MusicDescription.

        Raises:
            NotFoundError: If the description does not exist.
        """
        desc = await self._prompt_repo.get_description_by_id(desc_id)
        if desc is None:
            raise NotFoundError(
                f"Description {desc_id} not found.",
                details={"description_id": str(desc_id)},
            )
        return desc

    async def list_descriptions(self) -> list[MusicDescription]:
        """List all descriptions ordered by name ascending."""
        return await self._prompt_repo.list_descriptions()

    # -----------------------------------------------------------------------
    # Music Structure CRUD
    # -----------------------------------------------------------------------

    async def create_structure(
        self,
        name: str,
        content: str,
        match_key: str | None = None,
    ) -> MusicStructure:
        """Create a new song structure.

        Validates name (1-100 chars, unique), content (1-5000 chars),
        and optional match_key.

        Args:
            name: Unique structure name.
            content: Section headers text (e.g. [Verse], [Chorus]).
            match_key: Optional key for pairing with descriptions.

        Returns:
            The created MusicStructure.

        Raises:
            ValidationError: If name or content validation fails.
            DuplicateError: If a structure with the same name exists.
        """
        name = self._validate_name(name, "structure")
        content = self._validate_content(content, "structure")

        # Check uniqueness
        existing = await self._prompt_repo.get_structure_by_name(name)
        if existing is not None:
            raise DuplicateError(
                f"A structure named '{name}' already exists.",
                details={"name": name},
            )

        struct = MusicStructure(
            id=uuid4(),
            name=name,
            content=content,
            match_key=match_key.strip() if match_key else None,
        )

        created = await self._prompt_repo.create_structure(struct)
        logger.info("Created structure '%s' (id=%s).", name, created.id)
        return created

    async def update_structure(
        self, struct_id: UUID, **fields: Any
    ) -> MusicStructure:
        """Update an existing song structure.

        Validates any changed fields. If name is changed, checks uniqueness.
        Clearing match_key dissociates from pairings.

        Args:
            struct_id: The UUID of the structure to update.
            **fields: Fields to update (name, content, match_key).

        Returns:
            The updated MusicStructure.

        Raises:
            NotFoundError: If the structure does not exist.
            ValidationError: If name or content validation fails.
            DuplicateError: If the new name conflicts with another.
        """
        # Validate name if provided
        if "name" in fields:
            fields["name"] = self._validate_name(fields["name"], "structure")
            # Check uniqueness of new name
            existing = await self._prompt_repo.get_structure_by_name(fields["name"])
            if existing is not None and existing.id != struct_id:
                raise DuplicateError(
                    f"A structure named '{fields['name']}' already exists.",
                    details={"name": fields["name"]},
                )

        # Validate content if provided
        if "content" in fields:
            fields["content"] = self._validate_content(fields["content"], "structure")

        # Normalize match_key
        if "match_key" in fields:
            mk = fields["match_key"]
            fields["match_key"] = mk.strip() if mk else None

        updated = await self._prompt_repo.update_structure(struct_id, **fields)
        if updated is None:
            raise NotFoundError(
                f"Structure {struct_id} not found.",
                details={"structure_id": str(struct_id)},
            )

        logger.info("Updated structure %s.", struct_id)
        return updated

    async def delete_structure(self, struct_id: UUID) -> None:
        """Delete a song structure.

        Removes the structure and dissociates it from any match key
        pairings and songs.

        Args:
            struct_id: The UUID of the structure to delete.

        Raises:
            NotFoundError: If the structure does not exist.
        """
        deleted = await self._prompt_repo.delete_structure(struct_id)
        if not deleted:
            raise NotFoundError(
                f"Structure {struct_id} not found.",
                details={"structure_id": str(struct_id)},
            )
        logger.info("Deleted structure %s.", struct_id)

    async def get_structure(self, struct_id: UUID) -> MusicStructure:
        """Get a structure by ID.

        Args:
            struct_id: The UUID of the structure.

        Returns:
            The MusicStructure.

        Raises:
            NotFoundError: If the structure does not exist.
        """
        struct = await self._prompt_repo.get_structure_by_id(struct_id)
        if struct is None:
            raise NotFoundError(
                f"Structure {struct_id} not found.",
                details={"structure_id": str(struct_id)},
            )
        return struct

    async def list_structures(self) -> list[MusicStructure]:
        """List all structures ordered by name ascending."""
        return await self._prompt_repo.list_structures()

    # -----------------------------------------------------------------------
    # matchKey Pairing Logic (Requirement 9.6)
    # -----------------------------------------------------------------------

    async def get_matched_pairs(
        self,
    ) -> list[tuple[MusicDescription, MusicStructure]]:
        """Get description-structure pairs matched by matchKey.

        Pairs descriptions with structures where both share the same matchKey
        value. Descriptions or structures with a matchKey that has no
        corresponding counterpart are skipped and a warning is logged.

        Returns:
            List of (description, structure) tuples paired by matchKey.
        """
        descriptions = await self._prompt_repo.get_descriptions_with_match_key()
        structures = await self._prompt_repo.get_structures_with_match_key()

        # Build lookup maps by match_key
        desc_by_key: dict[str, list[MusicDescription]] = {}
        for d in descriptions:
            if d.match_key:
                desc_by_key.setdefault(d.match_key, []).append(d)

        struct_by_key: dict[str, list[MusicStructure]] = {}
        for s in structures:
            if s.match_key:
                struct_by_key.setdefault(s.match_key, []).append(s)

        # Build pairs — only where both sides exist
        pairs: list[tuple[MusicDescription, MusicStructure]] = []
        all_keys = set(desc_by_key.keys()) | set(struct_by_key.keys())

        for key in sorted(all_keys):
            descs = desc_by_key.get(key, [])
            structs = struct_by_key.get(key, [])

            if not descs:
                for s in structs:
                    logger.warning(
                        "Structure '%s' (match_key='%s') has no matching description; skipping.",
                        s.name,
                        key,
                    )
                continue

            if not structs:
                for d in descs:
                    logger.warning(
                        "Description '%s' (match_key='%s') has no matching structure; skipping.",
                        d.name,
                        key,
                    )
                continue

            # Pair each description with each structure sharing the same key
            for d in descs:
                for s in structs:
                    pairs.append((d, s))

        return pairs

    # -----------------------------------------------------------------------
    # Cyclic / Shuffle Structure Assignment (Requirement 9.7)
    # -----------------------------------------------------------------------

    @staticmethod
    def assign_structures_cycle(
        structures: list[MusicStructure],
        song_count: int,
    ) -> list[MusicStructure]:
        """Assign structures to songs in cyclic (sequential wrapping) order.

        Structures are assigned sequentially to songs in batch order,
        wrapping to the first structure after the last is used.

        Args:
            structures: The list of available structures.
            song_count: The number of songs in the batch.

        Returns:
            List of structures assigned to each song index.

        Raises:
            ValidationError: If structures list is empty.
        """
        if not structures:
            raise ValidationError(
                "Cannot assign structures: no structures available.",
                details={"structures_count": 0},
            )
        return [structures[i % len(structures)] for i in range(song_count)]

    @staticmethod
    def assign_structures_shuffle(
        structures: list[MusicStructure],
        song_count: int,
        batch_id: UUID,
    ) -> list[MusicStructure]:
        """Assign structures in shuffled order using a seeded random per Batch.

        Randomizes the assignment order using a seeded random generator
        per Batch (deterministic for reproducibility). Every structure
        appears before any structure repeats within each full cycle.

        Args:
            structures: The list of available structures.
            song_count: The number of songs in the batch.
            batch_id: The batch UUID used as the random seed.

        Returns:
            List of structures assigned to each song index.

        Raises:
            ValidationError: If structures list is empty.
        """
        if not structures:
            raise ValidationError(
                "Cannot assign structures: no structures available.",
                details={"structures_count": 0},
            )

        # Use batch_id as seed for deterministic shuffling
        rng = random.Random(str(batch_id))
        n = len(structures)
        assignments: list[MusicStructure] = []

        # Build full cycles of shuffled structures
        while len(assignments) < song_count:
            # Create a new shuffled cycle
            cycle = list(structures)
            rng.shuffle(cycle)
            assignments.extend(cycle)

        return assignments[:song_count]
