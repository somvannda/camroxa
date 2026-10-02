from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import InsufficientCreditsError, QuotaExceededError, ValidationError
from platform_api.models.domain import Batch, Song, SunoTask
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.ports.generation_port import DraftRequest, SongDraft
from platform_api.services.batch_service import SONG_STATUS_DRAFT_READY
from platform_api.services.batch_service import BatchService
from platform_api.services.billing_calendar import billing_today


@pytest.fixture
def batch_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create_batch = AsyncMock(side_effect=lambda batch: batch)
    repo.create_songs = AsyncMock(side_effect=lambda songs: songs)
    repo.upsert_batch_channel_assets = AsyncMock()

    async def _claim_albums(_batch_id, *, ok_album, alt_album):
        return (
            str(ok_album or "").strip() or None,
            str(alt_album or "").strip() or None,
        )

    async def _claim_dirs(_batch_id, *, ok_run_dir, alt_run_dir):
        return (
            str(ok_run_dir or "").strip() or None,
            str(alt_run_dir or "").strip() or None,
        )

    repo.claim_batch_channel_albums = AsyncMock(side_effect=_claim_albums)
    repo.claim_batch_run_directories = AsyncMock(side_effect=_claim_dirs)
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

    async def _resolve_image_chain(operation: str) -> list[SimpleNamespace]:
        return [await _resolve(operation)]

    service = AsyncMock()
    service.resolve = AsyncMock(side_effect=_resolve)
    service.resolve_image_chain = AsyncMock(side_effect=_resolve_image_chain)
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

    assert result.ok_run_dir == r"Primary\2026-06-25"
    assert result.alt_run_dir == r"Secondary\2026-06-25"


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
    async def _claim(_batch_id, *, ok_run_dir, alt_run_dir):
        return ok_run_dir, alt_run_dir

    batch_repo.claim_batch_run_directories = AsyncMock(side_effect=_claim)
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
    batch_repo.get_batch_by_id = AsyncMock(return_value=batch)

    updated = await service._assign_batch_run_directories_if_needed(
        batch, ok_album="Neon Nights", alt_album="Sunset Pulse"
    )

    batch_repo.claim_batch_run_directories.assert_awaited_once()
    assert updated.ok_run_dir == r"bass-drive\2026-07-13_Neon-Nights"
    assert updated.alt_run_dir == r"beattok-remixes\2026-07-13_Sunset-Pulse"


@pytest.mark.asyncio
async def test_persist_batch_channel_albums_first_writer_wins(
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
    batch = Batch(
        id=batch_id,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
        ok_album="Twilight Letters Burn",
        alt_album="Opal Silence Drift",
    )
    batch_repo.get_batch_by_id = AsyncMock(return_value=batch)
    batch_repo.claim_batch_channel_albums = AsyncMock(
        return_value=("Twilight Letters Burn", "Opal Silence Drift")
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
    song = SimpleNamespace(album="Crystal Desire Collection", batch_index=1)
    updated = await service._persist_batch_channel_albums(
        batch_id=batch_id,
        user_id="00000000-0000-0000-0000-000000000001",
        successful_songs=[song],
        use_content_pools=False,
        draft_requests=[
            DraftRequest(
                language="en",
                creativity_level=55,
                description="Desc",
                structure="[Verse]",
            )
        ],
        draft_routing=SimpleNamespace(),
        channel_profile_id=batch.ok_profile_id,
    )
    assert updated is not None
    assert updated.ok_album == "Twilight Letters Burn"
    assert updated.alt_album == "Opal Silence Drift"
    batch_repo.claim_batch_channel_albums.assert_not_awaited()
    generation_service.generate_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_song_draft_forces_locked_ok_album(
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
    batch = Batch(
        id=batch_id,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
        song_count=2,
        auto_gsuno=False,
        ok_album="Locked Album",
        alt_album="Locked Alt",
        ok_run_dir=r"D:\Music\primary\2026-08-03_Locked-Album",
        alt_run_dir=r"D:\Music\secondary\2026-08-03_Locked-Alt",
        status="processing",
    )
    racing_song = Song(
        id=song_id,
        batch_id=batch_id,
        user_id=batch.user_id,
        batch_index=1,
        status="pending",
    )
    sibling = Song(
        id=uuid4(),
        batch_id=batch_id,
        user_id=batch.user_id,
        batch_index=0,
        status="draft_ready",
        title="Sibling",
        album="Locked Album",
        lyrics="x",
    )
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.get_songs_for_user_batch = AsyncMock(return_value=[sibling, racing_song])
    batch_repo.get_batch_by_id = AsyncMock(return_value=batch)
    batch_repo.update_song_status = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.claim_batch_channel_albums = AsyncMock(
        return_value=("Locked Album", "Locked Alt")
    )
    batch_repo.claim_batch_run_directories = AsyncMock(
        return_value=(batch.ok_run_dir, batch.alt_run_dir)
    )
    batch_repo.get_batch_status_counters = AsyncMock(
        return_value={
            "total_songs": 2,
            "drafts_completed": 2,
            "drafts_failed": 0,
            "suno_submitted": 0,
            "suno_completed": 0,
            "suno_failed": 0,
        }
    )
    batch_repo.update_batch_status = AsyncMock()
    generation_service.submit_draft = AsyncMock(
        return_value=SongDraft(title="Racer Title", album="Locked Album", lyrics="Lyrics")
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
    song = await service.retry_song_draft(
        batch_id=batch_id,
        song_id=song_id,
        user_id=str(batch.user_id),
        submit_suno=False,
    )
    assert song.album == "Locked Album"
    request = generation_service.submit_draft.await_args.args[1]
    assert request.forced_album == "Locked Album"


@pytest.mark.asyncio
async def test_active_suno_task_skips_failed_and_lost_audio(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    song_id = uuid4()

    batch_repo.get_latest_suno_task_for_song = AsyncMock(return_value=None)
    assert await service._active_suno_task_for_song(song_id) is None

    batch_repo.get_latest_suno_task_for_song = AsyncMock(
        return_value=SunoTask(song_id=song_id, status=TaskStatus.FAILED)
    )
    assert await service._active_suno_task_for_song(song_id) is None

    batch_repo.get_latest_suno_task_for_song = AsyncMock(
        return_value=SunoTask(
            song_id=song_id,
            status=TaskStatus.SUCCESS,
            download_unavailable_ok=True,
        )
    )
    assert await service._active_suno_task_for_song(song_id) is None

    live = SunoTask(song_id=song_id, status=TaskStatus.SUCCESS)
    batch_repo.get_latest_suno_task_for_song = AsyncMock(return_value=live)
    assert await service._active_suno_task_for_song(song_id) is live


@pytest.mark.asyncio
async def test_submit_song_to_suno_skips_duplicate_live_task(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    song_id = uuid4()
    batch_id = uuid4()
    song = Song(
        id=song_id,
        batch_id=batch_id,
        user_id=uuid4(),
        title="Already Done",
        album="Album",
        lyrics="la la",
        batch_index=0,
    )
    batch = Batch(id=batch_id, user_id=song.user_id, ok_profile_id=uuid4(), song_count=1)
    existing = SunoTask(song_id=song_id, status=TaskStatus.SUCCESS)
    batch_repo.get_latest_suno_task_for_song = AsyncMock(return_value=existing)

    task_id = await service._submit_song_to_suno(
        song=song,
        batch=batch,
        user_id=str(song.user_id),
        model="V6",
    )

    assert task_id == str(existing.id)
    generation_service.submit_suno.assert_not_awaited()
    batch_repo.link_suno_task.assert_not_awaited()


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
    batch_id = uuid4()
    ok_profile_id = uuid4()
    alt_profile_id = uuid4()
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
                description_id=UUID("00000000-0000-0000-0000-000000000004"),
                structure_id=UUID("00000000-0000-0000-0000-000000000005"),
                status="pending",
            ),
        ]
    )
    batch_repo.get_batch_by_id = AsyncMock(
        return_value=SimpleNamespace(
            id=batch_id,
            ok_profile_id=ok_profile_id,
            alt_profile_id=alt_profile_id,
        )
    )
    batch_repo.update_batch_status = AsyncMock()
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()
    credit_service.get_balance = AsyncMock(return_value=0)
    enforcement_service = AsyncMock()
    enforcement_service.deduct_for_operation = AsyncMock(return_value=0)
    enforcement_service.attribute_secondary_daily_usage = AsyncMock()

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

    await service.orchestrate_drafts(
        batch_id=batch_id,
        user_id="00000000-0000-0000-0000-000000000001",
        draft_requests=[
            DraftRequest(
                language="en",
                creativity_level=55,
                description="EDM / Workout Gym",
                structure="[Verse]\n[Chorus]",
            )
        ],
        channel_profile_id=ok_profile_id,
    )

    assert enforcement_service.deduct_for_operation.await_count == 3
    assert generation_service.submit_draft.await_args.kwargs.get("skip_pricing") is True
    enforcement_service.attribute_secondary_daily_usage.assert_awaited_once_with(
        UUID("00000000-0000-0000-0000-000000000001"),
        alt_profile_id,
        "draft",
        count=3,
    )


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
    batch_repo.update_song_draft = AsyncMock()
    batch_repo.update_song_status = AsyncMock()

    async def _claim(_batch_id, *, ok_album, alt_album):
        return ok_album, alt_album

    batch_repo.claim_batch_channel_albums = AsyncMock(side_effect=_claim)
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

    batch_repo.claim_batch_channel_albums.assert_awaited_once_with(
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

    class _FakeRotation:
        async def pick_sample_path(self, *, settings, kind, exclude=None):
            return str(bg_sample) if kind == ImageKind.BACKGROUND else str(th_sample)

    service._image_sample_rotation = _FakeRotation()

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
    from platform_api.services.suno_blocklist_service import SunoBlocklistService
    from platform_api.tests.test_suno_blocklist_service import FakeSunoBlocklistRepo

    monkeypatch.setattr(
        "platform_api.dependencies.get_suno_blocklist_service",
        lambda: SunoBlocklistService(FakeSunoBlocklistRepo()),
    )
    batch_id = uuid4()
    song_id = uuid4()
    task_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    batch = SimpleNamespace(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        alt_profile_id=UUID("00000000-0000-0000-0000-000000000003"),
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


def test_build_draft_requests_preserves_suno_structure_mode() -> None:
    batch = Batch(song_count=2, structure_mode="suno")
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
    assert all(request.structure_mode == "suno" for request in requests)


@pytest.mark.asyncio
async def test_create_batch_rejects_structure_id_for_suno_mode(
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
    with pytest.raises(ValidationError, match="structure_id must be null"):
        await service.create_batch(
            user_id="00000000-0000-0000-0000-000000000001",
            ok_profile_id="00000000-0000-0000-0000-000000000002",
            alt_profile_id="00000000-0000-0000-0000-000000000003",
            structure_id="00000000-0000-0000-0000-000000000099",
            structure_mode="suno",
            song_count=1,
            from_date=date(2026, 8, 1),
            to_date=date(2026, 8, 1),
        )
    batch_repo.create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_batch_rejects_shuffle_for_suno_mode(
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
    with pytest.raises(ValidationError, match="shuffle_structure cannot be enabled"):
        await service.create_batch(
            user_id="00000000-0000-0000-0000-000000000001",
            ok_profile_id="00000000-0000-0000-0000-000000000002",
            alt_profile_id="00000000-0000-0000-0000-000000000003",
            structure_mode="suno",
            shuffle_structure=True,
            song_count=1,
            from_date=date(2026, 8, 1),
            to_date=date(2026, 8, 1),
        )
    batch_repo.create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_batch_suno_mode_ignores_settings_shuffle_structure(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    """Saved shuffleStructure must not assign template ids under structure_mode=suno."""
    prompt_service.list_structures_workspace = AsyncMock(
        return_value=[SimpleNamespace(id=uuid4(), name="S1")]
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
        structure_mode="suno",
        shuffle_structure=False,
        song_count=3,
        language="en",
        creativity_level=60,
        pairing_mode="match_key",
        from_date=date(2026, 8, 1),
        to_date=date(2026, 8, 1),
    )

    created_songs = batch_repo.create_songs.await_args.args[0]
    assert [song.structure_id for song in created_songs] == [None, None, None]
    prompt_service.list_structures_workspace.assert_not_awaited()


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
async def test_build_batch_redownload_plan_ignores_downloaded_flag(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    """Redownload plan must include tracks already marked downloaded server-side.

    Those flags describe the OLD (possibly bad/full-drive) folder — the whole point of
    "change run folder + resume" is to re-fetch into a NEW folder regardless.
    """
    user_id = uuid4()
    batch_id = uuid4()
    batch = Batch(id=batch_id, user_id=user_id, ok_profile_id=uuid4(), song_count=2)
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.list_suno_audio_for_batch = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "song_id": uuid4(),
                "title": "Shadow Rebels",
                "audio_url_ok": "https://cdn.example.com/shadow-rebels.mp3",
                "audio_url_alt": None,
                "batch_index": 0,
            },
            {
                "id": uuid4(),
                "song_id": uuid4(),
                "title": "Midnight Drive",
                "audio_url_ok": None,
                "audio_url_alt": "https://cdn.example.com/midnight-drive-alt.mp3",
                "batch_index": 1,
            },
        ]
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )

    ok_items = await service.build_batch_redownload_plan(
        user_id=str(user_id),
        batch_id=batch_id,
        role="OK",
        run_dir="E:/NewFolder",
    )
    assert len(ok_items) == 1
    assert ok_items[0]["title"] == "Shadow Rebels"
    assert ok_items[0]["download_url"] == "https://cdn.example.com/shadow-rebels.mp3"
    assert ok_items[0]["target_path"].endswith("1. Shadow Rebels_OK.mp3")

    alt_items = await service.build_batch_redownload_plan(
        user_id=str(user_id),
        batch_id=batch_id,
        role="ALT",
        run_dir="E:/NewFolder",
    )
    assert len(alt_items) == 1
    assert alt_items[0]["title"] == "Midnight Drive"
    assert alt_items[0]["target_path"].endswith("2. Midnight Drive_Alt.mp3")


@pytest.mark.asyncio
async def test_build_batch_redownload_plan_synthesizes_tempfile_url_from_audio_id(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    """Success rows with audio_id_alt but empty audio_url_alt remain downloadable."""
    user_id = uuid4()
    batch_id = uuid4()
    task_id = uuid4()
    batch = Batch(id=batch_id, user_id=user_id, ok_profile_id=uuid4(), song_count=1)
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.update_status = AsyncMock()
    batch_repo.list_suno_audio_for_batch = AsyncMock(
        return_value=[
            {
                "id": task_id,
                "song_id": uuid4(),
                "title": "Beneath Fading Golden Steel",
                "audio_url_ok": "https://cdn1.suno.ai/ok.mp3",
                "audio_url_alt": None,
                "audio_id_ok": "ok-id",
                "audio_id_alt": "25d27d13-10a9-4b73-9e2e-b344da4cf0c8",
                "batch_index": 4,
            }
        ]
    )
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    service._resolve_redownload_storage_keys = AsyncMock(return_value={})  # type: ignore[method-assign]

    items = await service.build_batch_redownload_plan(
        user_id=str(user_id),
        batch_id=batch_id,
        role="ALT",
        run_dir=r"E:\SUNO\bass-gravity\run",
    )
    assert len(items) == 1
    assert (
        items[0]["download_url"]
        == "https://tempfile.aiquickdraw.com/r/25d27d13-10a9-4b73-9e2e-b344da4cf0c8.mp3"
    )
    batch_repo.update_status.assert_awaited()


@pytest.mark.asyncio
async def test_build_batch_redownload_plan_prefers_suno_url_with_backblaze_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    """Suno's URL (retained 14 days) is the primary source; the durable Backblaze
    copy only rides along as `fallback_download_url` for the desktop client to use
    if the Suno URL turns out to be dead — never fetched from Backblaze proactively."""
    user_id = uuid4()
    batch_id = uuid4()
    task_id = uuid4()
    batch = Batch(id=batch_id, user_id=user_id, ok_profile_id=uuid4(), song_count=1)
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.list_suno_audio_for_batch = AsyncMock(
        return_value=[
            {
                "id": task_id,
                "song_id": uuid4(),
                "title": "Shadow Rebels",
                "audio_url_ok": "https://suno.cdn.example.com/shadow-rebels.mp3",
                "audio_url_alt": None,
                "batch_index": 0,
            }
        ]
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    monkeypatch.setattr(
        service,
        "_resolve_redownload_storage_keys",
        AsyncMock(return_value={str(task_id): "https://b2.example.com/signed/shadow-rebels.mp3"}),
    )

    items = await service.build_batch_redownload_plan(
        user_id=str(user_id),
        batch_id=batch_id,
        role="OK",
        run_dir="E:/NewFolder",
    )
    assert len(items) == 1
    assert items[0]["download_url"] == "https://suno.cdn.example.com/shadow-rebels.mp3"
    assert items[0]["fallback_download_url"] == "https://b2.example.com/signed/shadow-rebels.mp3"


@pytest.mark.asyncio
async def test_build_batch_redownload_plan_uses_backblaze_when_suno_url_missing(
    monkeypatch: pytest.MonkeyPatch,
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    """If Suno no longer has the audio at all (e.g. outside its 14-day retention),
    the Backblaze copy becomes the primary `download_url` with no fallback left."""
    user_id = uuid4()
    batch_id = uuid4()
    task_id = uuid4()
    batch = Batch(id=batch_id, user_id=user_id, ok_profile_id=uuid4(), song_count=1)
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.list_suno_audio_for_batch = AsyncMock(
        return_value=[
            {
                "id": task_id,
                "song_id": uuid4(),
                "title": "Shadow Rebels",
                "audio_url_ok": None,
                "audio_url_alt": None,
                "batch_index": 0,
            }
        ]
    )

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    monkeypatch.setattr(
        service,
        "_resolve_redownload_storage_keys",
        AsyncMock(return_value={str(task_id): "https://b2.example.com/signed/shadow-rebels.mp3"}),
    )

    items = await service.build_batch_redownload_plan(
        user_id=str(user_id),
        batch_id=batch_id,
        role="OK",
        run_dir="E:/NewFolder",
    )
    assert len(items) == 1
    assert items[0]["download_url"] == "https://b2.example.com/signed/shadow-rebels.mp3"
    assert items[0]["fallback_download_url"] is None


@pytest.mark.asyncio
async def test_resolve_redownload_storage_keys_returns_empty_when_pool_unavailable(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    """Any Backblaze-lookup failure (e.g. DB pool unavailable in this call path)
    must never break the base Suno-URL redownload flow."""
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    result = await service._resolve_redownload_storage_keys(
        [{"id": uuid4()}], variant="ok"
    )
    assert result == {}


@pytest.mark.asyncio
async def test_build_batch_redownload_plan_empty_run_dir_returns_nothing(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
) -> None:
    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
    )
    items = await service.build_batch_redownload_plan(
        user_id=str(uuid4()),
        batch_id=uuid4(),
        role="OK",
        run_dir="   ",
    )
    assert items == []
    batch_repo.get_batch_for_user.assert_not_awaited()


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

@pytest.mark.asyncio
async def test_create_manual_image_generation_creates_batch_and_runs_clicked_kind(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    profile_id = uuid4()
    profile = SimpleNamespace(
        id=profile_id,
        image_config={
            "provider": "fal",
            "background_prompt": "BG profile",
            "thumbnail_prompt": "TH profile",
            "resolution": "1920x1080",
            "style_strength": 80,
        },
    )
    profile_repo.list_for_user = AsyncMock(return_value=[profile])
    profile_repo.get_by_id_for_user = AsyncMock(return_value=profile)
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageSourceMode": "ai",
            "imageBackgroundSourceMode": "prompt_only",
            "imageThumbnailSourceMode": "prompt_only",
            "imageBackgroundPrompt": "Neon skyline",
            "imageThumbnailPrompt": "Bold title card",
            "outputResolution": "1920x1080",
            "styleStrength": 80,
        }
    )
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.create_image_jobs = AsyncMock(side_effect=lambda jobs: jobs)

    service = BatchService(
        batch_repo=batch_repo,
        credit_service=credit_service,
        pricing_service=pricing_service,
        generation_service=generation_service,
        profile_repo=profile_repo,
        ai_routing_service=ai_routing_service,
        prompt_service=prompt_service,
        settings_service=settings_service,
    )
    service._schedule_image_jobs_run = AsyncMock()
    result = await service.create_manual_image_generation(
        user_id="00000000-0000-0000-0000-000000000001",
        kind="background",
        prompt="City lights",
    )

    assert result["album_label"] == "Not available"
    assert result["kind"] == "background"
    created_batch = batch_repo.create_batch.await_args.args[0]
    assert created_batch.status == "manual_image"
    assert created_batch.song_count == 0
    assert created_batch.ok_album == "Not available"
    created_jobs = batch_repo.create_image_jobs.await_args.args[0]
    assert len(created_jobs) == 2
    assert {job.kind for job in created_jobs} == {ImageKind.BACKGROUND, ImageKind.THUMBNAIL}
    assert all(job.status == TaskStatus.PENDING for job in created_jobs)
    service._schedule_image_jobs_run.assert_awaited_once()
    schedule_kwargs = service._schedule_image_jobs_run.await_args.kwargs
    assert schedule_kwargs["job_ids"] == [result["job_id"]]


@pytest.mark.asyncio
async def test_create_manual_image_generation_thumbnail_schedules_bg_then_th(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    profile_id = uuid4()
    profile = SimpleNamespace(
        id=profile_id,
        image_config={
            "provider": "fal",
            "background_prompt": "BG profile",
            "thumbnail_prompt": "TH profile",
            "resolution": "1920x1080",
            "style_strength": 80,
        },
    )
    profile_repo.list_for_user = AsyncMock(return_value=[profile])
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageSourceMode": "ai",
            "imageBackgroundSourceMode": "prompt_only",
            "imageThumbnailSourceMode": "prompt_only",
            "imageBackgroundPrompt": "Neon skyline",
            "imageThumbnailPrompt": "Bold title card",
            "outputResolution": "1920x1080",
            "styleStrength": 80,
        }
    )
    batch_repo.update_batch_channel_albums = AsyncMock()
    batch_repo.create_image_jobs = AsyncMock(side_effect=lambda jobs: jobs)
    service = BatchService(
        batch_repo=batch_repo,
        credit_service=credit_service,
        pricing_service=pricing_service,
        generation_service=generation_service,
        profile_repo=profile_repo,
        ai_routing_service=ai_routing_service,
        prompt_service=prompt_service,
        settings_service=settings_service,
    )
    service._schedule_image_jobs_run = AsyncMock()
    result = await service.create_manual_image_generation(
        user_id="00000000-0000-0000-0000-000000000001",
        kind="thumbnail",
        prompt="Title card",
    )
    created_jobs = batch_repo.create_image_jobs.await_args.args[0]
    bg = next(job for job in created_jobs if job.kind == ImageKind.BACKGROUND)
    th = next(job for job in created_jobs if job.kind == ImageKind.THUMBNAIL)
    assert th.source_job_id == bg.id
    schedule_kwargs = service._schedule_image_jobs_run.await_args.kwargs
    assert schedule_kwargs["job_ids"] == [str(bg.id), str(th.id)]
    assert result["job_id"] == str(th.id)


@pytest.mark.asyncio
async def test_create_manual_image_generation_blocks_personal_reference(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    profile_repo.list_for_user = AsyncMock(
        return_value=[SimpleNamespace(id=uuid4(), image_config={})]
    )
    settings_service.get_merged_settings = AsyncMock(
        return_value={
            "imageSourceMode": "ai",
            "imageBackgroundSourceMode": "personal_reference",
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
    with pytest.raises(ValidationError, match="not available yet"):
        await service.create_manual_image_generation(
            user_id="00000000-0000-0000-0000-000000000001",
            kind="background",
        )
    batch_repo.create_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_local_progress_does_not_rewrite_batch_run_dir_by_default(
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
    profile_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    legacy = r"D:\OldPC\Suno\bass-drive\2026-07-13_Neon-Nights"
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=profile_id,
        alt_profile_id=None,
        song_count=1,
        status="processing",
        ok_run_dir=legacy,
        alt_run_dir=None,
    )
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.update_batch_run_directories = AsyncMock()
    batch_repo.refresh_batch_status = AsyncMock()
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
    service.refresh_batch_status = AsyncMock()

    updated = await service.sync_local_progress_from_desktop(
        user_id=str(user_id),
        items=[
            {
                "batch_id": str(batch_id),
                "profile_id": str(profile_id),
                "role": "OK",
                "run_dir": r"C:\Users\Alice\Camxora\Media\Suno\bass-drive\2026-07-13_Neon-Nights",
            }
        ],
    )

    assert updated == 1
    batch_repo.upsert_batch_channel_assets.assert_awaited_once()
    batch_repo.update_batch_run_directories.assert_not_awaited()
    assert batch.ok_run_dir == legacy


@pytest.mark.asyncio
async def test_sync_local_progress_persists_batch_run_dir_when_flagged(
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
    profile_id = uuid4()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    batch = Batch(
        id=batch_id,
        user_id=user_id,
        ok_profile_id=profile_id,
        alt_profile_id=None,
        song_count=1,
        status="processing",
        ok_run_dir=r"D:\OldPC\Suno\bass-drive\2026-07-13_Neon-Nights",
        alt_run_dir=r"D:\OldPC\Suno\alt\2026-07-13_Other",
    )
    batch_repo.get_batch_for_user = AsyncMock(return_value=batch)
    batch_repo.update_batch_run_directories = AsyncMock()
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
    service.refresh_batch_status = AsyncMock()

    updated = await service.sync_local_progress_from_desktop(
        user_id=str(user_id),
        items=[
            {
                "batch_id": str(batch_id),
                "profile_id": str(profile_id),
                "role": "OK",
                "run_dir": r"E:\NewDrive\Suno\bass-drive\2026-07-13_Neon-Nights",
                "persist_batch_run_dir": True,
            }
        ],
    )

    assert updated == 1
    batch_repo.update_batch_run_directories.assert_awaited_once()
    kwargs = batch_repo.update_batch_run_directories.await_args.kwargs
    assert kwargs["ok_run_dir"] == r"bass-drive\2026-07-13_Neon-Nights"
    # Other role left untouched (still legacy absolute).
    assert kwargs["alt_run_dir"] == r"D:\OldPC\Suno\alt\2026-07-13_Other"


@pytest.mark.asyncio
async def test_preflight_includes_video_and_merge_credits(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    """Preflight must price local export/merge so plans cannot start short."""
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
    result = await service.preflight_music_plan(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_ids=["00000000-0000-0000-0000-000000000002"],
        alt_profile_ids=["00000000-0000-0000-0000-000000000003"],
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        auto_video_after_suno=True,
        auto_merge_after_video=True,
    )
    assert result["can_generate"] is True
    # 4 songs x 2 channels = 8 exports; 1 batch x 2 channels = 2 merges.
    assert result["video_ops"] == 8
    assert result["merge_ops"] == 2
    assert result["video_wallet_cost"] == 24
    assert result["merge_wallet_cost"] == 6


@pytest.mark.asyncio
async def test_preflight_blocks_when_only_video_credits_missing(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    """A wallet that covers music/images but not export/merge must block upfront."""
    credit_service.get_balance = AsyncMock(return_value=0)
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
    result = await service.preflight_music_plan(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_ids=["00000000-0000-0000-0000-000000000002"],
        alt_profile_ids=["00000000-0000-0000-0000-000000000003"],
        from_date=date(2026, 6, 25),
        to_date=date(2026, 6, 25),
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        auto_video_after_suno=True,
        auto_merge_after_video=True,
    )
    assert result["can_generate"] is False
    assert "video export" in result["reason"]
    assert "merge" in result["reason"]
    assert result["video_ops"] == 8
    assert result["merge_ops"] == 2


@pytest.mark.asyncio
async def test_preflight_blocks_on_daily_video_cap(
    batch_repo: AsyncMock,
    credit_service: AsyncMock,
    pricing_service: AsyncMock,
    generation_service: AsyncMock,
    profile_repo: AsyncMock,
    ai_routing_service: AsyncMock,
    prompt_service: AsyncMock,
    settings_service: AsyncMock,
) -> None:
    """Account-wide daily video cap must be preflighted with a clear reason."""
    enforcement_service = AsyncMock()
    enforcement_service.enforce_fail_absorb_budget = AsyncMock()
    enforcement_service._resolve_subscription_context = AsyncMock(return_value=None)

    async def _enforce_plan_quotas(
        *,
        user_id,
        channel_profile_id,
        operation_type,
        subscription_context=None,
        additional_count=1,
        wallet_bypass_credits=None,
    ):
        if operation_type == "video":
            raise QuotaExceededError(
                "Daily generation quota exceeded.",
                details={"error_code": "DAILY_QUOTA_EXCEEDED", "operation_type": "video"},
            )

    enforcement_service._enforce_plan_quotas = AsyncMock(side_effect=_enforce_plan_quotas)

    service = make_service(
        batch_repo,
        credit_service,
        pricing_service,
        generation_service,
        profile_repo,
        ai_routing_service,
        prompt_service,
        settings_service,
        enforcement_service,
    )
    today = billing_today()
    result = await service.preflight_music_plan(
        user_id="00000000-0000-0000-0000-000000000001",
        ok_profile_ids=["00000000-0000-0000-0000-000000000002"],
        alt_profile_ids=["00000000-0000-0000-0000-000000000003"],
        from_date=today,
        to_date=today,
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        auto_video_after_suno=True,
        auto_merge_after_video=True,
    )
    assert result["can_generate"] is False
    assert "video export" in result["reason"]
    assert "8" in result["reason"]
