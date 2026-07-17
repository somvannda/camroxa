"""Manual asset path tests."""

from shared.lib.manual_asset_paths import inspect_manual_asset_files, normalize_image_source_mode


def test_inspect_manual_asset_files_ready() -> None:
    inspection = inspect_manual_asset_files(
        "C:/runs/demo",
        [
            "C:/runs/demo/background-16x9.png",
            "C:/runs/demo/background-9x16.jpg",
            "C:/runs/demo/thumbnail-16x9.webp",
            "C:/runs/demo/thumbnail-9x16.jpeg",
        ],
    )
    assert inspection.ready
    assert inspection.ready_count == 4
    assert inspection.total == 4
    assert not inspection.missing_labels


def test_inspect_manual_asset_files_missing() -> None:
    inspection = inspect_manual_asset_files("C:/runs/demo", ["C:/runs/demo/background-16x9.png"])
    assert not inspection.ready
    assert inspection.ready_count == 1
    assert len(inspection.missing_labels) == 3


def test_normalize_image_source_mode() -> None:
    assert normalize_image_source_mode("manual") == "manual"
    assert normalize_image_source_mode("AI") == "ai"
    assert normalize_image_source_mode(None) == "ai"
