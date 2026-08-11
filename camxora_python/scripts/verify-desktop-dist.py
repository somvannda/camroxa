"""Verify a packaged Camxora dist folder has required runtime assets."""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_RELATIVE_PATHS = (
    "Camxora.exe",
    "_internal/resources/app-logo.svg",
    "_internal/resources/app-icon.ico",
    "_internal/resources/app-version.txt",
    "_internal/resources/window-close.svg",
    "_internal/resources/window-minimize.svg",
    "_internal/resources/window-maximize.svg",
)


def verify_dist(dist_dir: Path) -> list[str]:
    missing: list[str] = []
    for relative in REQUIRED_RELATIVE_PATHS:
        if not (dist_dir / relative).is_file():
            missing.append(relative)

    # Env file beside exe or under _internal
    env_ok = any(
        (dist_dir / name).is_file() or (dist_dir / "_internal" / name).is_file()
        for name in (".env.sandbox", ".env.production", ".env")
    )
    if not env_ok:
        missing.append(".env.sandbox|.env.production|_internal/.env.*")

    # glfw DLL lands under _internal (name varies by collect layout)
    glfw_hits = list((dist_dir / "_internal").rglob("glfw3.dll")) if (dist_dir / "_internal").is_dir() else []
    if not glfw_hits:
        missing.append("_internal/**/glfw3.dll")

    certifi_hits = list((dist_dir / "_internal").rglob("cacert.pem")) if (dist_dir / "_internal").is_dir() else []
    if not certifi_hits:
        missing.append("_internal/**/cacert.pem")

    # SciPy 1.17+ needs numpy._core in frozen installs (compat package on NumPy 1.26).
    numpy_core = dist_dir / "_internal" / "numpy" / "_core"
    if not numpy_core.is_dir():
        missing.append("_internal/numpy/_core/")

    # GPU / OpenGL stack markers (presence means packaging pulled them in).
    internal = dist_dir / "_internal"
    if internal.is_dir():
        qt_opengl_widgets = list(internal.rglob("Qt6OpenGLWidgets.dll")) + list(
            internal.rglob("*QtOpenGLWidgets*")
        )
        if not qt_opengl_widgets:
            missing.append("_internal/**/Qt6OpenGLWidgets.dll")

        gpu_markers = {
            "moderngl": list(internal.rglob("moderngl*")),
            "pygame": list(internal.rglob("pygame*")),
            "librosa": list(internal.rglob("librosa*")),
            "cv2": list(internal.rglob("cv2*")),
            "numpy": list(internal.rglob("numpy*")),
        }
        for name, hits in gpu_markers.items():
            if not hits:
                missing.append(f"_internal/**/{name}*")

        # MP3 decode path for librosa.load — missing these freezes exports on Loading audio.
        audio_decode_required = (
            "soundfile.py",
            "_soundfile.py",
            "threadpoolctl.py",
            "decorator.py",
            "audioread/__init__.py",
            "librosa/__init__.py",
            "lazy_loader/__init__.py",
            "_soundfile_data/__init__.py",
            "_soundfile_data/libsndfile_x64.dll",
        )
        for relative in audio_decode_required:
            if not (internal / relative).is_file():
                missing.append(f"_internal/{relative}")
        if not list(internal.rglob("libsndfile*")):
            missing.append("_internal/**/libsndfile*")
        for package_name in ("pooch", "joblib", "scipy", "numpy", "sklearn", "numba", "soxr"):
            if not (internal / package_name).exists() and not list(internal.glob(f"{package_name}*")):
                missing.append(f"_internal/{package_name}*")

    ffmpeg = dist_dir / "ffmpeg" / "ffmpeg.exe"
    if not ffmpeg.is_file():
        missing.append("ffmpeg/ffmpeg.exe")

    return missing


def main(argv: list[str]) -> int:
    dist_dir = Path(argv[1] if len(argv) > 1 else "dist/Camxora").resolve()
    if not dist_dir.is_dir():
        print(f"FAIL: dist directory not found: {dist_dir}")
        return 1
    missing = verify_dist(dist_dir)
    if missing:
        print(f"FAIL: missing {len(missing)} required package asset(s) in {dist_dir}:")
        for path in missing:
            print(f"  - {path}")
        return 1
    print(f"OK: package assets verified in {dist_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
