"""FFmpeg path guidance for desktop preferences."""

from __future__ import annotations

from shared.lib.ffmpeg_paths import get_bundled_ffmpeg_path

FFMPEG_DOWNLOAD_PAGE_URL = "https://www.gyan.dev/ffmpeg/builds/"
FFMPEG_WINDOWS_ESSENTIALS_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)

FFMPEG_SETUP_INSTRUCTIONS = (
    "1. Download the FFmpeg essentials ZIP for Windows.\n"
    "2. Extract the ZIP to a folder (for example C:\\Tools\\ffmpeg).\n"
    "3. Browse to the bin folder and select ffmpeg.exe.\n"
    "4. Save Preferences."
)


def ffmpeg_preferences_note() -> str:
    bundled = get_bundled_ffmpeg_path()
    if bundled:
        return (
            "FFmpeg is bundled with Camxora and linked automatically. "
            "You can browse to a different ffmpeg.exe if you prefer a custom build."
        )
    return (
        "FFmpeg was not found in this install. Use Download FFmpeg, extract it, "
        "then browse to ffmpeg.exe — or reinstall Camxora so the bundled copy is included."
    )
