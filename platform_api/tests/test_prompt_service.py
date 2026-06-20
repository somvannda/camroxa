"""Unit tests for PromptService.

Tests CRUD operations for music descriptions and structures,
matchKey pairing logic, and cycle/shuffle structure assignment.

Requirements: 9.1, 9.2, 9.3, 9.6, 9.7
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.models.domain import MusicDescription, MusicStructure
from platform_api.services.prompt_service import PromptService


# ---------------------------------------------------------------------------
# Fakes / In-memory implementations
# ---------------------------------------------------------------------------


class FakePromptRepository:
    """In-memory prompt repository for testing."""

    def __init__(self) -> None:
        self._descriptions: dict[UUID, MusicDescription] = {}
        self._structures: dict[UUID, MusicStructure] = {}

    # --- Descriptions ---

    async def create_description(self, desc: MusicDescription) -> MusicDescription:
        desc.created_at = datetime.now(timezone.utc)
        desc.updated_at = datetime.now(timezone.utc)
        self._descriptions[desc.id] = desc
        return desc

    async def get_description_by_id(self, desc_id: UUID) -> MusicDescription | None:
        return self._descriptions.get(desc_id)

    async def get_description_by_name(self, name: str) -> MusicDescription | None:
        for d in self._descriptions.values():
            if d.name == name:
                return d
        return None

    async def list_descriptions(self) -> list[MusicDescription]:
        return sorted(self._descriptions.values(), key=lambda d: d.name)

    async def update_description(
        self, desc_id: UUID, **fields
    ) -> MusicDescription | None:
        desc = self._descriptions.get(desc_id)
        if desc is None:
            return None
        for key, val in fields.items():
            if hasattr(desc, key):
                setattr(desc, key, val)
        desc.updated_at = datetime.now(timezone.utc)
        return desc

    async def delete_description(self, desc_id: UUID) -> bool:
        if desc_id in self._descriptions:
            del self._descriptions[desc_id]
            return True
        return False

    # --- Structures ---

    async def create_structure(self, struct: MusicStructure) -> MusicStructure:
        struct.created_at = datetime.now(timezone.utc)
        struct.updated_at = datetime.now(timezone.utc)
        self._structures[struct.id] = struct
        return struct

    async def get_structure_by_id(self, struct_id: UUID) -> MusicStructure | None:
        return self._structures.get(struct_id)

    async def get_structure_by_name(self, name: str) -> MusicStructure | None:
        for s in self._structures.values():
            if s.name == name:
                return s
        return None

    async def list_structures(self) -> list[MusicStructure]:
        return sorted(self._structures.values(), key=lambda s: s.name)

    async def update_structure(
        self, struct_id: UUID, **fields
    ) -> MusicStructure | None:
        struct = self._structures.get(struct_id)
        if struct is None:
            return None
        for key, val in fields.items():
            if hasattr(struct, key):
                setattr(struct, key, val)
        struct.updated_at = datetime.now(timezone.utc)
        return struct

    async def delete_structure(self, struct_id: UUID) -> bool:
        if struct_id in self._structures:
            del self._structures[struct_id]
            return True
        return False

    # --- matchKey lookups ---

    async def get_descriptions_with_match_key(self) -> list[MusicDescription]:
        return [d for d in self._descriptions.values() if d.match_key is not None]

    async def get_structures_with_match_key(self) -> list[MusicStructure]:
        return [s for s in self._structures.values() if s.match_key is not None]

    async def get_matched_pairs(
        self,
    ) -> list[tuple[MusicDescription, MusicStructure]]:
        desc_by_key: dict[str, list[MusicDescription]] = {}
        for d in self._descriptions.values():
            if d.match_key:
                desc_by_key.setdefault(d.match_key, []).append(d)

        struct_by_key: dict[str, list[MusicStructure]] = {}
        for s in self._structures.values():
            if s.match_key:
                struct_by_key.setdefault(s.match_key, []).append(s)

        pairs = []
        for key in sorted(set(desc_by_key.keys()) & set(struct_by_key.keys())):
            for d in desc_by_key[key]:
                for s in struct_by_key[key]:
                    pairs.append((d, s))
        return pairs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def prompt_repo() -> FakePromptRepository:
    return FakePromptRepository()


@pytest.fixture
def service(prompt_repo: FakePromptRepository) -> PromptService:
    return PromptService(prompt_repo=prompt_repo)


# ---------------------------------------------------------------------------
# Tests: Description CRUD
# ---------------------------------------------------------------------------


class TestCreateDescription:
    """Tests for PromptService.create_description."""

    async def test_creates_valid_description(self, service: PromptService) -> None:
        result = await service.create_description(
            name="Chill Vibes",
            content="A relaxed genre with smooth beats and mellow energy.",
        )
        assert result.name == "Chill Vibes"
        assert result.content == "A relaxed genre with smooth beats and mellow energy."
        assert result.match_key is None

    async def test_creates_description_with_match_key(self, service: PromptService) -> None:
        result = await service.create_description(
            name="Energetic Pop",
            content="High energy pop with upbeat tempo.",
            match_key="pop-energy",
        )
        assert result.match_key == "pop-energy"

    async def test_rejects_empty_name(self, service: PromptService) -> None:
        with pytest.raises(ValidationError, match="name is required"):
            await service.create_description(name="", content="Some content")

    async def test_rejects_name_too_long(self, service: PromptService) -> None:
        with pytest.raises(ValidationError, match="100 characters"):
            await service.create_description(name="x" * 101, content="Some content")

    async def test_rejects_empty_content(self, service: PromptService) -> None:
        with pytest.raises(ValidationError, match="content is required"):
            await service.create_description(name="Valid Name", content="")

    async def test_rejects_content_too_long(self, service: PromptService) -> None:
        with pytest.raises(ValidationError, match="5000 characters"):
            await service.create_description(name="Valid Name", content="x" * 5001)

    async def test_rejects_duplicate_name(self, service: PromptService) -> None:
        await service.create_description(name="Unique", content="Content one")
        with pytest.raises(DuplicateError, match="already exists"):
            await service.create_description(name="Unique", content="Content two")

    async def test_strips_name(self, service: PromptService) -> None:
        result = await service.create_description(name="  Padded  ", content="Content")
        assert result.name == "Padded"


class TestUpdateDescription:
    """Tests for PromptService.update_description."""

    async def test_updates_content(self, service: PromptService) -> None:
        created = await service.create_description(name="Original", content="Old content")
        updated = await service.update_description(created.id, content="New content")
        assert updated.content == "New content"

    async def test_updates_name(self, service: PromptService) -> None:
        created = await service.create_description(name="OldName", content="Content")
        updated = await service.update_description(created.id, name="NewName")
        assert updated.name == "NewName"

    async def test_rejects_duplicate_name_on_update(self, service: PromptService) -> None:
        await service.create_description(name="First", content="Content 1")
        second = await service.create_description(name="Second", content="Content 2")
        with pytest.raises(DuplicateError, match="already exists"):
            await service.update_description(second.id, name="First")

    async def test_raises_not_found(self, service: PromptService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.update_description(uuid4(), content="x")

    async def test_clears_match_key(self, service: PromptService) -> None:
        created = await service.create_description(
            name="WithKey", content="Content", match_key="old-key"
        )
        updated = await service.update_description(created.id, match_key=None)
        assert updated.match_key is None


class TestDeleteDescription:
    """Tests for PromptService.delete_description."""

    async def test_deletes_existing(self, service: PromptService) -> None:
        created = await service.create_description(name="ToDelete", content="Content")
        await service.delete_description(created.id)
        with pytest.raises(NotFoundError):
            await service.get_description(created.id)

    async def test_raises_not_found(self, service: PromptService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.delete_description(uuid4())


class TestListDescriptions:
    """Tests for PromptService.list_descriptions."""

    async def test_returns_ordered_by_name(self, service: PromptService) -> None:
        await service.create_description(name="Zen", content="Content")
        await service.create_description(name="Alpha", content="Content")
        await service.create_description(name="Mid", content="Content")

        result = await service.list_descriptions()
        names = [d.name for d in result]
        assert names == ["Alpha", "Mid", "Zen"]


# ---------------------------------------------------------------------------
# Tests: Structure CRUD
# ---------------------------------------------------------------------------


class TestCreateStructure:
    """Tests for PromptService.create_structure."""

    async def test_creates_valid_structure(self, service: PromptService) -> None:
        result = await service.create_structure(
            name="Pop Structure",
            content="[Verse]\n[Chorus]\n[Verse]\n[Chorus]\n[Bridge]\n[Chorus]",
        )
        assert result.name == "Pop Structure"
        assert "[Verse]" in result.content

    async def test_creates_structure_with_match_key(self, service: PromptService) -> None:
        result = await service.create_structure(
            name="Rock Structure",
            content="[Intro]\n[Verse]\n[Chorus]",
            match_key="rock-energy",
        )
        assert result.match_key == "rock-energy"

    async def test_rejects_empty_name(self, service: PromptService) -> None:
        with pytest.raises(ValidationError, match="name is required"):
            await service.create_structure(name="", content="Content")

    async def test_rejects_duplicate_name(self, service: PromptService) -> None:
        await service.create_structure(name="Unique", content="Content one")
        with pytest.raises(DuplicateError, match="already exists"):
            await service.create_structure(name="Unique", content="Content two")


class TestUpdateStructure:
    """Tests for PromptService.update_structure."""

    async def test_updates_content(self, service: PromptService) -> None:
        created = await service.create_structure(name="Original", content="Old")
        updated = await service.update_structure(created.id, content="New content")
        assert updated.content == "New content"

    async def test_raises_not_found(self, service: PromptService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.update_structure(uuid4(), content="x")


class TestDeleteStructure:
    """Tests for PromptService.delete_structure."""

    async def test_deletes_existing(self, service: PromptService) -> None:
        created = await service.create_structure(name="ToDelete", content="Content")
        await service.delete_structure(created.id)
        with pytest.raises(NotFoundError):
            await service.get_structure(created.id)

    async def test_raises_not_found(self, service: PromptService) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await service.delete_structure(uuid4())


# ---------------------------------------------------------------------------
# Tests: matchKey Pairing (Requirement 9.6)
# ---------------------------------------------------------------------------


class TestMatchKeyPairing:
    """Tests for PromptService.get_matched_pairs."""

    async def test_pairs_matching_keys(
        self, service: PromptService, prompt_repo: FakePromptRepository
    ) -> None:
        desc = MusicDescription(
            id=uuid4(), name="Pop Desc", content="Pop genre", match_key="pop"
        )
        struct = MusicStructure(
            id=uuid4(), name="Pop Struct", content="[Verse][Chorus]", match_key="pop"
        )
        prompt_repo._descriptions[desc.id] = desc
        prompt_repo._structures[struct.id] = struct

        pairs = await service.get_matched_pairs()
        assert len(pairs) == 1
        assert pairs[0][0].match_key == "pop"
        assert pairs[0][1].match_key == "pop"

    async def test_skips_unmatched_descriptions(
        self, service: PromptService, prompt_repo: FakePromptRepository
    ) -> None:
        desc = MusicDescription(
            id=uuid4(), name="Orphan Desc", content="No match", match_key="orphan"
        )
        prompt_repo._descriptions[desc.id] = desc

        pairs = await service.get_matched_pairs()
        assert len(pairs) == 0

    async def test_skips_unmatched_structures(
        self, service: PromptService, prompt_repo: FakePromptRepository
    ) -> None:
        struct = MusicStructure(
            id=uuid4(), name="Orphan Struct", content="[Verse]", match_key="orphan"
        )
        prompt_repo._structures[struct.id] = struct

        pairs = await service.get_matched_pairs()
        assert len(pairs) == 0

    async def test_multiple_pairs_same_key(
        self, service: PromptService, prompt_repo: FakePromptRepository
    ) -> None:
        desc1 = MusicDescription(
            id=uuid4(), name="D1", content="Content", match_key="shared"
        )
        desc2 = MusicDescription(
            id=uuid4(), name="D2", content="Content", match_key="shared"
        )
        struct = MusicStructure(
            id=uuid4(), name="S1", content="[Verse]", match_key="shared"
        )
        prompt_repo._descriptions[desc1.id] = desc1
        prompt_repo._descriptions[desc2.id] = desc2
        prompt_repo._structures[struct.id] = struct

        pairs = await service.get_matched_pairs()
        assert len(pairs) == 2

    async def test_ignores_null_match_keys(
        self, service: PromptService, prompt_repo: FakePromptRepository
    ) -> None:
        desc = MusicDescription(
            id=uuid4(), name="NoKey", content="Content", match_key=None
        )
        struct = MusicStructure(
            id=uuid4(), name="NoKey", content="[Verse]", match_key=None
        )
        prompt_repo._descriptions[desc.id] = desc
        prompt_repo._structures[struct.id] = struct

        pairs = await service.get_matched_pairs()
        assert len(pairs) == 0


# ---------------------------------------------------------------------------
# Tests: Cyclic Structure Assignment (Requirement 9.7)
# ---------------------------------------------------------------------------


class TestCycleStructureAssignment:
    """Tests for PromptService.assign_structures_cycle."""

    def test_cycles_through_structures(self) -> None:
        structures = [
            MusicStructure(id=uuid4(), name=f"S{i}", content=f"[V{i}]")
            for i in range(3)
        ]
        result = PromptService.assign_structures_cycle(structures, song_count=7)

        assert len(result) == 7
        assert result[0].name == "S0"
        assert result[1].name == "S1"
        assert result[2].name == "S2"
        assert result[3].name == "S0"  # wraps around
        assert result[4].name == "S1"
        assert result[5].name == "S2"
        assert result[6].name == "S0"

    def test_single_structure_repeats(self) -> None:
        structures = [MusicStructure(id=uuid4(), name="Only", content="[Verse]")]
        result = PromptService.assign_structures_cycle(structures, song_count=5)

        assert len(result) == 5
        assert all(s.name == "Only" for s in result)

    def test_exact_fit(self) -> None:
        structures = [
            MusicStructure(id=uuid4(), name=f"S{i}", content=f"[V{i}]")
            for i in range(4)
        ]
        result = PromptService.assign_structures_cycle(structures, song_count=4)

        assert len(result) == 4
        assert [s.name for s in result] == ["S0", "S1", "S2", "S3"]

    def test_empty_structures_raises(self) -> None:
        with pytest.raises(ValidationError, match="no structures available"):
            PromptService.assign_structures_cycle([], song_count=3)


# ---------------------------------------------------------------------------
# Tests: Shuffle Structure Assignment (Requirement 9.7)
# ---------------------------------------------------------------------------


class TestShuffleStructureAssignment:
    """Tests for PromptService.assign_structures_shuffle."""

    def test_deterministic_with_same_batch_id(self) -> None:
        structures = [
            MusicStructure(id=uuid4(), name=f"S{i}", content=f"[V{i}]")
            for i in range(5)
        ]
        batch_id = uuid4()

        result1 = PromptService.assign_structures_shuffle(structures, 10, batch_id)
        result2 = PromptService.assign_structures_shuffle(structures, 10, batch_id)

        assert [s.name for s in result1] == [s.name for s in result2]

    def test_different_batch_ids_produce_different_orders(self) -> None:
        structures = [
            MusicStructure(id=uuid4(), name=f"S{i}", content=f"[V{i}]")
            for i in range(5)
        ]
        batch_id_1 = uuid4()
        batch_id_2 = uuid4()

        result1 = PromptService.assign_structures_shuffle(structures, 10, batch_id_1)
        result2 = PromptService.assign_structures_shuffle(structures, 10, batch_id_2)

        # While theoretically they could be the same, it's extremely unlikely
        names1 = [s.name for s in result1]
        names2 = [s.name for s in result2]
        # At least one position should differ (probabilistic but safe)
        assert names1 != names2 or len(structures) == 1

    def test_every_structure_appears_before_repeat_in_cycle(self) -> None:
        structures = [
            MusicStructure(id=uuid4(), name=f"S{i}", content=f"[V{i}]")
            for i in range(4)
        ]
        batch_id = uuid4()
        result = PromptService.assign_structures_shuffle(structures, 8, batch_id)

        # First cycle (indices 0-3) should contain all structures
        first_cycle_names = {s.name for s in result[:4]}
        assert first_cycle_names == {"S0", "S1", "S2", "S3"}

        # Second cycle (indices 4-7) should also contain all structures
        second_cycle_names = {s.name for s in result[4:8]}
        assert second_cycle_names == {"S0", "S1", "S2", "S3"}

    def test_correct_length(self) -> None:
        structures = [
            MusicStructure(id=uuid4(), name=f"S{i}", content=f"[V{i}]")
            for i in range(3)
        ]
        batch_id = uuid4()
        result = PromptService.assign_structures_shuffle(structures, 5, batch_id)
        assert len(result) == 5

    def test_empty_structures_raises(self) -> None:
        with pytest.raises(ValidationError, match="no structures available"):
            PromptService.assign_structures_shuffle([], song_count=3, batch_id=uuid4())

    def test_single_structure(self) -> None:
        structures = [MusicStructure(id=uuid4(), name="Only", content="[Verse]")]
        batch_id = uuid4()
        result = PromptService.assign_structures_shuffle(structures, 5, batch_id)

        assert len(result) == 5
        assert all(s.name == "Only" for s in result)
