from __future__ import annotations

from platform_api.services.client_path_utils import (
    denormalize_cross_platform_path,
    is_windows_absolute_path,
    join_client_output_path,
)
from platform_api.services.generation_service import (
    normalize_ai_structure_lyrics,
    strip_trailing_lyric_meta_tail,
)


def test_is_windows_absolute_path() -> None:
    assert is_windows_absolute_path(r"C:\Music\run")
    assert not is_windows_absolute_path("/opt/camxora/repo")


def test_join_client_output_path_preserves_windows_path() -> None:
    joined = join_client_output_path(
        r"C:\Users\demo\AppData\Local\Camxora\Media\run",
        "background-16x9.png",
    )
    assert joined == r"C:\Users\demo\AppData\Local\Camxora\Media\run\background-16x9.png"


def test_join_client_output_path_keeps_portable_relative_key() -> None:
    joined = join_client_output_path(
        r"bass-drive\2026-08-06_Album",
        "background-16x9.png",
    )
    assert joined == r"bass-drive\2026-08-06_Album\background-16x9.png"
    # Must not resolve against the API host cwd into an absolute POSIX path.
    assert not joined.startswith("/")
    assert ":" not in joined.split("\\")[0]


def test_denormalize_cross_platform_path() -> None:
    polluted = (
        "/opt/camxora/repo/C:\\Users\\demo\\AppData\\Local\\Camxora\\Media\\run\\background-16x9.png"
    )
    assert denormalize_cross_platform_path(polluted).startswith("C:\\Users\\demo")


def test_strip_trailing_lyric_meta_tail() -> None:
    raw = "\n".join(
        [
            "[Outro]",
            "Hold the last note.",
            "---",
            "**Boat block error-- do not repeat dropped to deep ambient. End**",
        ]
    )
    cleaned = strip_trailing_lyric_meta_tail(raw)
    assert "Boat block" not in cleaned
    assert cleaned.endswith("Hold the last note.")


def test_normalize_ai_structure_lyrics_drops_meta_tail() -> None:
    raw = "\n".join(
        ["[Verse]"]
        + [f"Line {index}" for index in range(16)]
        + ["[Outro]", "Fade out.", "---", "Remaining through - Only low noise then END MARK"]
    )
    normalized = normalize_ai_structure_lyrics(raw)
    assert "END MARK" not in normalized
    assert "Fade out." in normalized
