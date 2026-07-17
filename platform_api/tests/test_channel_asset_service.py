from uuid import UUID, uuid4

from platform_api.models.enums import ChannelRole
from platform_api.services.channel_asset_service import (
    build_batch_channel_assets,
    compute_long_ready,
    compute_reel_ready,
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
