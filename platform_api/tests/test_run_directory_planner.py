from platform_api.services.run_directory_planner import (
    build_run_folder_label,
    infer_alt_run_dir_from_ok,
    normalize_run_key,
    plan_relative_run_directories,
    plan_run_directories,
    resolve_channel_run_dir,
)


def test_build_run_folder_label_prefers_date_first() -> None:
    assert build_run_folder_label(run_date="2026-07-12", album="Midnight Drive") == "2026-07-12_Midnight-Drive"
    assert build_run_folder_label(run_date="2026-07-12", album="") == "2026-07-12"


def test_normalize_run_key_strips_machine_absolute_paths() -> None:
    assert (
        normalize_run_key(r"C:\Users\Alice\AppData\Local\Camxora\Media\Suno\bass-drive\2026-07-12_02")
        == r"bass-drive\2026-07-12_02"
    )
    assert normalize_run_key(r"bass-drive\2026-07-12_02") == r"bass-drive\2026-07-12_02"
    assert normalize_run_key("") is None


def test_plan_run_directories_uses_profile_folders() -> None:
    planned = plan_run_directories(
        base_dir=r"D:\MusicGenerator\downloads\suno",
        ok_profile_folder="bass-drive",
        alt_profile_folder="beattok-remixes",
        run_label=build_run_folder_label(run_date="2026-07-12", album="Midnight Drive"),
    )
    assert planned.ok_run_dir == r"bass-drive\2026-07-12_Midnight-Drive"
    assert planned.alt_run_dir == r"beattok-remixes\2026-07-12_Midnight-Drive"


def test_plan_relative_run_directories_needs_no_machine_base() -> None:
    planned = plan_relative_run_directories(
        ok_profile_folder="bass-drive",
        alt_profile_folder="beattok-remixes",
        run_label=build_run_folder_label(run_date="2026-07-12", album="Midnight Drive"),
    )
    assert planned.ok_run_dir == r"bass-drive\2026-07-12_Midnight-Drive"
    assert planned.alt_run_dir == r"beattok-remixes\2026-07-12_Midnight-Drive"


def test_plan_run_directories_allows_distinct_channel_labels() -> None:
    planned = plan_run_directories(
        base_dir=r"D:\MusicGenerator\downloads\suno",
        ok_profile_folder="bass-drive",
        alt_profile_folder="beattok-remixes",
        run_label="2026-07-12",
        ok_run_label=build_run_folder_label(run_date="2026-07-12", album="Midnight Drive"),
        alt_run_label=build_run_folder_label(run_date="2026-07-12", album="Sunset Pulse"),
    )
    assert planned.ok_run_dir == r"bass-drive\2026-07-12_Midnight-Drive"
    assert planned.alt_run_dir == r"beattok-remixes\2026-07-12_Sunset-Pulse"
    assert planned.ok_run_dir != planned.alt_run_dir


def test_infer_alt_run_dir_from_ok() -> None:
    inferred = infer_alt_run_dir_from_ok(
        ok_run_dir=r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
        alt_profile_folder="beattok-remixes",
    )
    assert inferred == r"beattok-remixes\2026-07-12_02"
    assert (
        infer_alt_run_dir_from_ok(
            ok_run_dir=r"bass-drive\2026-07-12_02",
            alt_profile_folder="beattok-remixes",
        )
        == r"beattok-remixes\2026-07-12_02"
    )


def test_resolve_channel_run_dir_does_not_fallback_alt_to_ok() -> None:
    resolved = resolve_channel_run_dir(
        role="ALT",
        ok_run_dir=r"bass-drive\2026-07-12_02",
        alt_run_dir=r"bass-drive\2026-07-12_02",
        alt_profile_folder="beattok-remixes",
    )
    assert resolved == r"beattok-remixes\2026-07-12_02"


def test_resolve_history_output_dirs_uses_batch_fallback_and_alt_inference() -> None:
    from platform_api.services.run_directory_planner import resolve_history_output_dirs

    ok_dir, alt_dir = resolve_history_output_dirs(
        song_output_dir_ok=None,
        song_output_dir_alt=None,
        batch_ok_run_dir=r"bass-drive\2026-07-12_02",
        batch_alt_run_dir=r"bass-drive\2026-07-12_02",
        alt_profile_folder="beattok-remixes",
    )
    assert ok_dir == r"bass-drive\2026-07-12_02"
    assert alt_dir == r"beattok-remixes\2026-07-12_02"
