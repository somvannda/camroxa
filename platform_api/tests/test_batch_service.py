from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import InsufficientCreditsError, ValidationError
from platform_api.models.domain import Batch, Song, SunoTask
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.ports.generation_port import DraftRequest, SongDraft
from platform_api.services.batch_service import SONG_STATUS_DRAFT_READY
from platform_api.services.batch_service import BatchService


@pytest.fixture
def batch_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create_batch = AsyncMock(side_effect=lambda batch: batch)
    repo.create_songs = AsyncMock(side_effect=lambda songs: songs)
    repo.upsert_batch_channel_assets = AsyncMock()
    return repo


@pytest.fixture
def credit_service() -> AsyncMock:
    service = AsyncMock()
    service.get_balance = AsyncMock(return_value=500)
    return service


@pytest.fixture
def pricing_service() -> AsyncMock:
    service = AsyncMock()

    async def _get_price(ai_service: str, operation_type: str, sub_model: str | None = None) -> int:
        if operation_type == "music":
            return 7
        if operation_type == "background_image":
            return 5
        return 3

    service.get_price = AsyncMock(side_effect=_get_price)
    return service


@pytest.fixture
def generation_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def profile_repo() -> AsyncMock:
    repo = AsyncMock()
    profile = SimpleNamespace(image_config={"mode": "bg_thumb"})
    repo.get_by_id = AsyncMock(return_value=profile)
    repo.get_by_id_for_user = AsyncMock(return_value=profile)
    return repo


@pytest.fixture
def ai_routing_service() -> AsyncMock:
    text_routing = SimpleNamespace(provider="deepseek", sub_model="chat")
    music_routing = SimpleNamespace(provider="suno", sub_model="V5")
    image_routing = SimpleNamespace(provider="fal", sub_model="flux")

    async def _resolve(operation: str) -> SimpleNamespace:
        if operation in {"lyric", "title", "album"}:
            return text_routing
        if operation == "music":
            return music_routing
        if operation in {"background_image", "thumbnail_image", "image"}:
            return image_routing
        return text_routing

    service = AsyncMock()
    service.resolve = AsyncMock(side_effect=_resolve)
    return service


@pytest.fixture
def prompt_service() -> AsyncMock:
    service = AsyncMock()
    description = SimpleNamespace(content="Hidden EDM admin prompt")
    structure = SimpleNamespace(content="[Intro]\n[Drop]\n[Breakdown]")
    service.get_description = AsyncMock(return_value=description)
    service.get_structure = AsyncMock(return_value=structure)
    service.get_description_for_access = AsyncMock(return_value=description)
    service.get_structure_for_access = AsyncMock(return_value=structure)
    return service


@pytest.fixture
def settings_service() -> AsyncMock:
    service = AsyncMock()
    service.get_merged_settings = AsyncMock(return_value={"sunoDefaultVersion": "v5.5"})
    return service


def make_service(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock | None = None,
    settings_service: AsyncMock | None = None,
    enforcement_service: AsyncMock | None = None,
) -> BatchService:
    return BatchService(
        batch_repo=batch_repo,
        credit_service=credit_service,
        pricing_service=pricing_service,
        generation_service=generation_service,
        profile_repo=profile_repo,
        ai_routing_service=ai_routing_service,
        prompt_service=prompt_service,
        settings_service=settings_service,
        enforcement_service=enforcement_service,
    )


@pytest.mark.asyncio
async def test_create_batch_persists_planned_date_window(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    result = await service.create_batch(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_id="00000000-0000-0000-0000-000000000002",
        alt_profile_id="00000000-0000-0000-0000-000000000003",
        description_id="00000000-0000-0000-0000-000000000004",
        structure_id="00000000-0000-0000-0000-000000000005",
        song_count=4,
        language="en",
        creativity_level=60,
        pairing_mode="match_key",
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 28),
    )

    assert result.planned_from_date == date(2026, 6, 25)
    assert result.planned_to_date == date(2026, 6, 28)
    assert result.auto_gen_image is False
    assert result.auto_gsuno is False
    batch_repo.create_batch.assert_awaited_once()
    batch_repo.create_songs.assert_awaited_once()
    created_songs = batch_repo.create_songs.await_args.args[0]
    assert all(str(song.description_id) == "00000000-0000-0000-0000-000000000004" for song in created_songs)
    assert all(str(song.structure_id) == "00000000-0000-0000-0000-000000000005" for song in created_songs)


@pytest.mark.asyncio
async def test_create_batch_shuffles_structures_when_enabled(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    structure_ids = [uuid4() for _ in range(3)]
    prompt_service.list_structures_workspace = AsyncMock(
        return_value=[
            SimpleNamespace(id=structure_id, name=f"S{index}")
            for index, structure_id in enumerate(structure_ids)
        ]
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={"shuffleStructure": True, "sunoDefaultVersion": "v5.5"}
    )
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    await service.create_batch(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_id="00000000-0000-0000-0000-000000000002",
        alt_profile_id="00000000-0000-0000-0000-000000000003",
        description_id="00000000-0000-0000-0000-000000000004",
        structure_id="00000000-0000-0000-0000-000000000005",
        shuffle_structure=True,
        song_count=4,
        language="en",
        creativity_level=60,
        pairing_mode="match_key",
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
    )

    created_songs = batch_repo.create_songs.await_args.args[0]
    assigned = [song.structure_id for song in created_songs]
    assert len(assigned) == 4
    assert all(structure_id in structure_ids for structure_id in assigned)
    assert len(set(assigned)) > 1
    prompt_service.list_structures_workspace.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_batch_keeps_fixed_structure_when_shuffle_off(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    prompt_service.list_structures_workspace = AsyncMock(
        return_value=[SimpleNamespace(id=uuid4(), name="S1")]
    )
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    await service.create_batch(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_id="00000000-0000-0000-0000-000000000002",
        alt_profile_id="00000000-0000-0000-0000-000000000003",
        description_id="00000000-0000-0000-0000-000000000004",
        structure_id="00000000-0000-0000-0000-000000000005",
        shuffle_structure=False,
        song_count=4,
        language="en",
        creativity_level=60,
        pairing_mode="match_key",
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
    )

    created_songs = batch_repo.create_songs.await_args.args[0]
    assert all(
        str(song.structure_id) == "00000000-0000-0000-0000-000000000005"
        for song in created_songs
    )
    prompt_service.list_structures_workspace.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_batch_persists_run_directories(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    result = await service.create_batch(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_id="00000000-0000-0000-0000-000000000002",
        alt_profile_id="00000000-0000-0000-0000-000000000003",
        song_count=1,
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
        ok_run_dir=r"D:\Music\Primary\2026-06-25",
        alt_run_dir=r"D:\Music\Secondary\2026-06-25",
    )

    assert result.ok_run_dir == r"D:\Music\Primary\2026-06-25"
    assert result.alt_run_dir == r"D:\Music\Secondary\2026-06-25"


@pytest.mark.asyncio
async def test_create_batch_defers_run_directory_planning(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    result = await service.create_batch(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_id="00000000-0000-0000-0000-000000000002",
        alt_profile_id="00000000-0000-0000-0000-000000000003",
        song_count=1,
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
    )

    assert result.ok_run_dir is None
    assert result.alt_run_dir is None


@pytest.mark.asyncio
async def test_assign_batch_run_directories_after_album(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    batch_repo.update_batch_run_directories = AsyncMock()
    profile_repo.get_by_id = AsyncMock(
        side_effect=[
            SimpleNamespace(folder_name="bass-drive", name="Bass Drive"),
            SimpleNamespace(folder_name="beattok-remixes", name="Beattok Remixes"),
        ]
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={"sunoOutputDir": r"D:\MusicGenerator\downloads\suno"}
    )
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )
    batch = Batch(
        id=uuid4(),
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
        song_count=1,
        status="processing",
        planned_from_date=date(2026, 7, 13),
        planned_to_date=date(2026, 7, 13),
    )

    updated = await service._assign_batch_run_directories_if_needed(
        batch, ok_album="Neon Nights", alt_album="Sunset Pulse"
    )

    batch_repo.update_batch_run_directories.assert_awaited_once()
    assert updated.ok_run_dir is not None
    assert updated.ok_run_dir.endswith(r"bass-drive\2026-07-13_Neon-Nights")
    assert updated.alt_run_dir is not None
    assert updated.alt_run_dir.endswith(r"beattok-remixes\2026-07-13_Sunset-Pulse")


@pytest.mark.asyncio
async def test_create_batch_rejects_inverted_date_window(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    with pytest.raises(ValidationError, match="to_date must be on or after from_date"):
        await service.create_batch(
            user_id="00000000-0000-0000-0000-000000000001",
            ok_profile_id="00000000-0000-0000-0000-000000000002",
            alt_profile_id="00000000-0000-0000-0000-000000000003",
            song_count=4,
            from_date=date(2026, 6, 28),
            to_date=date(2026, 6, 25),
        )

    credit_service.get_balance.assert_not_awaited()
    batch_repo.create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_batch_includes_image_cost_when_auto_image_is_enabled(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    credit_service.get_balance = AsyncMock(return_value=58)
    ai_routing_service.resolve = AsyncMock(
        side_effect=[
            SimpleNamespace(provider="deepseek", sub_model="chat"),
            SimpleNamespace(provider="deepseek", sub_model="chat"),
            SimpleNamespace(provider="deepseek", sub_model="chat"),
            SimpleNamespace(provider="suno", sub_model="V5"),
            SimpleNamespace(provider="fal", sub_model="flux"),
        ]
    )
    profile_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(image_config={"mode": "bg_thumb"})
    )
    profile_repo.get_by_id_for_user = AsyncMock(
        return_value=SimpleNamespace(image_config={"mode": "bg_thumb"})
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    # Draft reuse album after song1 (27) + Suno music×4 (28) + album-level images 2×2×5 (20) = 75
    with pytest.raises(InsufficientCreditsError, match="Required: 75"):
        await service.create_batch(
            user_id="00000000-0000-0000-0000-000000000001",
            ok_profile_id="00000000-0000-0000-0000-000000000002",
            alt_profile_id="00000000-0000-0000-0000-000000000003",
            auto_gen_image=True,
            auto_gsuno=True,
            song_count=4,
            from_date=date(2026, 6, 25),
            to_date=date(2026, 6, 25),
        )

    batch_repo.create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_batch_skips_music_cost_when_auto_gsuno_is_disabled(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    credit_service.get_balance = AsyncMock(return_value=27)
    ai_routing_service.resolve = AsyncMock(
        return_value=SimpleNamespace(provider="deepseek", sub_model="chat")
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    result = await service.create_batch(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_id="00000000-0000-0000-0000-000000000002",
        alt_profile_id="00000000-0000-0000-0000-000000000003",
        song_count=4,
        auto_gsuno=False,
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
    )

    assert result.auto_gsuno is False
    assert ai_routing_service.resolve.await_count == 3
    pricing_service.get_price.assert_awaited()
    batch_repo.create_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_suno_task_completed_skips_image_jobs_when_auto_image_is_disabled(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    song_id = uuid4()
    batch_id = uuid4()
    batch_repo.get_batch_by_id = AsyncMock(
        return_value=SimpleNamespace(id=batch_id, auto_gen_image=False, auto_gsuno=False)
    )
    batch_repo.get_songs_by_batch = AsyncMock(
        return_value=[SimpleNamespace(id=song_id, batch_index=0, title="Test Song")]
    )
    batch_repo.update_song_status = AsyncMock()
    batch_repo.create_image_jobs = AsyncMock()
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 1,
            "drafts_completed": 1,
            "drafts_failed": 0,
            "suno_submitted": 0,
            "suno_completed": 1,
            "suno_failed": 0,
            "audio_downloaded": 0,
            "images_completed": 0,
        }
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    jobs = await service.on_suno_task_completed(song_id=song_id, batch_id=batch_id)

    assert jobs == []
    batch_repo.create_image_jobs.assert_not_awaited()


@pytest.mark.asyncio
async def test_orchestrate_drafts_resolves_hidden_prompt_content_from_song_ids(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(
            title="Generated Title",
            album="Generated Album",
            lyrics="Generated Lyrics",
        )
    )
    batch_repo.get_songs_by_batch = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid4(),
                batch_id=uuid4(),
                batch_index=0,
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                title=None,
                album=None,
                lyrics=None,
                description_id=UUID("00000000-0000-0000-0000-000000000004"),
                structure_id=UUID("00000000-0000-0000-0000-000000000005"),
                status="pending",
            ),
        ]
    )
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    draft_requests = [
        DraftRequest(
            language="en",
            creativity_level=55,
            description="EDM / Workout Gym",
            structure="Verse Chorus Bridge",
        )
    ]

    songs = await service.orchestrate_drafts(
        batch_id=uuid4(),
        user_id="00000000-0000-0000-0000-000000000001",
        draft_requests=draft_requests,
    )

    _, prepared_request = generation_service.submit_draft.await_args.args[:2]
    assert prepared_request.description == "Hidden EDM admin prompt"
    assert prepared_request.structure == "[Intro]\n[Drop]\n[Breakdown]"
    assert songs[0].status == SONG_STATUS_DRAFT_READY
    prompt_service.get_description_for_access.assert_awaited_once()
    prompt_service.get_structure_for_access.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrate_drafts_charges_via_enforcement_not_wallet(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(
            title="Generated Title",
            album="Generated Album",
            lyrics="Generated Lyrics",
        )
    )
    batch_repo.get_songs_by_batch = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid4(),
                batch_id=uuid4(),
                batch_index=0,
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                title=None,
                album=None,
                lyrics=None,
                description_id=UUID("00000000-0000-0000-0000-000000000004"),
                structure_id=UUID("00000000-0000-0000-0000-000000000005"),
                status="pending",
            ),
        ]
    )
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()
    credit_service.get_balance = AsyncMock(return_value=0)
    enforcement_service = AsyncMock()
    enforcement_service.deduct_for_operation = AsyncMock(return_value=0)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
        enforcement_service=enforcement_service,
    )

    profile_id = uuid4()
    await service.orchestrate_drafts(
        batch_id=uuid4(),
        user_id="00000000-0000-0000-0000-000000000001",
        draft_requests=[
            DraftRequest(
                language="en",
                creativity_level=55,
                description="EDM / Workout Gym",
                structure="[Verse]\n[Chorus]",
            )
        ],
        channel_profile_id=profile_id,
    )

    assert enforcement_service.deduct_for_operation.await_count == 3
    assert generation_service.submit_draft.await_args.kwargs.get("skip_pricing") is True


@pytest.mark.asyncio
async def test_orchestrate_drafts_reuses_first_album_for_later_songs(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    song_one_id = uuid4()
    song_two_id = uuid4()
    batch_repo.get_songs_by_batch = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=song_one_id,
                batch_id=uuid4(),
                batch_index=0,
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                title=None,
                album=None,
                lyrics=None,
                description_id=None,
                structure_id=None,
                status="pending",
            ),
            SimpleNamespace(
                id=song_two_id,
                batch_id=uuid4(),
                batch_index=1,
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                title=None,
                album=None,
                lyrics=None,
                description_id=None,
                structure_id=None,
                status="pending",
            ),
        ]
    )
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()

    async def _submit_draft(
        _user_id: str,
        request: DraftRequest,
        *,
        provider: str,
        model: str,
        **kwargs: object,
    ) -> SongDraft:
        if request.forced_album:
            return SongDraft(
                title=f"Title for {request.forced_album}",
                album=request.forced_album,
                lyrics="Lyrics",
            )
        return SongDraft(title="Song One", album="Shared Album", lyrics="Lyrics")

    generation_service.submit_draft = AsyncMock(side_effect=_submit_draft)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    songs = await service.orchestrate_drafts(
        batch_id=uuid4(),
        user_id="00000000-0000-0000-0000-000000000001",
        draft_requests=[
            DraftRequest(language="en", creativity_level=55, description="Desc", structure="[Verse]"),
            DraftRequest(language="en", creativity_level=55, description="Desc", structure="[Verse]"),
        ],
    )

    assert songs[0].album == "Shared Album"
    assert songs[1].album == "Shared Album"
    second_request = generation_service.submit_draft.await_args_list[1].args[1]
    assert second_request.forced_album == "Shared Album"


@pytest.mark.asyncio
async def test_orchestrate_drafts_uses_content_pools_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    from platform_api.services import batch_service as batch_service_module
    from platform_api.services.content_pool_service import ClaimedPoolItem

    batch_repo.get_songs_by_batch = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid4(),
                batch_id=uuid4(),
                batch_index=0,
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                title=None,
                album=None,
                lyrics=None,
                description_id=None,
                structure_id=None,
                status="pending",
            ),
        ]
    )
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(title="Pool Title", album="Pool Album", lyrics="Lyrics")
    )

    from platform_api.services import batch_service as batch_service_module

    async def _claim_pool_item(**kwargs):
        kind = kwargs["kind"]
        if kind == "titles":
            return ClaimedPoolItem(
                kind="titles",
                item_id=1,
                text="Seed Title",
                secondary_text=None,
                reservation_token="token-1",
            )
        if kind == "albums":
            return ClaimedPoolItem(
                kind="albums",
                item_id=2,
                text="Seed Album",
                secondary_text=None,
                reservation_token="token-1",
            )
        return ClaimedPoolItem(
            kind="openings",
            item_id=3,
            text="Line one",
            secondary_text="Line two",
            reservation_token="token-1",
        )

    finalized: list[int] = []
    monkeypatch.setattr(batch_service_module, "claim_pool_item", _claim_pool_item)
    monkeypatch.setattr(
        batch_service_module,
        "finalize_pool_item",
        AsyncMock(side_effect=lambda *, item: finalized.append(item.item_id)),
    )
    monkeypatch.setattr(batch_service_module, "release_claimed_items", AsyncMock())

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    songs = await service.orchestrate_drafts(
        batch_id=uuid4(),
        user_id="00000000-0000-0000-0000-000000000001",
        draft_requests=[
            DraftRequest(language="en", creativity_level=55, description="Base desc", structure="[Verse]"),
        ],
        use_content_pools=True,
        unique_opening=True,
    )

    prepared_request = generation_service.submit_draft.await_args.args[1]
    assert prepared_request.title_seed == "Seed Title"
    assert prepared_request.album_seed == "Seed Album"
    assert prepared_request.forced_opening == "Line one\nLine two"
    assert songs[0].status == SONG_STATUS_DRAFT_READY
    assert finalized == [1, 2, 3]


@pytest.mark.asyncio
async def test_orchestrate_drafts_persists_distinct_channel_albums(
    monkeypatch: pytest.MonkeyPatch,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    from platform_api.services import batch_service as batch_service_module
    from platform_api.services.content_pool_service import ClaimedPoolItem

    batch_id = uuid4()
    batch = Batch(
        id=batch_id,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
    )
    batch_repo.get_songs_by_batch = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid4(),
                batch_id=batch_id,
                batch_index=0,
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                title=None,
                album=None,
                lyrics=None,
                description_id=None,
                structure_id=None,
                status="pending",
            ),
        ]
    )
    batch_repo.get_batch_by_id = AsyncMock(return_value=batch)
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(title="Pool Title", album="Primary Album", lyrics="Lyrics")
    )
    generation_service.generate_text = AsyncMock(
        return_value='{"album": "Polished Secondary Album"}'
    )

    async def _claim_pool_item(**kwargs):
        kind = kwargs["kind"]
        if kind == "titles":
            return ClaimedPoolItem(
                kind="titles",
                item_id=1,
                text="Seed Title",
                secondary_text=None,
                reservation_token="token-1",
            )
        avoid = kwargs.get("avoid_texts") or []
        album_text = "Secondary Album" if avoid else "Primary Album"
        return ClaimedPoolItem(
            kind="albums",
            item_id=2 if not avoid else 4,
            text=album_text,
            secondary_text=None,
            reservation_token="token-1",
        )

    monkeypatch.setattr(batch_service_module, "claim_pool_item", _claim_pool_item)
    monkeypatch.setattr(batch_service_module, "finalize_pool_item", AsyncMock())
    monkeypatch.setattr(batch_service_module, "release_claimed_items", AsyncMock())

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    await service.orchestrate_drafts(
        batch_id=batch_id,
        user_id="00000000-0000-0000-0000-000000000001",
        draft_requests=[
            DraftRequest(language="en", creativity_level=55, description="Base desc", structure="[Verse]"),
        ],
        use_content_pools=True,
    )

    batch_repo.update_batch_channel_albums.assert_awaited_once_with(
        batch_id,
        ok_album="Primary Album",
        alt_album="Polished Secondary Album",
    )


@pytest.mark.asyncio
async def test_create_image_jobs_for_song_applies_dual_prompts_and_reference_paths(
    tmp_path,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    bg_sample = tmp_path / "bg-sample.png"
    bg_sample.write_bytes(b"bg")
    th_sample = tmp_path / "thumb-style.png"
    th_sample.write_bytes(b"th")

    profile_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            image_config={
                "mode": "bg_thumb",
                "background_prompt": "Profile BG {title}",
                "thumbnail_prompt": "Profile TH {album}",
                "provider": "fal",
                "resolution": "1920x1080",
                "style_strength": 0.7,
            }
        )
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageBackgroundPrompt": "Boss background direction",
            "imageThumbnailPrompt": "Boss thumbnail direction",
            "imageBgSamples": [str(bg_sample)],
            "imageThumbSamples": [str(th_sample)],
            "imageBgRandom": False,
            "imageThumbRandom": False,
        }
    )
    batch_repo.get_image_jobs_by_batch = AsyncMock(return_value=[])
    batch_repo.create_image_jobs = AsyncMock(side_effect=lambda jobs: jobs)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    song = Song(
        id=uuid4(),
        batch_id=uuid4(),
        batch_index=0,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Storm Run",
        album="Night Shift",
        lyrics="lyrics",
    )
    batch = Batch(
        id=uuid4(),
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=None,
        auto_gen_image=True,
    )

    jobs = await service.create_image_jobs_for_song(song, batch)

    assert len(jobs) == 2
    background_job = next(job for job in jobs if job.kind == ImageKind.BACKGROUND)
    thumbnail_job = next(job for job in jobs if job.kind == ImageKind.THUMBNAIL)

    assert background_job.channel_role == ChannelRole.OK
    assert "Profile BG Storm Run" in str(background_job.prompt)
    assert "Boss background direction" in str(background_job.prompt)
    assert background_job.input_image_path == str(bg_sample)

    assert "Profile TH Night Shift" in str(thumbnail_job.prompt)
    assert "Boss thumbnail direction" in str(thumbnail_job.prompt)
    assert thumbnail_job.style_reference_path == str(th_sample)
    assert thumbnail_job.source_job_id == background_job.id
    assert thumbnail_job.input_image_path is None


@pytest.mark.asyncio
async def test_create_image_jobs_for_song_uses_manual_assets_without_ai_jobs(
    tmp_path,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    run_dir = tmp_path / "Primary" / "2026-06-29"
    run_dir.mkdir(parents=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg16")
    (run_dir / "background-9x16.png").write_bytes(b"bg9")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th16")
    (run_dir / "thumbnail-9x16.png").write_bytes(b"th9")

    profile_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            image_config={
                "mode": "bg_thumb",
                "background_prompt": "Profile BG {title}",
                "thumbnail_prompt": "Profile TH {album}",
                "resolution": "1920x1080",
                "style_strength": 0.7,
            }
        )
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageSourceMode": "manual",
            "imageBackgroundPrompt": "Boss background direction",
            "imageThumbnailPrompt": "Boss thumbnail direction",
        }
    )
    batch_repo.get_image_jobs_by_batch = AsyncMock(return_value=[])
    batch_repo.create_image_jobs = AsyncMock(side_effect=lambda jobs: jobs)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    song = Song(
        id=uuid4(),
        batch_id=uuid4(),
        batch_index=0,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Storm Run",
        album="Night Shift",
        lyrics="lyrics",
    )
    batch = Batch(
        id=uuid4(),
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=None,
        ok_run_dir=str(run_dir),
        auto_gen_image=True,
    )

    jobs = await service.create_image_jobs_for_song(song, batch)

    assert len(jobs) == 2
    assert all(job.status.name.lower() == "success" for job in jobs)
    assert all(job.provider == "manual" for job in jobs)
    background_job = next(job for job in jobs if job.kind == ImageKind.BACKGROUND)
    thumbnail_job = next(job for job in jobs if job.kind == ImageKind.THUMBNAIL)
    assert background_job.output_image_path == str((run_dir / "background-16x9.png").resolve())
    assert thumbnail_job.output_image_path == str((run_dir / "thumbnail-16x9.png").resolve())
    assert background_job.input_image_path is None
    assert thumbnail_job.source_job_id is None
    batch_repo.upsert_batch_channel_assets.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_image_jobs_for_batch_is_once_per_channel_not_per_song(
    tmp_path,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    bg_sample = tmp_path / "bg-sample.png"
    bg_sample.write_bytes(b"bg")
    th_sample = tmp_path / "thumb-style.png"
    th_sample.write_bytes(b"th")

    profile_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            image_config={
                "mode": "bg_thumb",
                "background_prompt": "Profile BG {title}",
                "thumbnail_prompt": "Profile TH {album}",
                "provider": "fal",
                "resolution": "1920x1080",
                "style_strength": 0.7,
            }
        )
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageBackgroundPrompt": "Boss background direction",
            "imageThumbnailPrompt": "Boss thumbnail direction",
            "imageBgSamples": [str(bg_sample)],
            "imageThumbSamples": [str(th_sample)],
            "imageBgRandom": False,
            "imageThumbRandom": False,
        }
    )
    existing: list = []
    batch_repo.get_image_jobs_by_batch = AsyncMock(side_effect=lambda _bid: list(existing))

    async def _persist(jobs: list) -> list:
        existing.extend(jobs)
        return jobs

    batch_repo.create_image_jobs = AsyncMock(side_effect=_persist)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    batch_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    song_a = Song(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title="Track One",
        album="Shared Album",
        lyrics="lyrics",
    )
    song_b = Song(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=1,
        user_id=user_id,
        title="Track Two",
        album="Shared Album",
        lyrics="lyrics",
    )
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
        auto_gen_image=True,
    )
    batch_repo.get_songs_by_batch = AsyncMock(return_value=[song_a, song_b])

    first = await service.create_image_jobs_for_song(song_a, batch)
    second = await service.create_image_jobs_for_song(song_b, batch)

    # Two channels × BG+TH = 4 jobs on first song; second song adds none.
    assert len(first) == 4
    assert second == []
    assert len(existing) == 4
    assert batch_repo.create_image_jobs.await_count == 1


@pytest.mark.asyncio
async def test_create_image_jobs_for_batch_race_second_insert_is_noop(
    tmp_path,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    """Concurrent Suno callbacks both see empty slots; DB unique keeps one set."""
    bg_sample = tmp_path / "bg-sample.png"
    bg_sample.write_bytes(b"bg")
    th_sample = tmp_path / "thumb-style.png"
    th_sample.write_bytes(b"th")

    profile_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            image_config={
                "mode": "bg_thumb",
                "background_prompt": "Profile BG {title}",
                "thumbnail_prompt": "Profile TH {album}",
                "provider": "fal",
                "resolution": "1920x1080",
                "style_strength": 0.7,
            }
        )
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageBackgroundPrompt": "Boss background direction",
            "imageThumbnailPrompt": "Boss thumbnail direction",
            "imageBgSamples": [str(bg_sample)],
            "imageThumbSamples": [str(th_sample)],
            "imageBgRandom": False,
            "imageThumbRandom": False,
        }
    )
    existing: list = []
    # Race: both callers miss the in-flight insert.
    batch_repo.get_image_jobs_by_batch = AsyncMock(return_value=[])

    async def _persist(jobs: list) -> list:
        added: list = []
        keys = {
            (item.profile_id, item.kind, item.channel_role)
            for item in existing
        }
        for job in jobs:
            key = (job.profile_id, job.kind, job.channel_role)
            if key in keys:
                continue
            existing.append(job)
            keys.add(key)
            added.append(job)
        return added

    batch_repo.create_image_jobs = AsyncMock(side_effect=_persist)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    batch_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    song_a = Song(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title="Track One",
        album="Shared Album",
        lyrics="lyrics",
    )
    song_b = Song(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=1,
        user_id=user_id,
        title="Track Two",
        album="Shared Album",
        lyrics="lyrics",
    )
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
        auto_gen_image=True,
    )
    batch_repo.get_songs_by_batch = AsyncMock(return_value=[song_a, song_b])

    first = await service.create_image_jobs_for_song(song_a, batch)
    second = await service.create_image_jobs_for_song(song_b, batch)

    assert len(first) == 4
    assert second == []
    assert len(existing) == 4
    assert batch_repo.create_image_jobs.await_count == 2


@pytest.mark.asyncio
async def test_sync_manual_assets_for_batch_updates_existing_jobs(
    tmp_path,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    run_dir = tmp_path / "Primary" / "2026-06-29"
    run_dir.mkdir(parents=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg16")
    (run_dir / "background-9x16.png").write_bytes(b"bg9")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th16")
    (run_dir / "thumbnail-9x16.png").write_bytes(b"th9")

    profile_id = UUID("00000000-0000-0000-0000-000000000002")
    batch_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    song = Song(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title="Storm Run",
        album="Night Shift",
        lyrics="lyrics",
    )
    existing_job = SimpleNamespace(
        id=uuid4(),
        song_id=song.id,
        profile_id=profile_id,
        kind=ImageKind.BACKGROUND,
        channel_role=ChannelRole.OK,
        status="pending",
        output_image_path=None,
        attempt_count=1,
    )

    profile_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            image_config={
                "mode": "bg_thumb",
                "background_prompt": "Profile BG {title}",
                "thumbnail_prompt": "Profile TH {album}",
                "resolution": "1920x1080",
                "style_strength": 0.7,
            }
        )
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageSourceMode": "manual",
            "imageBackgroundPrompt": "Boss background direction",
            "imageThumbnailPrompt": "Boss thumbnail direction",
        }
    )
    batch_repo.get_batch_for_user = AsyncMock(
        return_value=Batch(
            id=batch_id,
            user_id=user_id,
            ok_profile_id=profile_id,
            alt_profile_id=None,
            ok_run_dir=str(run_dir),
            auto_gen_image=True,
        )
    )
    batch_repo.get_songs_by_batch = AsyncMock(return_value=[song])
    batch_repo.get_image_jobs_by_batch = AsyncMock(return_value=[existing_job])
    batch_repo.update_image_job_status = AsyncMock()
    batch_repo.create_image_jobs = AsyncMock(side_effect=lambda jobs: jobs)
    batch_repo.get_batch_by_id = AsyncMock(
        return_value=Batch(
            id=batch_id,
            user_id=user_id,
            ok_profile_id=profile_id,
            alt_profile_id=None,
            ok_run_dir=str(run_dir),
            auto_gen_image=True,
            auto_gsuno=True,
        )
    )
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 1,
            "drafts_completed": 1,
            "drafts_failed": 0,
            "suno_submitted": 1,
            "suno_completed": 1,
            "suno_failed": 0,
        }
    )
    batch_repo.update_batch_status = AsyncMock()

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    updated = await service.sync_manual_assets_for_batch(
        user_id=str(user_id),
        batch_id=str(batch_id),
    )

    assert updated == 2
    batch_repo.update_image_job_status.assert_awaited_once()
    batch_repo.create_image_jobs.assert_awaited_once()
    batch_repo.upsert_batch_channel_assets.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_batch_completes_after_drafts_when_auto_gsuno_is_disabled(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    batch_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    batch = SimpleNamespace(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        song_count=1,
        language="en",
        creativity_level=55,
        auto_gsuno=False,
        auto_gen_image=False,
        ok_run_dir=r"D:\Music\bass-drive\2026-07-12_02",
        alt_run_dir=r"D:\Music\beattok-remixes\2026-07-12_02",
        ok_album="Generated Album",
        alt_album="Generated Alt Album",
    )
    song = SimpleNamespace(
        id=uuid4(),
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title=None,
        album=None,
        lyrics=None,
        description_id=UUID("00000000-0000-0000-0000-000000000004"),
        structure_id=UUID("00000000-0000-0000-0000-000000000005"),
        status="pending",
    )
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.get_batch_by_id = AsyncMock(return_value=batch)
    batch_repo.get_songs_by_batch = AsyncMock(return_value=[song])
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 1,
            "drafts_completed": 1,
            "drafts_failed": 0,
            "suno_submitted": 0,
            "suno_completed": 0,
            "suno_failed": 0,
            "audio_downloaded": 0,
            "images_completed": 0,
        }
    )
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(
            title="Generated Title",
            album="Generated Album",
            lyrics="Generated Lyrics",
        )
    )
    ai_routing_service.resolve = AsyncMock(
        return_value=SimpleNamespace(provider="deepseek", sub_model="chat")
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
    )

    await service.execute_batch(batch_id=batch_id, user_id=str(user_id))

    generation_service.submit_suno.assert_not_awaited()
    assert any(call.args == (batch_id, "completed") for call in batch_repo.update_batch_status.await_args_list)


@pytest.mark.asyncio
async def test_execute_batch_submits_suno_for_successful_drafts_when_enabled(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    batch_id = uuid4()
    song_id = uuid4()
    task_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    batch = SimpleNamespace(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        song_count=1,
        language="en",
        creativity_level=55,
        auto_gsuno=True,
        auto_gen_image=False,
        ok_run_dir=r"D:\Music\bass-drive\2026-07-12_02",
        alt_run_dir=r"D:\Music\beattok-remixes\2026-07-12_02",
        ok_album="Generated Album",
        alt_album="Generated Alt Album",
    )
    song = SimpleNamespace(
        id=song_id,
        batch_id=batch_id,
        batch_index=0,
        user_id=user_id,
        title=None,
        album=None,
        lyrics=None,
        description_id=UUID("00000000-0000-0000-0000-000000000004"),
        structure_id=UUID("00000000-0000-0000-0000-000000000005"),
        status="pending",
    )
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.get_batch_by_id = AsyncMock(return_value=batch)
    batch_repo.get_songs_by_batch = AsyncMock(return_value=[song])
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()
    batch_repo.link_suno_task = AsyncMock()
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 1,
            "drafts_completed": 1,
            "drafts_failed": 0,
            "suno_submitted": 1,
            "suno_completed": 0,
            "suno_failed": 0,
            "audio_downloaded": 0,
            "images_completed": 0,
        }
    )
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(
            title="Generated Title",
            album="Generated Album",
            lyrics="Generated Lyrics",
        )
    )
    generation_service.submit_suno = AsyncMock(return_value=str(task_id))
    enforcement_service = AsyncMock()
    enforcement_service.deduct_for_operation = AsyncMock(return_value=14)
    ai_routing_service.resolve = AsyncMock(
        side_effect=lambda operation: SimpleNamespace(
            provider="suno" if operation == "music" else "deepseek",
            sub_model="V5" if operation == "music" else "chat",
        )
    )
    settings_service.get_merged_settings = AsyncMock(return_value={"sunoDefaultVersion": "v5"})

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
        enforcement_service=enforcement_service,
    )

    await service.execute_batch(batch_id=batch_id, user_id=str(user_id))

    assert enforcement_service.deduct_for_operation.await_count == 4
    draft_operations = [
        call.args[2]
        for call in enforcement_service.deduct_for_operation.await_args_list
        if call.args[2] != "music"
    ]
    assert draft_operations == ["lyric", "title", "album"]
    music_calls = [
        call
        for call in enforcement_service.deduct_for_operation.await_args_list
        if call.args[2] == "music"
    ]
    assert len(music_calls) == 1
    deduct_args = music_calls[0].args
    assert deduct_args[3] == "suno"
    assert music_calls[0].kwargs["sub_model"] == "V5"
    generation_service.submit_draft.assert_awaited_once()
    assert generation_service.submit_draft.await_args.kwargs.get("skip_pricing") is True
    generation_service.submit_suno.assert_awaited_once()
    assert generation_service.submit_suno.await_args.kwargs.get("skip_pricing") is True
    _, suno_request = generation_service.submit_suno.await_args.args[:2]
    assert suno_request.model == "V5"
    assert suno_request.style == "Hidden EDM admin prompt"
    batch_repo.link_suno_task.assert_awaited_once_with(task_id, song_id, batch_id)
    batch_repo.update_suno_download_state.assert_awaited_once()
    assert any(call.args == (song_id, "suno_pending") for call in batch_repo.update_song_status.await_args_list)


def test_build_suno_download_target_path_uses_ok_alt_suffixes() -> None:
    ok_path = BatchService._build_suno_download_target_path(
        output_dir=r"D:\Music\bass-drive\2026-07-12_02",
        title="Shadow Rebels August Night",
        track_no=1,
        variant="primary",
    )
    alt_path = BatchService._build_suno_download_target_path(
        output_dir=r"D:\Music\beattok-remixes\2026-07-12_02",
        title="Shadow Rebels August Night",
        track_no=1,
        variant="secondary",
    )
    assert ok_path.endswith(r"bass-drive\2026-07-12_02\1. Shadow Rebels August Night_OK.mp3")
    assert alt_path.endswith(r"beattok-remixes\2026-07-12_02\1. Shadow Rebels August Night_Alt.mp3")


def test_resolve_batch_run_dir_keeps_alt_separate_from_ok() -> None:
    batch = Batch(
        id=uuid4(),
        user_id=uuid4(),
        ok_profile_id=uuid4(),
        alt_profile_id=uuid4(),
        song_count=1,
        ok_run_dir=r"D:\Music\bass-drive\2026-07-12_02",
        alt_run_dir=r"D:\Music\beattok-remixes\2026-07-12_02",
    )
    assert BatchService._resolve_batch_run_dir(batch, ChannelRole.OK).endswith("bass-drive\\2026-07-12_02")
    assert BatchService._resolve_batch_run_dir(batch, ChannelRole.ALT).endswith(
        "beattok-remixes\\2026-07-12_02"
    )
    assert BatchService._resolve_batch_run_dir(batch, ChannelRole.ALT) != BatchService._resolve_batch_run_dir(
        batch, ChannelRole.OK
    )


def test_build_draft_requests_preserves_ai_free_structure_mode() -> None:
    batch = Batch(song_count=2, structure_mode="ai_free")
    service = BatchService(
        batch_repo=AsyncMock(),
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=AsyncMock(),
    )
    requests = service._build_draft_requests(batch)
    assert len(requests) == 2
    assert all(request.structure_mode == "ai_free" for request in requests)


def test_derive_batch_status_processing_when_drafts_done_before_suno() -> None:
    batch = Batch(song_count=2, auto_gsuno=True)
    counters = {
        "total_songs": 2,
        "drafts_completed": 2,
        "drafts_failed": 0,
        "suno_submitted": 0,
        "suno_completed": 0,
        "suno_failed": 0,
    }
    service = make_service(
        batch_repo=AsyncMock(),
        credit_service=AsyncMock(),
        pricing_service=AsyncMock(),
        generation_service=AsyncMock(),
        profile_repo=AsyncMock(),
        ai_routing_service=AsyncMock(),
    )
    assert service._derive_batch_status(batch, counters) == "processing"


@pytest.mark.asyncio
async def test_sanitize_suno_payload_uses_learned_terms_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    from platform_api.services.suno_blocklist_service import SunoBlocklistService
    from platform_api.tests.test_suno_blocklist_service import FakeSunoBlocklistRepo

    blocklist_service = SunoBlocklistService(FakeSunoBlocklistRepo())
    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: blocklist_service,
    )
    song_id = uuid4()
    batch_id = uuid4()
    song = Song(
        id=song_id,
        batch_id=batch_id,
        user_id=uuid4(),
        title="Neon lowlight",
        album="Album",
        lyrics="Pressure in the lowlight",
        batch_index=0,
    )
    batch = Batch(id=batch_id, user_id=song.user_id, ok_profile_id=uuid4(), song_count=1)
    latest_task = SunoTask(
        song_id=song_id,
        status=TaskStatus.FAILED,
        error_message="Your lyrics contain producer tag lowlight - we don't reference specific artists",
    )
    batch_repo.get_latest_suno_task_for_song = AsyncMock(return_value=latest_task)
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_suno_sanitize_metadata = AsyncMock()

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    service._resolve_song_style = AsyncMock(return_value="Dream pop lowlight")

    payload = await service._sanitize_suno_payload(song, batch)

    assert "lowlight" not in payload.lyrics.lower()
    assert "afterglow" in payload.lyrics.lower()
    assert payload.title.lower().endswith("afterglow")
    assert "afterglow" in payload.style.lower()
    assert payload.is_retry is True
    assert payload.blocked_terms == ("lowlight",)
    batch_repo.update_song_draft.assert_awaited_once()
    batch_repo.update_song_suno_sanitize_metadata.assert_awaited_once()
    assert song.lyrics == payload.lyrics
