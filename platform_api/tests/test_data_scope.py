"""Unit tests for user-scoped data isolation.

Tests that User-role requests only return records belonging to the
authenticated user, and Admin-role requests bypass scoping.

Requirements: 16.1, 16.2
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.middleware.auth import AuthContext
from platform_api.models.domain import Batch, ChannelProfile, Song, SunoTask
from platform_api.models.enums import TaskStatus
from platform_api.services.data_scope_service import DataScopeService


# ---------------------------------------------------------------------------
# Helpers: Create AuthContext for User and Admin
# ---------------------------------------------------------------------------


def make_user_ctx(user_id: str | None = None) -> AuthContext:
    """Create a User-role AuthContext."""
    return AuthContext(
        user_id=user_id or str(uuid4()),
        email="user@example.com",
        role="user",
    )


def make_admin_ctx(user_id: str | None = None) -> AuthContext:
    """Create an Admin-role AuthContext."""
    return AuthContext(
        user_id=user_id or str(uuid4()),
        email="admin@example.com",
        role="admin",
    )


# ---------------------------------------------------------------------------
# Fake Repositories
# ---------------------------------------------------------------------------


class FakeBatchRepo:
    """In-memory batch repository for testing data isolation."""

    def __init__(self) -> None:
        self._batches: dict[UUID, Batch] = {}
        self._songs: dict[UUID, Song] = {}
        self._suno_tasks: dict[UUID, SunoTask] = {}

    def add_batch(self, batch: Batch) -> None:
        self._batches[batch.id] = batch

    def add_song(self, song: Song) -> None:
        self._songs[song.id] = song

    def add_suno_task(self, task: SunoTask) -> None:
        self._suno_tasks[task.id] = task

    async def get_batch_by_id(self, batch_id: UUID) -> Batch | None:
        return self._batches.get(batch_id)

    async def get_batch_for_user(self, batch_id: UUID, user_id: UUID) -> Batch | None:
        batch = self._batches.get(batch_id)
        if batch and batch.user_id == user_id:
            return batch
        return None

    async def list_batches_for_user(self, user_id: UUID) -> list[Batch]:
        return [b for b in self._batches.values() if b.user_id == user_id]

    async def list_all_batches(self) -> list[Batch]:
        return list(self._batches.values())

    async def get_songs_by_batch(self, batch_id: UUID) -> list[Song]:
        return [s for s in self._songs.values() if s.batch_id == batch_id]

    async def get_songs_for_user(self, user_id: UUID) -> list[Song]:
        return [s for s in self._songs.values() if s.user_id == user_id]

    async def get_songs_for_user_batch(self, batch_id: UUID, user_id: UUID) -> list[Song]:
        return [
            s for s in self._songs.values()
            if s.batch_id == batch_id and s.user_id == user_id
        ]

    async def get_suno_task_by_id(self, task_id: UUID) -> SunoTask | None:
        return self._suno_tasks.get(task_id)

    async def get_suno_task_for_user(self, task_id: UUID, user_id: UUID) -> SunoTask | None:
        task = self._suno_tasks.get(task_id)
        if task and task.user_id == user_id:
            return task
        return None

    async def get_suno_tasks_for_user(self, user_id: UUID) -> list[SunoTask]:
        return [t for t in self._suno_tasks.values() if t.user_id == user_id]

    async def get_suno_tasks_by_batch(self, batch_id: UUID) -> list[SunoTask]:
        return [t for t in self._suno_tasks.values() if t.batch_id == batch_id]


class FakeProfileRepo:
    """In-memory profile repository for testing data isolation."""

    def __init__(self) -> None:
        self._profiles: dict[UUID, ChannelProfile] = {}

    def add_profile(self, profile: ChannelProfile) -> None:
        self._profiles[profile.id] = profile

    async def get_by_id(self, profile_id: UUID) -> ChannelProfile | None:
        return self._profiles.get(profile_id)

    async def get_by_id_for_user(self, profile_id: UUID, user_id: UUID) -> ChannelProfile | None:
        profile = self._profiles.get(profile_id)
        if profile and profile.user_id == user_id:
            return profile
        return None

    async def list_for_user(self, user_id: UUID) -> list[ChannelProfile]:
        return [p for p in self._profiles.values() if p.user_id == user_id]


class FakeSettingsRepo:
    """In-memory settings repository for testing data isolation."""

    def __init__(self) -> None:
        self._settings: dict[UUID, dict[str, Any]] = {}

    def add_settings(self, user_id: UUID, settings: dict[str, Any]) -> None:
        self._settings[user_id] = settings

    async def get_user_settings(self, user_id: UUID) -> dict[str, Any]:
        return self._settings.get(user_id, {})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_a_id() -> UUID:
    return uuid4()


@pytest.fixture
def user_b_id() -> UUID:
    return uuid4()


@pytest.fixture
def batch_repo(user_a_id: UUID, user_b_id: UUID) -> FakeBatchRepo:
    """Create a batch repo with data from two users."""
    repo = FakeBatchRepo()

    # User A's batch
    batch_a = Batch(
        id=uuid4(),
        user_id=user_a_id,
        ok_profile_id=uuid4(),
        alt_profile_id=uuid4(),
        song_count=2,
        language="en",
        creativity_level=50,
        pairing_mode="match_key",
        status="completed",
    )
    repo.add_batch(batch_a)

    # User B's batch
    batch_b = Batch(
        id=uuid4(),
        user_id=user_b_id,
        ok_profile_id=uuid4(),
        alt_profile_id=uuid4(),
        song_count=3,
        language="en",
        creativity_level=50,
        pairing_mode="match_key",
        status="processing",
    )
    repo.add_batch(batch_b)

    # Songs for user A's batch
    song_a = Song(
        id=uuid4(),
        batch_id=batch_a.id,
        batch_index=0,
        user_id=user_a_id,
        title="Song A",
        album="Album A",
        lyrics="Lyrics A",
        status="suno_success",
    )
    repo.add_song(song_a)

    # Songs for user B's batch
    song_b = Song(
        id=uuid4(),
        batch_id=batch_b.id,
        batch_index=0,
        user_id=user_b_id,
        title="Song B",
        album="Album B",
        lyrics="Lyrics B",
        status="pending",
    )
    repo.add_song(song_b)

    # Suno task for user A
    task_a = SunoTask(
        id=uuid4(),
        song_id=song_a.id,
        user_id=user_a_id,
        batch_id=batch_a.id,
        request_hash="hash_a",
        model="V5",
        title="Song A",
        lyrics="Lyrics A",
        style="pop",
        instrumental=False,
        status=TaskStatus.SUCCESS,
    )
    repo.add_suno_task(task_a)

    # Suno task for user B
    task_b = SunoTask(
        id=uuid4(),
        song_id=song_b.id,
        user_id=user_b_id,
        batch_id=batch_b.id,
        request_hash="hash_b",
        model="V5_5",
        title="Song B",
        lyrics="Lyrics B",
        style="rock",
        instrumental=False,
        status=TaskStatus.PENDING,
    )
    repo.add_suno_task(task_b)

    return repo


@pytest.fixture
def profile_repo(user_a_id: UUID, user_b_id: UUID) -> FakeProfileRepo:
    """Create a profile repo with data from two users."""
    repo = FakeProfileRepo()

    profile_a = ChannelProfile(
        id=uuid4(),
        user_id=user_a_id,
        name="Profile A",
        output_resolution="1920x1080",
        image_config={},
        youtube_config={},
    )
    repo.add_profile(profile_a)

    profile_b = ChannelProfile(
        id=uuid4(),
        user_id=user_b_id,
        name="Profile B",
        output_resolution="1920x1080",
        image_config={},
        youtube_config={},
    )
    repo.add_profile(profile_b)

    return repo


@pytest.fixture
def settings_repo(user_a_id: UUID, user_b_id: UUID) -> FakeSettingsRepo:
    """Create a settings repo with data from two users."""
    repo = FakeSettingsRepo()
    repo.add_settings(user_a_id, {"theme": "dark", "language": "en"})
    repo.add_settings(user_b_id, {"theme": "light", "language": "fr"})
    return repo


@pytest.fixture
def scope_service(
    batch_repo: FakeBatchRepo,
    profile_repo: FakeProfileRepo,
    settings_repo: FakeSettingsRepo,
) -> DataScopeService:
    """Create the DataScopeService with fake repositories."""
    return DataScopeService(
        batch_repo=batch_repo,
        profile_repo=profile_repo,
        settings_repo=settings_repo,
    )


# ---------------------------------------------------------------------------
# Tests: Batch Isolation
# ---------------------------------------------------------------------------


class TestBatchIsolation:
    """Tests that batch access is properly scoped by user role."""

    @pytest.mark.asyncio
    async def test_user_can_only_see_own_batches(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_a_id: UUID,
    ) -> None:
        """User-role request only returns batches belonging to that user."""
        ctx = make_user_ctx(str(user_a_id))
        batches = await scope_service.list_batches(ctx)

        assert len(batches) == 1
        assert all(b.user_id == user_a_id for b in batches)

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_batch(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_a_id: UUID,
        user_b_id: UUID,
    ) -> None:
        """User-role request cannot access a batch belonging to another user."""
        ctx = make_user_ctx(str(user_a_id))

        # Get user B's batch ID
        b_batches = [b for b in batch_repo._batches.values() if b.user_id == user_b_id]
        assert len(b_batches) == 1
        b_batch_id = b_batches[0].id

        result = await scope_service.get_batch(b_batch_id, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_admin_can_see_all_batches(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
    ) -> None:
        """Admin-role request returns all batches without scoping."""
        ctx = make_admin_ctx()
        batches = await scope_service.list_batches(ctx)

        assert len(batches) == 2  # Both user A and user B batches

    @pytest.mark.asyncio
    async def test_admin_can_access_any_batch(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_b_id: UUID,
    ) -> None:
        """Admin-role request can access any user's batch."""
        ctx = make_admin_ctx()

        # Get user B's batch ID
        b_batches = [b for b in batch_repo._batches.values() if b.user_id == user_b_id]
        b_batch_id = b_batches[0].id

        result = await scope_service.get_batch(b_batch_id, ctx)
        assert result is not None
        assert result.user_id == user_b_id


# ---------------------------------------------------------------------------
# Tests: Song Isolation
# ---------------------------------------------------------------------------


class TestSongIsolation:
    """Tests that song access is properly scoped by user role."""

    @pytest.mark.asyncio
    async def test_user_can_only_see_own_songs_in_batch(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_a_id: UUID,
    ) -> None:
        """User-role request only returns songs from their own batches."""
        ctx = make_user_ctx(str(user_a_id))

        # Get user A's batch
        a_batches = [b for b in batch_repo._batches.values() if b.user_id == user_a_id]
        batch_id = a_batches[0].id

        songs = await scope_service.get_songs_for_batch(batch_id, ctx)
        assert len(songs) == 1
        assert all(s.user_id == user_a_id for s in songs)

    @pytest.mark.asyncio
    async def test_user_cannot_see_songs_from_other_users_batch(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_a_id: UUID,
        user_b_id: UUID,
    ) -> None:
        """User-role request returns empty for another user's batch songs."""
        ctx = make_user_ctx(str(user_a_id))

        # Get user B's batch
        b_batches = [b for b in batch_repo._batches.values() if b.user_id == user_b_id]
        batch_id = b_batches[0].id

        songs = await scope_service.get_songs_for_batch(batch_id, ctx)
        assert len(songs) == 0

    @pytest.mark.asyncio
    async def test_admin_can_see_songs_from_any_batch(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_b_id: UUID,
    ) -> None:
        """Admin-role request can see songs from any user's batch."""
        ctx = make_admin_ctx()

        # Get user B's batch
        b_batches = [b for b in batch_repo._batches.values() if b.user_id == user_b_id]
        batch_id = b_batches[0].id

        songs = await scope_service.get_songs_for_batch(batch_id, ctx)
        assert len(songs) == 1
        assert songs[0].user_id == user_b_id


# ---------------------------------------------------------------------------
# Tests: Suno Task Isolation
# ---------------------------------------------------------------------------


class TestSunoTaskIsolation:
    """Tests that Suno task access is properly scoped by user role."""

    @pytest.mark.asyncio
    async def test_user_can_only_see_own_suno_tasks(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_a_id: UUID,
    ) -> None:
        """User-role request only returns Suno tasks belonging to that user."""
        ctx = make_user_ctx(str(user_a_id))
        tasks = await scope_service.list_suno_tasks(ctx)

        assert len(tasks) == 1
        assert all(t.user_id == user_a_id for t in tasks)

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_suno_task(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_a_id: UUID,
        user_b_id: UUID,
    ) -> None:
        """User-role request cannot access a Suno task belonging to another user."""
        ctx = make_user_ctx(str(user_a_id))

        # Get user B's task ID
        b_tasks = [t for t in batch_repo._suno_tasks.values() if t.user_id == user_b_id]
        assert len(b_tasks) == 1
        b_task_id = b_tasks[0].id

        result = await scope_service.get_suno_task(b_task_id, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_admin_can_access_any_suno_task(
        self,
        scope_service: DataScopeService,
        batch_repo: FakeBatchRepo,
        user_b_id: UUID,
    ) -> None:
        """Admin-role request can access any user's Suno task."""
        ctx = make_admin_ctx()

        # Get user B's task ID
        b_tasks = [t for t in batch_repo._suno_tasks.values() if t.user_id == user_b_id]
        b_task_id = b_tasks[0].id

        result = await scope_service.get_suno_task(b_task_id, ctx)
        assert result is not None
        assert result.user_id == user_b_id


# ---------------------------------------------------------------------------
# Tests: Profile Isolation
# ---------------------------------------------------------------------------


class TestProfileIsolation:
    """Tests that profile access is properly scoped by user role."""

    @pytest.mark.asyncio
    async def test_user_can_only_see_own_profiles(
        self,
        scope_service: DataScopeService,
        profile_repo: FakeProfileRepo,
        user_a_id: UUID,
    ) -> None:
        """User-role request only returns profiles belonging to that user."""
        ctx = make_user_ctx(str(user_a_id))
        profiles = await scope_service.list_profiles(ctx)

        assert len(profiles) == 1
        assert all(p.user_id == user_a_id for p in profiles)

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_profile(
        self,
        scope_service: DataScopeService,
        profile_repo: FakeProfileRepo,
        user_a_id: UUID,
        user_b_id: UUID,
    ) -> None:
        """User-role request cannot access a profile belonging to another user."""
        ctx = make_user_ctx(str(user_a_id))

        # Get user B's profile ID
        b_profiles = [p for p in profile_repo._profiles.values() if p.user_id == user_b_id]
        assert len(b_profiles) == 1
        b_profile_id = b_profiles[0].id

        result = await scope_service.get_profile(b_profile_id, ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_admin_can_access_any_profile(
        self,
        scope_service: DataScopeService,
        profile_repo: FakeProfileRepo,
        user_b_id: UUID,
    ) -> None:
        """Admin-role request can access any user's profile."""
        ctx = make_admin_ctx()

        # Get user B's profile ID
        b_profiles = [p for p in profile_repo._profiles.values() if p.user_id == user_b_id]
        b_profile_id = b_profiles[0].id

        result = await scope_service.get_profile(b_profile_id, ctx)
        assert result is not None
        assert result.user_id == user_b_id


# ---------------------------------------------------------------------------
# Tests: Settings Isolation
# ---------------------------------------------------------------------------


class TestSettingsIsolation:
    """Tests that settings access is always scoped to the authenticated user."""

    @pytest.mark.asyncio
    async def test_user_only_gets_own_settings(
        self,
        scope_service: DataScopeService,
        settings_repo: FakeSettingsRepo,
        user_a_id: UUID,
    ) -> None:
        """User-role request returns only their own settings."""
        ctx = make_user_ctx(str(user_a_id))
        settings = await scope_service.get_settings(ctx)

        assert settings == {"theme": "dark", "language": "en"}

    @pytest.mark.asyncio
    async def test_admin_gets_own_settings_not_all(
        self,
        scope_service: DataScopeService,
        settings_repo: FakeSettingsRepo,
        user_a_id: UUID,
    ) -> None:
        """Admin-role request also returns their own settings (not all users')."""
        # Admin context with user_a's ID
        ctx = make_admin_ctx(str(user_a_id))
        settings = await scope_service.get_settings(ctx)

        # Admin still gets their own settings
        assert settings == {"theme": "dark", "language": "en"}

    @pytest.mark.asyncio
    async def test_user_cannot_get_other_users_settings(
        self,
        scope_service: DataScopeService,
        settings_repo: FakeSettingsRepo,
        user_a_id: UUID,
        user_b_id: UUID,
    ) -> None:
        """User A cannot access User B's settings."""
        ctx = make_user_ctx(str(user_a_id))
        settings = await scope_service.get_settings(ctx)

        # Should not contain User B's settings
        assert settings.get("theme") == "dark"  # User A's theme
        assert settings.get("language") == "en"  # User A's language


# ---------------------------------------------------------------------------
# Tests: Role Check Verification
# ---------------------------------------------------------------------------


class TestRoleChecks:
    """Tests that the AuthContext role check works correctly."""

    def test_user_context_is_not_admin(self) -> None:
        """User-role context returns False for is_admin."""
        ctx = make_user_ctx()
        assert ctx.is_admin is False

    def test_admin_context_is_admin(self) -> None:
        """Admin-role context returns True for is_admin."""
        ctx = make_admin_ctx()
        assert ctx.is_admin is True
