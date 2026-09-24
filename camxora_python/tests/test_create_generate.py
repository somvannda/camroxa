"""Create page generate payload and folder mapping."""

from __future__ import annotations

from pathlib import Path

from shared.lib.create_generate import (
    CreateGeneratePlan,
    clip_folder_assignment,
    draft_description,
    draft_prompt,
    planned_song_count,
    safe_audio_filename,
    validate_create_plan,
    version_folders,
    web_generate_body,
)


def _plan(**overrides: object) -> CreateGeneratePlan:
    values: dict[str, object] = {
        "mode": "simple",
        "model": "V6",
        "title": "Night Drive",
        "lyrics": "",
        "styles": "synthwave",
        "prompt": "A rainy-night song",
        "negative_tags": "",
        "vocal_gender": "m",
        "style_weight": 0.5,
        "weirdness": 0.4,
        "audio_weight": 0.6,
        "song_count": 2,
        "songs_per_day": 2,
        "planned_days": 1,
        "save_folder": "D:/Music/Out",
        "version_mode": "keep",
        "language": "en",
        "secondary_language": "",
        "creativity": 55,
        "auto_image": False,
        "auto_video": False,
        "auto_merge": False,
        "template_v1_id": "",
        "template_v2_id": "",
    }
    values.update(overrides)
    return CreateGeneratePlan(**values)  # type: ignore[arg-type]


def test_planned_song_count_multiplies_days() -> None:
    assert planned_song_count(10, "2026-08-24", "2026-08-25") == 20
    assert planned_song_count(4, "2026-08-24", "2026-08-24") == 4


def test_simple_payload_uses_web_create_fields() -> None:
    body = web_generate_body(_plan())
    assert body["mode"] == "simple"
    assert body["prompt"] == "A rainy-night song"
    assert body["vocal_gender"] == "m"
    assert body["style_weight"] == 0.5
    assert "workspace_id" not in body


def test_advanced_payload_sends_lyrics() -> None:
    body = web_generate_body(
        _plan(mode="advanced", lyrics="Verse one", prompt="", styles="rock"),
        title="Night Drive",
        lyrics="Verse one",
    )
    assert body["mode"] == "advanced"
    assert body["lyrics"] == "Verse one"
    assert body["prompt"] == ""
    assert body["instrumental"] is False


def test_advanced_does_not_require_lyrics_upfront() -> None:
    plan = _plan(mode="advanced", lyrics="", prompt="", styles="pop")
    assert validate_create_plan(plan) is None
    assert "Create an original" in draft_description(_plan(styles="", prompt="", title=""))


def test_draft_prompt_uses_web_create_assist_not_music_draft() -> None:
    prompt = draft_prompt(_plan(mode="advanced", styles="synthwave", language="km", secondary_language="en"))
    assert "synthwave" in prompt
    assert "km" in prompt
    assert "en" in prompt
    assert "bilingual" in prompt


def test_validate_requires_save_folder_and_prompt() -> None:
    assert "Save to" in (validate_create_plan(_plan(save_folder="")) or "")
    assert "Enter styles" in (validate_create_plan(_plan(prompt="")) or "")


def test_version_folders_and_keep_assignment(tmp_path: Path) -> None:
    v1, v2 = version_folders(str(tmp_path))
    assert v1.name == "Version 1"
    assert v2.name == "Version 2"
    assert clip_folder_assignment("keep") == ("Version 1", "Version 2")
    assert clip_folder_assignment("selective") == ("Version 1", "Version 2")


def test_safe_audio_filename_adds_index_and_task() -> None:
    name = safe_audio_filename("Night / Drive", index=2, song_count=3, task_id="abcd1234-ffff")
    assert name == "Night Drive (2) abcd1234.mp3"


def test_create_history_maps_database_rows(tmp_path: Path) -> None:
    from shared.lib.create_history import (
        download_root_from_file,
        generation_row_state,
        history_file_stem,
        history_slots,
        match_local_audio,
        match_local_files,
        matches_search,
        task_file_token,
    )
    from shared.models.web_music import WebMusicClipResponse, WebMusicGenerationResponse

    assert generation_row_state("failed") == "Failed"
    assert generation_row_state("queued") == "Generating…"
    assert (
        generation_row_state(
            "success",
            [WebMusicClipResponse(variant="ok", ready=True)],
        )
        == "Ready"
    )
    assert matches_search("Night Drive", "drive")
    assert not matches_search("Night Drive", "rain")
    assert task_file_token("abcd1234-ffff-0000") == "abcd1234"
    from shared.lib.create_history import is_encrypted_audio_bytes

    assert is_encrypted_audio_bytes(b"CXO1xxxx")
    assert is_encrypted_audio_bytes(b"CXA1xxxx")
    assert not is_encrypted_audio_bytes(b"ID3\x00")

    folder = tmp_path / "Version 1"
    folder.mkdir()
    dest = folder / "Night Drive abcd1234.mp3"
    dest.write_bytes(b"id3")
    lyrics = folder / "Night Drive abcd1234.lrc"
    lyrics.write_text("[00:00.00]night", encoding="utf-8")
    assert match_local_audio(folder, title="Night Drive", task_id="abcd1234-ffff") == str(dest)
    files = match_local_files(folder, title="Night Drive", task_id="abcd1234-ffff")
    assert files["mp3"] == str(dest)
    assert files["lrc"] == str(lyrics)
    assert files["wav"] == ""
    assert files["srt"] == ""
    assert download_root_from_file(str(dest)) == str(tmp_path)

    rows = history_slots(
        [
            WebMusicGenerationResponse(
                id="abcd1234-ffff-0000-0000-000000000001",
                title="Night Drive",
                status="success",
                created_at="2026-08-26T10:00:00+00:00",
                clips=[WebMusicClipResponse(variant="ok", ready=True)],
            )
        ]
    )
    assert rows[0]["title"] == "Night Drive"
    assert rows[0]["state"] == "Ready"
    assert rows[0]["task_id"].startswith("abcd1234")
    stem = history_file_stem("ខ្ញុំមិនចុះចាញ់", "854bc609-973c-4de6-9ec1-356aa6d3992e")
    assert "(1000)" not in stem
    assert stem.endswith("854bc609")


def test_create_clip_download_worker_writes_mp3_without_generate(tmp_path: Path) -> None:
    from features.create.workers.create_generate_worker import CreateClipDownloadWorker

    class FakeApi:
        def download_web_music_clip(self, task_id: str, variant: str = "ok") -> bytes:
            assert task_id == "854bc609-973c-4de6-9ec1-356aa6d3992e"
            assert variant == "ok"
            return b"id3ok"

        def generate_web_music(self, payload):  # noqa: ANN001
            raise AssertionError("click/download must not POST generate")

    saved: list[tuple] = []
    worker = CreateClipDownloadWorker(
        FakeApi(),  # type: ignore[arg-type]
        str(tmp_path),
        "854bc609-973c-4de6-9ec1-356aa6d3992e",
        "Night Drive",
        "mp3",
        "ok",
    )
    worker.file_saved.connect(lambda *args: saved.append(args))
    worker.run()
    assert saved
    assert Path(saved[0][2]).is_file()
    assert "(1000)" not in Path(saved[0][2]).name


def test_create_history_worker_pages_generations() -> None:
    from features.create.workers.create_generate_worker import CreateHistoryWorker
    from shared.models.web_music import (
        WebMusicGenerationListResponse,
        WebMusicGenerationResponse,
    )

    class FakeApi:
        def list_web_music_generations(self, *, limit: int = 100, offset: int = 0):
            items = [
                WebMusicGenerationResponse(id=f"task-{index}", title=f"Song {index}", status="success")
                for index in range(offset, min(offset + limit, 120))
            ]
            return WebMusicGenerationListResponse(items=items, total=120, limit=limit, offset=offset)

    captured: list[object] = []
    worker = CreateHistoryWorker(FakeApi())  # type: ignore[arg-type]
    worker.succeeded.connect(captured.append)
    worker.run()
    assert captured
    items = captured[0]
    assert isinstance(items, list)
    assert len(items) == 120
    assert items[0].title == "Song 0"


def test_estimate_video_merge_ops() -> None:
    from shared.lib.create_generate import estimate_video_merge_ops

    assert estimate_video_merge_ops(_plan(auto_video=False)) == (0, 0)
    assert estimate_video_merge_ops(_plan(song_count=15, auto_video=True, auto_merge=False)) == (30, 0)
    assert estimate_video_merge_ops(_plan(song_count=15, auto_video=True, auto_merge=True)) == (30, 2)


def _quota(**overrides: object):
    from shared.models.platform import QuotaStatusResponse

    values: dict[str, object] = {
        "videos_remaining": None,
        "merges_remaining": None,
        "daily_videos_remaining": None,
        "daily_merges_remaining": None,
        "wallet_balance": 0.0,
    }
    values.update(overrides)
    return QuotaStatusResponse(**values)  # type: ignore[arg-type]


def _costs():
    from shared.models.platform import OperationCostResponse, OperationCostsResponse

    return OperationCostsResponse(
        items=[
            OperationCostResponse(operation_type="video", credits_per_operation=3, available=True),
            OperationCostResponse(
                operation_type="video_merge", credits_per_operation=10, available=True
            ),
        ]
    )


def test_create_preflight_passes_when_quota_covers() -> None:
    from features.create.workers.create_generate_worker import CreateGenerateWorker

    class FakeApi:
        def get_quota_status(self):
            return _quota(
                videos_remaining=100,
                merges_remaining=5,
                daily_videos_remaining=100,
                daily_merges_remaining=5,
                wallet_balance=0.0,
            )

        def get_operation_costs(self):
            return _costs()

    plan = _plan(song_count=15, auto_video=True, auto_merge=True)
    worker = CreateGenerateWorker(FakeApi(), plan)  # type: ignore[arg-type]
    assert worker._preflight_video_merge(plan) is None


def test_create_preflight_blocks_when_video_credits_short() -> None:
    from features.create.workers.create_generate_worker import CreateGenerateWorker

    class FakeApi:
        def get_quota_status(self):
            return _quota(
                videos_remaining=0,
                merges_remaining=0,
                daily_videos_remaining=0,
                daily_merges_remaining=0,
                wallet_balance=1.0,
            )

        def get_operation_costs(self):
            return _costs()

    plan = _plan(song_count=15, auto_video=True, auto_merge=True)
    worker = CreateGenerateWorker(FakeApi(), plan)  # type: ignore[arg-type]
    error = worker._preflight_video_merge(plan)
    assert error is not None
    assert "Not enough credits" in error


def test_create_preflight_wallet_covers_when_quota_exhausted() -> None:
    from features.create.workers.create_generate_worker import CreateGenerateWorker

    class FakeApi:
        def get_quota_status(self):
            # 15 songs x 2 videos x 3 credits + 2 merges x 10 credits = 110.
            return _quota(
                videos_remaining=0,
                merges_remaining=0,
                daily_videos_remaining=0,
                daily_merges_remaining=0,
                wallet_balance=110.0,
            )

        def get_operation_costs(self):
            return _costs()

    plan = _plan(song_count=15, auto_video=True, auto_merge=True)
    worker = CreateGenerateWorker(FakeApi(), plan)  # type: ignore[arg-type]
    assert worker._preflight_video_merge(plan) is None
