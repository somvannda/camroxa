from uuid import UUID, uuid4

from platform_api.models.enums import ChannelRole
from platform_api.services.channel_asset_service import (
    build_batch_channel_assets,
    compute_long_ready,
    compute_reel_ready,
    merge_channel_asset_paths,
    resolve_channel_asset_paths,
)


def test_resolve_channel_asset_paths_and_readiness(tmp_path) -> None:
    run_dir = tmp_path / "Primary" / "2026-06-29"
    run_dir.mkdir(parents=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg16")
    (run_dir / "background-9x16.png").write_bytes(b"bg9")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th16")
    (run_dir / "thumbnail-9x16.png").write_bytes(b"th9")

    asset_paths = resolve_channel_asset_paths(str(run_dir))

    assert asset_paths["background_16x9_path"] == str((run_dir / "background-16x9.png").resolve())
    assert asset_paths["thumbnail_9x16_path"] == str((run_dir / "thumbnail-9x16.png").resolve())
    assert compute_long_ready(asset_paths) is True
    assert compute_reel_ready(asset_paths) is True


def test_resolve_channel_asset_paths_prefers_role_suffix_when_disambiguated(tmp_path) -> None:
    run_dir = tmp_path / "shared"
    run_dir.mkdir(parents=True)
    (run_dir / "background-16x9-ok.png").write_bytes(b"ok")
    (run_dir / "background-16x9-alt.png").write_bytes(b"alt")
    (run_dir / "background-16x9.png").write_bytes(b"legacy")

    ok_paths = resolve_channel_asset_paths(
        str(run_dir),
        channel_role=ChannelRole.OK,
        role_disambiguate=True,
    )
    alt_paths = resolve_channel_asset_paths(
        str(run_dir),
        channel_role=ChannelRole.ALT,
        role_disambiguate=True,
    )

    assert ok_paths["background_16x9_path"] == str((run_dir / "background-16x9-ok.png").resolve())
    assert alt_paths["background_16x9_path"] == str((run_dir / "background-16x9-alt.png").resolve())


def test_build_batch_channel_assets_keeps_partial_readiness(tmp_path) -> None:
    run_dir = tmp_path / "Primary" / "2026-06-29"
    run_dir.mkdir(parents=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg16")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th16")

    asset = build_batch_channel_assets(
        batch_id=uuid4(),
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        profile_id=UUID("00000000-0000-0000-0000-000000000002"),
        role=ChannelRole.OK,
        run_dir=str(run_dir),
        source_mode="manual",
    )

    assert asset.background_16x9_path == str((run_dir / "background-16x9.png").resolve())
    assert asset.thumbnail_16x9_path == str((run_dir / "thumbnail-16x9.png").resolve())
    assert asset.background_9x16_path is None
    assert asset.thumbnail_9x16_path is None


def test_merge_channel_asset_paths_ignores_missing_persisted_paths(tmp_path) -> None:
    run_dir = tmp_path / "Primary" / "2026-06-29"
    run_dir.mkdir(parents=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg16")

    merged = merge_channel_asset_paths(
        str(run_dir),
        {
            "background_16x9_path": str((run_dir / "background-16x9.png").resolve()),
            "thumbnail_16x9_path": str(tmp_path / "missing-thumbnail-16x9.png"),
        },
    )

    assert merged["background_16x9_path"] == str((run_dir / "background-16x9.png").resolve())
    assert merged["thumbnail_16x9_path"] is None
    # Background alone is enough for export / long_ready.
    assert compute_long_ready(merged) is True
    from platform_api.services.channel_asset_service import compute_youtube_long_ready

    assert compute_youtube_long_ready(merged) is False


def test_compute_long_ready_is_background_only() -> None:
    assert compute_long_ready({"background_16x9_path": "/bg.png", "thumbnail_16x9_path": None}) is True
    assert compute_long_ready({"background_16x9_path": None, "thumbnail_16x9_path": "/th.png"}) is False
    assert compute_reel_ready({"background_9x16_path": "/bg.png", "thumbnail_9x16_path": None}) is True
    assert compute_reel_ready({"background_9x16_path": None, "thumbnail_9x16_path": "/th.png"}) is False


def test_trust_persisted_asset_paths_keeps_windows_desktop_paths() -> None:
    from platform_api.services.channel_asset_service import (
        overlay_live_channel_asset_paths,
        trust_persisted_asset_paths,
    )

    persisted = {
        "background_16x9_path": r"D:\SUNO\neon-kicks\2026-09-02_Album\background-16x9.png",
        "thumbnail_16x9_path": r"D:\SUNO\neon-kicks\2026-09-02_Album\thumbnail-16x9.png",
    }
    trusted = trust_persisted_asset_paths(persisted)
    assert trusted["background_16x9_path"]
    assert trusted["background_16x9_path"].endswith("background-16x9.png")
    assert compute_long_ready(trusted) is True

    # API host cannot see D:\ — must still keep the DB path.
    overlaid = overlay_live_channel_asset_paths(r"D:\SUNO\neon-kicks\2026-09-02_Album", persisted)
    assert compute_long_ready(overlaid) is True


def test_mark_ready_from_image_jobs_without_local_files() -> None:
    from platform_api.services.channel_asset_service import mark_ready_from_image_jobs

    key = ("batch-1", "profile-1", "OK")
    assets = {
        key: {
            "background_16x9_path": None,
            "background_9x16_path": None,
            "thumbnail_16x9_path": None,
            "thumbnail_9x16_path": None,
            "long_ready": False,
            "reel_ready": False,
        }
    }
    groups = {
        key: {
            "background": {"ready": 1, "total": 1},
            "thumbnail": {"ready": 1, "total": 1},
        }
    }
    mark_ready_from_image_jobs(assets, groups)
    assert assets[key]["long_ready"] is True
    assert assets[key]["background_16x9_path"]


def test_mark_ready_from_image_jobs_skips_when_kind_still_has_failures() -> None:
    from platform_api.services.channel_asset_service import mark_ready_from_image_jobs

    key = ("batch-1", "profile-1", "OK")
    assets = {
        key: {
            "background_16x9_path": None,
            "background_9x16_path": None,
            "thumbnail_16x9_path": None,
            "thumbnail_9x16_path": None,
            "long_ready": False,
            "reel_ready": False,
        }
    }
    groups = {
        key: {
            "background": {"ready": 1, "total": 1, "failed": 1},
            "thumbnail": {"ready": 0, "total": 1, "failed": 1},
        }
    }
    mark_ready_from_image_jobs(assets, groups)
    assert assets[key]["long_ready"] is False
    assert assets[key]["background_16x9_path"] is None
