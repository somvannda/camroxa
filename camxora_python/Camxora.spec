# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Camxora desktop (camxora_python).

Build with scripts/build-desktop.ps1 (sandbox or production).
Bundles UI resources, factory video templates, SSL certs, glfw, and the full
GPU preview stack so end users never need pip.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

block_cipher = None

ROOT = Path(SPECPATH).resolve()
REPO_ROOT = ROOT.parent
ENV_FILE = os.environ.get("CAMXORA_ENV_FILE", ".env.sandbox")
env_path = ROOT / ENV_FILE
if not env_path.is_file():
    env_path = ROOT / ".env.sandbox.example"

datas = []
binaries = []
hiddenimports = []

if env_path.is_file():
    datas.append((str(env_path), "."))

resources_dir = ROOT / "resources"
# Bundle the whole tree, then pin critical chrome assets explicitly so a
# partial Analysis never ships without logo / window-control SVGs.
if resources_dir.is_dir():
    datas.append((str(resources_dir), "resources"))
for chrome_name in (
    "app-icon.ico",
    "app-logo.svg",
    "app-version.txt",
    "window-close.svg",
    "window-minimize.svg",
    "window-maximize.svg",
    "log-out.svg",
    "background_login.png",
):
    chrome_path = resources_dir / chrome_name
    if chrome_path.is_file():
        datas.append((str(chrome_path), "resources"))

khmer_font = ROOT / "assets" / "fonts" / "KhmerOS" / "KhmerOSsiemreap.ttf"
if khmer_font.is_file():
    datas.append((str(khmer_font), "assets/fonts/KhmerOS"))

factory_templates = REPO_ROOT / "python_app" / "video_templates_local.json"
# Optional legacy sample catalog — not auto-loaded by the app; keep only if present.
if factory_templates.is_file():
    datas.append((str(factory_templates), "data"))

# Studio editor bundled assets (playlist template backgrounds + thumbnails).
# studio.core.playlist_assets resolves them via __file__ → studio/assets/…
studio_assets = ROOT / "studio" / "assets"
if studio_assets.is_dir():
    datas.append((str(studio_assets), "studio/assets"))

datas += collect_data_files("certifi")
binaries += collect_dynamic_libs("glfw")

# Native / data-heavy packages only. Avoid collect_all() on numpy / PIL / OpenGL
# (huge Analysis time). The audio stack below uses collect_all intentionally.
for package in ("cv2", "moderngl", "pygame", "glfw", "glcontext"):
    try:
        datas += collect_data_files(package)
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass
    hiddenimports.append(package)


def _bundle_module_file(module_name: str) -> None:
    try:
        module = __import__(module_name)
    except Exception:
        return
    module_path = Path(getattr(module, "__file__", "") or "")
    if module_path.is_file():
        datas.append((str(module_path), "."))


def _bundle_package_dir(package_name: str) -> None:
    """Copy an entire package tree into onedir (not only PYZ)."""
    try:
        module = __import__(package_name)
    except Exception:
        return
    module_file = Path(getattr(module, "__file__", "") or "").resolve()
    if not module_file:
        return
    package_dir = module_file.parent if module_file.name.startswith("__init__.") else None
    if package_dir is None or not package_dir.is_dir() or package_dir.name != package_name:
        return
    datas.append((str(package_dir), package_name))


# Studio editor: imageio-ffmpeg ships its own ffmpeg binary (studio export /
# audio/video decode) and sounddevice drives live audio output. Copy the whole
# package trees so the binaries survive freezing even without hooks-contrib.
for package in ("imageio_ffmpeg", "sounddevice"):
    try:
        datas += collect_data_files(package)
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass
    hiddenimports.append(package)
    _bundle_package_dir(package)


# Audio / analysis stack — bundle COMPLETE package trees (not PYZ-only).
# Earlier builds used hiddenimports alone; PyInstaller then omitted top-level
# modules like soundfile.py and _soundfile_data/__init__.py, which made frozen
# librosa/soundfile paths hang. Prefer collect_all for this subsystem.
from PyInstaller.utils.hooks import collect_all  # noqa: E402

# SciPy 1.17+ extensions import ``numpy._core.multiarray``. NumPy 1.26 still
# ships that as a compatibility package on disk, but PyInstaller often omits
# ``numpy._core`` when only ``numpy`` is listed — frozen export then crashes with
# ``ImportError: numpy._core.multiarray failed to import``.
for _package_name in ("numpy", "scipy"):
    try:
        _pkg_datas, _pkg_binaries, _pkg_hidden = collect_all(_package_name)
        datas += _pkg_datas
        binaries += _pkg_binaries
        hiddenimports += _pkg_hidden
    except Exception:
        pass
    _bundle_package_dir(_package_name)
    try:
        hiddenimports += collect_submodules(_package_name)
    except Exception:
        pass

hiddenimports += [
    "numpy._core",
    "numpy._core.multiarray",
    "numpy._core._multiarray_umath",
    "numpy.core",
    "numpy.core.multiarray",
    "scipy.signal",
    "scipy.signal._signal_api",
    "scipy.signal._support_alternative_backends",
]

_AUDIO_STACK = (
    "soundfile",
    "_soundfile_data",
    "audioread",
    "librosa",
    "soxr",
    "lazy_loader",
    "pooch",
    "joblib",
    "decorator",
    "threadpoolctl",
    "msgpack",
    "packaging",
)
for _package_name in _AUDIO_STACK:
    try:
        _pkg_datas, _pkg_binaries, _pkg_hidden = collect_all(_package_name)
        datas += _pkg_datas
        binaries += _pkg_binaries
        hiddenimports += _pkg_hidden
    except Exception:
        pass
    _bundle_package_dir(_package_name)
    try:
        hiddenimports += collect_submodules(_package_name)
    except Exception:
        pass

for _module_name in ("soundfile", "_soundfile", "threadpoolctl", "decorator", "msgpack"):
    _bundle_module_file(_module_name)

# Guarantee _soundfile_data includes __init__.py + DLL (collect_data_files alone
# previously dropped __init__.py and broke soundfile in frozen installs).
try:
    import _soundfile_data as _soundfile_data_pkg

    _soundfile_data_dir = Path(getattr(_soundfile_data_pkg, "__file__", "") or "").resolve().parent
    if _soundfile_data_dir.is_dir():
        datas.append((str(_soundfile_data_dir), "_soundfile_data"))
except Exception:
    pass

hiddenimports += [
    "soundfile",
    "_soundfile",
    "_soundfile_data",
    "audioread",
    "audioread.ffdec",
    "audioread.rawread",
    "threadpoolctl",
    "decorator",
    "lazy_loader",
    "pooch",
    "joblib",
    "soxr",
    "msgpack",
    "librosa",
    "librosa.core",
    "librosa.beat",
    "librosa.onset",
    "librosa.feature",
]

# OpenGL needs platform .dll/.pyd data; pull files without collect_all(OpenGL).
try:
    datas += collect_data_files("OpenGL")
    binaries += collect_dynamic_libs("OpenGL")
except Exception:
    pass
hiddenimports.append("OpenGL")

for package in ("app", "shared", "features", "visualizer", "database"):
    hiddenimports += collect_submodules(package)

# Studio editor modules (skip its tests/ tree — never shipped).
hiddenimports += [
    name
    for name in collect_submodules("studio")
    if not name.startswith("studio.tests")
]

hiddenimports += [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "httpx",
    "httpx._transports",
    "httpx._transports.default",
    "certifi",
    "pydantic",
    "cryptography",
    "websockets",
    "moderngl",
    "moderngl.context",
    "numpy",
    "PIL",
    "PIL.Image",
    "pygame",
    "glfw",
    "OpenGL",
    "OpenGL.GL",
    "librosa",
    "soundfile",
    "_soundfile",
    "audioread",
    "threadpoolctl",
    "cv2",
    "imageio_ffmpeg",
    "sounddevice",
    "visualizer.preview_widget",
    "visualizer.gpu_render",
    "visualizer.audio",
]

# Deduplicate while preserving order
seen: set[str] = set()
unique_hidden: list[str] = []
for name in hiddenimports:
    if name not in seen:
        seen.add(name)
        unique_hidden.append(name)
hiddenimports = unique_hidden

icon_candidates = [
    ROOT / "resources" / "app-icon.ico",
    ROOT / "resources" / "app.ico",
    REPO_ROOT / "python_app" / "assets" / "icons" / "app.ico",
    REPO_ROOT / "camxora" / "public" / "app.ico",
]
icon_path = next((path for path in icon_candidates if path.is_file()), None)
icon = str(icon_path) if icon_path is not None else None

a = Analysis(
    ["run_entry.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "tensorflow",
        "transformers",
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Camxora",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Camxora",
)
